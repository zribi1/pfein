"""Build company-year features and continuity-risk labels from the data lake.

The builder prefers clean Parquet tables, but can fall back to the raw exports
already produced by the source exporters. It writes three datasets:

* features/company_year_features
* features/risk_labels
* features/company_features
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger("build_company_year_features")
MIN_REASONABLE_DATE = "1900-01-01"
FUTURE_DATE_SLACK_DAYS = 366


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    build_company_year_datasets(
        data_lake_dir=Path(args.data_lake_dir or settings.DATA_LAKE_DIR),
        start_year=args.start_year,
        end_year=args.end_year,
        max_companies=args.max_companies,
        year_batch_size=args.year_batch_size,
        overwrite=args.overwrite,
    )


def build_company_year_datasets(
    *,
    data_lake_dir: Path,
    start_year: int,
    end_year: int,
    max_companies: int | None,
    year_batch_size: int | None = None,
    overwrite: bool,
) -> None:
    import duckdb

    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")

    features_dir = data_lake_dir / "features"
    company_year_dir = features_dir / "company_year_features"
    labels_dir = features_dir / "risk_labels"
    company_features_dir = features_dir / "company_features"
    for path in (company_year_dir, labels_dir, company_features_dir):
        _prepare_output_dir(path, data_lake_dir, overwrite)

    con = duckdb.connect()
    try:
        logger.info(
            "feature build started data_lake=%s years=%s-%s overwrite=%s max_companies=%s",
            data_lake_dir,
            start_year,
            end_year,
            overwrite,
            max_companies,
        )
        if year_batch_size is not None and year_batch_size < 1:
            raise ValueError("year_batch_size must be greater than or equal to 1")
        _configure_duckdb(con, data_lake_dir)
        sources = _SourceRoots(data_lake_dir)
        logger.info("feature source roots=%s", sources.as_dict())
        _create_company_identity_view(con, sources.company_identity)
        _create_legal_events_view(con, sources.legal_events)
        _create_formalities_view(con, sources.formalities_events)
        _create_annual_accounts_view(con, sources.annual_accounts)
        _create_financials_view(con, sources.financials)

        limit_sql = f"LIMIT {int(max_companies)}" if max_companies else ""
        con.execute(
            f"""
            CREATE TEMP TABLE companies AS
            SELECT DISTINCT siren
            FROM (
                SELECT siren FROM company_identity WHERE siren IS NOT NULL
                UNION
                SELECT siren FROM legal_events WHERE siren IS NOT NULL
                UNION
                SELECT siren FROM formalities_events WHERE siren IS NOT NULL
                UNION
                SELECT siren FROM annual_accounts WHERE siren IS NOT NULL
                UNION
                SELECT siren FROM financials WHERE siren IS NOT NULL
            )
            ORDER BY siren
            {limit_sql}
            """
        )

        companies = con.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        logger.info("feature build companies=%s years=%s-%s", companies, start_year, end_year)
        if companies == 0:
            raise RuntimeError("no companies found in clean/raw data lake sources")

        feature_rows = 0
        label_rows = 0
        batches = _year_batches(start_year, end_year, year_batch_size)
        for batch_index, (batch_start, batch_end) in enumerate(batches, start=1):
            logger.info(
                "feature batch %s/%s years=%s-%s",
                batch_index,
                len(batches),
                batch_start,
                batch_end,
            )
            _drop_feature_temp_tables(con)
            _create_years_table(con, batch_start, batch_end)
            _create_feature_tables(con)
            logger.info("feature tables created in DuckDB; writing company_year_features")
            _write_partitioned(con, "company_year_feature_rows", company_year_dir)
            batch_feature_rows = _count(con, "company_year_feature_rows")
            feature_rows += batch_feature_rows
            logger.info("feature write done company_year_features rows=%s", batch_feature_rows)
            logger.info("writing risk_labels")
            _write_partitioned(con, "risk_label_rows", labels_dir)
            batch_label_rows = _count(con, "risk_label_rows")
            label_rows += batch_label_rows
            logger.info("feature write done risk_labels rows=%s", batch_label_rows)

        logger.info("writing company_features")
        _write_single_file(con, "company_feature_rows", company_features_dir / "company_features.parquet")
        logger.info("feature write done company_features rows=%s", _count(con, "company_feature_rows"))

        _write_manifest(
            company_year_dir,
            {
                "dataset": "company_year_features",
                "rows": feature_rows,
                "start_year": start_year,
                "end_year": end_year,
                "max_companies": max_companies,
                "year_batch_size": year_batch_size,
                "source_roots": sources.as_dict(),
            },
        )
        _write_manifest(
            labels_dir,
            {
                "dataset": "risk_labels",
                "rows": label_rows,
                "start_year": start_year,
                "end_year": end_year,
                "max_companies": max_companies,
                "year_batch_size": year_batch_size,
                "source_roots": sources.as_dict(),
            },
        )
        _write_manifest(
            company_features_dir,
            {
                "dataset": "company_features",
                "rows": _count(con, "company_feature_rows"),
                "source": "latest prediction year from company_year_features",
            },
        )
    finally:
        con.close()


class _SourceRoots:
    def __init__(self, data_lake_dir: Path) -> None:
        self.data_lake_dir = data_lake_dir
        self.company_identity = _first_dataset(
            data_lake_dir / "clean" / "company_identity",
            data_lake_dir / "raw" / "insee" / "unites_legales",
            data_lake_dir / "raw" / "insee" / "bulk" / "stock_unite_legale",
        )
        self.legal_events = _first_dataset(
            data_lake_dir / "clean" / "legal_events",
            data_lake_dir / "raw" / "bodacc",
        )
        self.formalities_events = _first_dataset(
            data_lake_dir / "clean" / "formalities_events",
            data_lake_dir / "raw" / "inpi" / "formalites",
        )
        self.annual_accounts = _first_dataset(
            data_lake_dir / "clean" / "annual_accounts",
            data_lake_dir / "raw" / "inpi" / "comptes_annuels",
        )
        self.financials = _first_dataset(
            data_lake_dir / "clean" / "financials",
            data_lake_dir / "raw" / "financials",
            data_lake_dir / "raw" / "financial",
        )

    def as_dict(self) -> dict[str, str | None]:
        return {
            "company_identity": str(self.company_identity) if self.company_identity else None,
            "legal_events": str(self.legal_events) if self.legal_events else None,
            "formalities_events": str(self.formalities_events) if self.formalities_events else None,
            "annual_accounts": str(self.annual_accounts) if self.annual_accounts else None,
            "financials": str(self.financials) if self.financials else None,
        }


def _create_company_identity_view(con: Any, root: Path | None) -> None:
    _create_normalized_view(
        con,
        "company_identity",
        root,
        {
            "siren": ("VARCHAR", ("siren",)),
            "company_name": ("VARCHAR", ("company_name", "denomination", "denomination_periode", "nom")),
            "activity_code": ("VARCHAR", ("activity_code", "activite_principale", "activite_principale_periode")),
            "legal_category_code": ("VARCHAR", ("legal_category_code", "categorie_juridique")),
            "administrative_status": ("VARCHAR", ("administrative_status", "etat_administratif")),
            "creation_date": ("DATE", ("creation_date", "date_creation")),
            "closure_date": ("DATE", ("closure_date", "date_cessation", "date_cessation_activite")),
            "status_period_start": ("DATE", ("last_insee_period_start", "date_debut_periode")),
            "employee_size_bracket": ("VARCHAR", ("employee_size_bracket", "tranche_effectifs")),
        },
    )


def _create_legal_events_view(con: Any, root: Path | None) -> None:
    _create_normalized_view(
        con,
        "legal_events",
        root,
        {
            "siren": ("VARCHAR", ("siren",)),
            "event_date": ("DATE", ("event_date", "eventDate", "date_parution", "dateParution")),
            "event_category": ("VARCHAR", ("event_category", "eventCategory", "bodacc_family", "bodaccFamily")),
            "event_type": ("VARCHAR", ("event_type", "eventType", "jugement_nature", "jugementNature")),
            "is_risk_event": ("BOOLEAN", ("is_risk_event", "isRiskEvent")),
            "is_radiation": ("BOOLEAN", ("is_radiation", "isRadiation")),
            "flag_liquidation": ("BOOLEAN", ("flag_liquidation", "liquidation")),
            "flag_redressement": ("BOOLEAN", ("flag_redressement", "redressement")),
            "flag_sauvegarde": ("BOOLEAN", ("flag_sauvegarde", "sauvegarde")),
            "flag_procedure_collective": ("BOOLEAN", ("flag_procedure_collective", "procedureCollective")),
            "flag_cessation_paiement": ("BOOLEAN", ("flag_cessation_paiement", "cessationPaiement")),
        },
    )


def _create_formalities_view(con: Any, root: Path | None) -> None:
    _create_normalized_view(
        con,
        "formalities_events",
        root,
        {
            "siren": ("VARCHAR", ("siren",)),
            "event_date": ("DATE", ("event_date", "date_depot", "dateDepot", "updated_at_source")),
            "event_type": ("VARCHAR", ("event_type", "type_formalite", "formality_type", "category")),
            "event_text": ("VARCHAR", ("event_text", "formality_label", "denomination", "category")),
        },
    )


def _create_annual_accounts_view(con: Any, root: Path | None) -> None:
    _create_normalized_view(
        con,
        "annual_accounts",
        root,
        {
            "siren": ("VARCHAR", ("siren",)),
            "closing_date": ("DATE", ("closing_date", "date_cloture", "dateCloture")),
            "filing_date": ("DATE", ("filing_date", "date_depot", "dateDepot", "updated_at_source")),
            "account_type": ("VARCHAR", ("account_type", "type_bilan", "typeBilan")),
            "confidentiality": ("VARCHAR", ("confidentiality",)),
        },
    )


def _create_financials_view(con: Any, root: Path | None) -> None:
    _create_normalized_view(
        con,
        "financials_source",
        root,
        {
            "siren": ("VARCHAR", ("siren", "SIREN")),
            "financial_year": ("INTEGER", ("financial_year", "year", "annee", "exercice")),
            "closing_date": ("DATE", ("closing_date", "date_cloture", "dateCloture")),
            "revenue": ("DOUBLE", ("revenue", "chiffre_affaires", "ca", "chiffreAffaires")),
            "net_result": ("DOUBLE", ("net_result", "resultat_net", "resultatNet", "benefice")),
            "equity": ("DOUBLE", ("equity", "capitaux_propres", "capitauxPropres")),
            "debt": ("DOUBLE", ("debt", "dettes", "total_dettes", "totalDettes")),
            "total_assets": ("DOUBLE", ("total_assets", "totalAssets", "total_actifs", "totalActifs")),
            "net_margin": ("DOUBLE", ("net_margin",)),
            "debt_to_assets": ("DOUBLE", ("debt_to_assets",)),
            "equity_ratio": ("DOUBLE", ("equity_ratio",)),
            "debt_to_equity": ("DOUBLE", ("debt_to_equity",)),
            "has_negative_result": ("BOOLEAN", ("has_negative_result",)),
            "has_negative_equity": ("BOOLEAN", ("has_negative_equity",)),
            "account_type": ("VARCHAR", ("account_type", "type_bilan", "typeBilan")),
            "confidentiality": ("VARCHAR", ("confidentiality",)),
        },
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW financials AS
        SELECT
            siren,
            COALESCE(financial_year, YEAR(closing_date))::INTEGER AS financial_year,
            closing_date,
            revenue,
            net_result,
            equity,
            debt,
            total_assets,
            net_margin,
            debt_to_assets,
            equity_ratio,
            debt_to_equity,
            has_negative_result,
            has_negative_equity,
            account_type,
            confidentiality
        FROM financials_source
        """
    )


def _create_feature_tables(con: Any) -> None:
    con.execute(
        """
        CREATE TEMP TABLE base_rows AS
        WITH company_creation AS (
            SELECT siren, min(creation_date) AS creation_date
            FROM company_identity
            GROUP BY siren
        )
        SELECT
            c.siren,
            y.prediction_year,
            make_date(y.prediction_year, 12, 31) AS prediction_date
        FROM companies c
        CROSS JOIN years y
        LEFT JOIN company_creation cc ON cc.siren = c.siren
        WHERE cc.creation_date IS NULL
           OR cc.creation_date <= make_date(y.prediction_year, 12, 31)
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE company_year_feature_rows AS
        WITH identity_features AS (
            SELECT
                b.siren,
                b.prediction_year,
                b.prediction_date,
                any_value(i.company_name) AS company_name,
                any_value(i.activity_code) AS activity_code,
                any_value(i.legal_category_code) AS legal_category_code,
                any_value(i.employee_size_bracket) AS employee_size_bracket,
                min(i.creation_date) AS creation_date,
                max(
                    CASE
                        WHEN i.status_period_start IS NULL OR i.status_period_start <= b.prediction_date
                        THEN i.administrative_status
                        ELSE NULL
                    END
                ) AS administrative_status_at_cutoff
            FROM base_rows b
            LEFT JOIN company_identity i ON i.siren = b.siren
            GROUP BY b.siren, b.prediction_year, b.prediction_date
        ),
        legal_features AS (
            SELECT
                b.siren,
                b.prediction_year,
                count(e.event_date) FILTER (WHERE e.event_date <= b.prediction_date) AS legal_events_count_all,
                count(e.event_date) FILTER (
                    WHERE e.event_date > b.prediction_date - INTERVAL 365 DAY
                      AND e.event_date <= b.prediction_date
                ) AS legal_events_count_12m,
                count(e.event_date) FILTER (
                    WHERE e.event_date <= b.prediction_date
                      AND COALESCE(e.is_risk_event, false)
                ) AS legal_risk_events_count_all,
                count(e.event_date) FILTER (
                    WHERE e.event_date > b.prediction_date - INTERVAL 365 DAY
                      AND e.event_date <= b.prediction_date
                      AND COALESCE(e.is_risk_event, false)
                ) AS legal_risk_events_count_12m,
                count(e.event_date) FILTER (
                    WHERE e.event_date <= b.prediction_date
                      AND (
                        COALESCE(e.flag_liquidation, false)
                        OR COALESCE(e.flag_redressement, false)
                        OR COALESCE(e.flag_sauvegarde, false)
                        OR COALESCE(e.flag_procedure_collective, false)
                      )
                ) AS legal_distress_events_count_all,
                count(e.event_date) FILTER (
                    WHERE e.event_date <= b.prediction_date
                      AND COALESCE(e.is_radiation, false)
                ) AS radiation_events_count_all,
                date_diff('day', max(e.event_date), b.prediction_date) AS days_since_last_legal_event
            FROM base_rows b
            LEFT JOIN legal_events e ON e.siren = b.siren AND e.event_date <= b.prediction_date
            GROUP BY b.siren, b.prediction_year, b.prediction_date
        ),
        formality_features AS (
            SELECT
                b.siren,
                b.prediction_year,
                count(f.event_date) FILTER (WHERE f.event_date <= b.prediction_date) AS formalities_count_all,
                count(f.event_date) FILTER (
                    WHERE f.event_date > b.prediction_date - INTERVAL 365 DAY
                      AND f.event_date <= b.prediction_date
                ) AS formalities_count_12m,
                count(f.event_date) FILTER (
                    WHERE f.event_date <= b.prediction_date
                      AND (
                        lower(COALESCE(f.event_type, '') || ' ' || COALESCE(f.event_text, '')) LIKE '%cessation%'
                        OR lower(COALESCE(f.event_type, '') || ' ' || COALESCE(f.event_text, '')) LIKE '%radiation%'
                        OR lower(COALESCE(f.event_type, '') || ' ' || COALESCE(f.event_text, '')) LIKE '%fermeture%'
                      )
                ) AS cessation_formalities_count_all
            FROM base_rows b
            LEFT JOIN formalities_events f ON f.siren = b.siren AND f.event_date <= b.prediction_date
            GROUP BY b.siren, b.prediction_year
        ),
        account_features AS (
            SELECT
                b.siren,
                b.prediction_year,
                count(a.filing_date) FILTER (WHERE a.filing_date <= b.prediction_date) AS annual_accounts_count_all,
                count(a.filing_date) FILTER (
                    WHERE a.filing_date > b.prediction_date - INTERVAL 730 DAY
                      AND a.filing_date <= b.prediction_date
                ) AS annual_accounts_count_24m,
                date_diff('day', max(a.filing_date), b.prediction_date) AS days_since_last_account_filing,
                max(YEAR(a.closing_date)) FILTER (WHERE a.closing_date <= b.prediction_date) AS latest_account_closing_year
            FROM base_rows b
            LEFT JOIN annual_accounts a ON a.siren = b.siren AND a.filing_date <= b.prediction_date
            GROUP BY b.siren, b.prediction_year, b.prediction_date
        ),
        financial_features AS (
            SELECT
                b.siren,
                b.prediction_year,
                arg_max(fin.revenue, fin.financial_year) AS latest_revenue,
                arg_max(fin.net_result, fin.financial_year) AS latest_net_result,
                arg_max(fin.equity, fin.financial_year) AS latest_equity,
                arg_max(fin.debt, fin.financial_year) AS latest_debt,
                arg_max(fin.total_assets, fin.financial_year) AS latest_total_assets,
                arg_max(fin.net_margin, fin.financial_year) AS latest_net_margin,
                arg_max(fin.debt_to_assets, fin.financial_year) AS latest_debt_to_assets,
                arg_max(fin.equity_ratio, fin.financial_year) AS latest_equity_ratio,
                arg_max(fin.debt_to_equity, fin.financial_year) AS latest_debt_to_equity,
                max(CASE WHEN COALESCE(fin.has_negative_result, false) THEN 1 ELSE 0 END)::BOOLEAN AS has_negative_result_history,
                max(CASE WHEN COALESCE(fin.has_negative_equity, false) THEN 1 ELSE 0 END)::BOOLEAN AS has_negative_equity_history,
                count(fin.financial_year) AS financial_years_available,
                max(fin.financial_year) AS latest_financial_year,
                max(CASE WHEN fin.confidentiality IS NOT NULL THEN 1 ELSE 0 END)::BOOLEAN AS has_confidential_financials,
                max(CASE WHEN fin.financial_year = b.prediction_year - 1 THEN fin.revenue ELSE NULL END) AS previous_year_revenue,
                max(CASE WHEN fin.financial_year = b.prediction_year - 1 THEN fin.net_result ELSE NULL END) AS previous_year_net_result
            FROM base_rows b
            LEFT JOIN financials fin
              ON fin.siren = b.siren
             AND fin.financial_year <= b.prediction_year
            GROUP BY b.siren, b.prediction_year
        )
        SELECT
            i.siren,
            i.prediction_year,
            i.prediction_date,
            i.company_name,
            i.activity_code,
            i.legal_category_code,
            i.employee_size_bracket,
            i.administrative_status_at_cutoff,
            CASE
                WHEN i.creation_date IS NULL THEN NULL
                ELSE date_diff('year', i.creation_date, i.prediction_date)
            END AS company_age_years,
            COALESCE(l.legal_events_count_all, 0) AS legal_events_count_all,
            COALESCE(l.legal_events_count_12m, 0) AS legal_events_count_12m,
            COALESCE(l.legal_risk_events_count_all, 0) AS legal_risk_events_count_all,
            COALESCE(l.legal_risk_events_count_12m, 0) AS legal_risk_events_count_12m,
            COALESCE(l.legal_distress_events_count_all, 0) AS legal_distress_events_count_all,
            COALESCE(l.radiation_events_count_all, 0) AS radiation_events_count_all,
            l.days_since_last_legal_event,
            COALESCE(f.formalities_count_all, 0) AS formalities_count_all,
            COALESCE(f.formalities_count_12m, 0) AS formalities_count_12m,
            COALESCE(f.cessation_formalities_count_all, 0) AS cessation_formalities_count_all,
            COALESCE(a.annual_accounts_count_all, 0) AS annual_accounts_count_all,
            COALESCE(a.annual_accounts_count_24m, 0) AS annual_accounts_count_24m,
            a.days_since_last_account_filing,
            a.latest_account_closing_year,
            fin.latest_revenue,
            fin.latest_net_result,
            fin.latest_equity,
            fin.latest_debt,
            fin.latest_total_assets,
            fin.latest_net_margin,
            fin.latest_debt_to_assets,
            fin.latest_equity_ratio,
            fin.latest_debt_to_equity,
            fin.has_negative_result_history,
            fin.has_negative_equity_history,
            (fin.financial_years_available > 0)::BOOLEAN AS has_financial_data,
            COALESCE(fin.financial_years_available, 0) AS financial_years_available,
            fin.latest_financial_year,
            CASE
                WHEN fin.latest_financial_year IS NULL THEN NULL
                ELSE i.prediction_year - fin.latest_financial_year
            END AS years_since_last_financial_statement,
            COALESCE(fin.has_confidential_financials, false) AS has_confidential_financials,
            CASE
                WHEN fin.previous_year_revenue IS NULL OR fin.previous_year_revenue = 0 THEN NULL
                ELSE (fin.latest_revenue - fin.previous_year_revenue) / abs(fin.previous_year_revenue)
            END AS revenue_growth_1y,
            fin.latest_net_result - fin.previous_year_net_result AS net_result_change_1y
        FROM identity_features i
        LEFT JOIN legal_features l USING (siren, prediction_year)
        LEFT JOIN formality_features f USING (siren, prediction_year)
        LEFT JOIN account_features a USING (siren, prediction_year)
        LEFT JOIN financial_features fin USING (siren, prediction_year)
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE risk_label_rows AS
        WITH future_legal AS (
            SELECT
                b.siren,
                b.prediction_year,
                max(
                    CASE WHEN (
                        COALESCE(e.flag_liquidation, false)
                        OR COALESCE(e.flag_redressement, false)
                        OR COALESCE(e.flag_sauvegarde, false)
                        OR COALESCE(e.flag_procedure_collective, false)
                    ) THEN 1 ELSE 0 END
                ) AS legal_distress_risk_12m_label,
                max(CASE WHEN COALESCE(e.is_radiation, false) THEN 1 ELSE 0 END) AS radiation_risk_12m_bodacc,
                min(e.event_date) AS first_future_legal_event_date
            FROM base_rows b
            LEFT JOIN legal_events e
              ON e.siren = b.siren
             AND e.event_date > b.prediction_date
             AND e.event_date <= b.prediction_date + INTERVAL 12 MONTH
            GROUP BY b.siren, b.prediction_year
        ),
        future_formalities AS (
            SELECT
                b.siren,
                b.prediction_year,
                max(
                    CASE WHEN (
                        lower(COALESCE(f.event_type, '') || ' ' || COALESCE(f.event_text, '')) LIKE '%cessation%'
                        OR lower(COALESCE(f.event_type, '') || ' ' || COALESCE(f.event_text, '')) LIKE '%radiation%'
                        OR lower(COALESCE(f.event_type, '') || ' ' || COALESCE(f.event_text, '')) LIKE '%fermeture%'
                    ) THEN 1 ELSE 0 END
                ) AS radiation_risk_12m_inpi
            FROM base_rows b
            LEFT JOIN formalities_events f
              ON f.siren = b.siren
             AND f.event_date > b.prediction_date
             AND f.event_date <= b.prediction_date + INTERVAL 12 MONTH
            GROUP BY b.siren, b.prediction_year
        ),
        future_insee AS (
            SELECT
                b.siren,
                b.prediction_year,
                max(
                    CASE WHEN (
                        i.closure_date > b.prediction_date
                        AND i.closure_date <= b.prediction_date + INTERVAL 12 MONTH
                    ) OR (
                        upper(COALESCE(i.administrative_status, '')) IN ('C', 'CESSEE', 'FERMEE', 'INACTIVE')
                        AND i.status_period_start > b.prediction_date
                        AND i.status_period_start <= b.prediction_date + INTERVAL 12 MONTH
                    ) THEN 1 ELSE 0 END
                ) AS insee_closure_risk_12m_label
            FROM base_rows b
            LEFT JOIN company_identity i ON i.siren = b.siren
            GROUP BY b.siren, b.prediction_year
        ),
        future_financials AS (
            SELECT
                b.siren,
                b.prediction_year,
                max(
                    CASE WHEN fin.financial_year = b.prediction_year + 1
                       AND (
                            COALESCE(fin.net_result, 0) < 0
                            OR COALESCE(fin.equity, 0) < 0
                       )
                    THEN 1 ELSE 0 END
                ) AS financial_weakness_risk_12m_label
            FROM base_rows b
            LEFT JOIN financials fin ON fin.siren = b.siren
            GROUP BY b.siren, b.prediction_year
        ),
        filing_anomaly AS (
            SELECT
                f.siren,
                f.prediction_year,
                CASE
                    WHEN f.annual_accounts_count_24m > 0
                     AND NOT EXISTS (
                        SELECT 1
                        FROM annual_accounts a
                        WHERE a.siren = f.siren
                          AND a.filing_date > f.prediction_date
                          AND a.filing_date <= f.prediction_date + INTERVAL 18 MONTH
                     )
                    THEN 1 ELSE 0
                END AS filing_anomaly_risk_12m_label
            FROM company_year_feature_rows f
        )
        SELECT
            b.siren,
            b.prediction_year,
            b.prediction_date,
            COALESCE(fl.legal_distress_risk_12m_label, 0)::BOOLEAN AS legal_distress_risk_12m_label,
            (
                COALESCE(fl.radiation_risk_12m_bodacc, 0) = 1
                OR COALESCE(ff.radiation_risk_12m_inpi, 0) = 1
            ) AS radiation_risk_12m_label,
            COALESCE(fin.financial_weakness_risk_12m_label, 0)::BOOLEAN AS financial_weakness_risk_12m_label,
            COALESCE(fa.filing_anomaly_risk_12m_label, 0)::BOOLEAN AS filing_anomaly_risk_12m_label,
            (
                COALESCE(fi.insee_closure_risk_12m_label, 0) = 1
                OR COALESCE(fl.legal_distress_risk_12m_label, 0) = 1
                OR COALESCE(fl.radiation_risk_12m_bodacc, 0) = 1
                OR COALESCE(ff.radiation_risk_12m_inpi, 0) = 1
            ) AS continuity_risk_12m_label,
            fl.first_future_legal_event_date
        FROM base_rows b
        LEFT JOIN future_legal fl USING (siren, prediction_year)
        LEFT JOIN future_formalities ff USING (siren, prediction_year)
        LEFT JOIN future_insee fi USING (siren, prediction_year)
        LEFT JOIN future_financials fin USING (siren, prediction_year)
        LEFT JOIN filing_anomaly fa USING (siren, prediction_year)
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE company_feature_rows AS
        SELECT *
        FROM company_year_feature_rows
        QUALIFY row_number() OVER (PARTITION BY siren ORDER BY prediction_year DESC) = 1
        """
    )


def _year_batches(start_year: int, end_year: int, year_batch_size: int | None) -> list[tuple[int, int]]:
    if not year_batch_size:
        return [(start_year, end_year)]
    batches = []
    batch_start = start_year
    while batch_start <= end_year:
        batch_end = min(batch_start + year_batch_size - 1, end_year)
        batches.append((batch_start, batch_end))
        batch_start = batch_end + 1
    return batches


def _create_years_table(con: Any, start_year: int, end_year: int) -> None:
    con.execute(
        """
        CREATE TEMP TABLE years AS
        SELECT prediction_year::INTEGER AS prediction_year
        FROM range(?, ? + 1) AS y(prediction_year)
        """,
        [start_year, end_year],
    )


def _drop_feature_temp_tables(con: Any) -> None:
    for table_name in (
        "company_feature_rows",
        "risk_label_rows",
        "company_year_feature_rows",
        "base_rows",
        "years",
    ):
        con.execute(f"DROP TABLE IF EXISTS {table_name}")


def _create_normalized_view(
    con: Any,
    view_name: str,
    root: Path | None,
    columns: dict[str, tuple[str, tuple[str, ...]]],
) -> None:
    if root is None or not _has_parquet(root):
        select_sql = ", ".join(f"NULL::{sql_type} AS {name}" for name, (sql_type, _) in columns.items())
        con.execute(f"CREATE OR REPLACE TEMP VIEW {view_name} AS SELECT {select_sql} WHERE FALSE")
        logger.info("created empty view %s", view_name)
        return

    path = _duckdb_glob(root)
    available = _parquet_columns(con, path)
    select_parts = [
        f"{_coalesce_expr(available, candidates, sql_type)} AS {name}"
        for name, (sql_type, candidates) in columns.items()
    ]
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW {view_name} AS
        SELECT {", ".join(select_parts)}
        FROM read_parquet('{_sql_string(path)}', union_by_name=true)
        """
    )
    logger.info("created view %s from %s", view_name, root)


def _coalesce_expr(available: set[str], candidates: tuple[str, ...], sql_type: str) -> str:
    exprs = []
    for candidate in candidates:
        match = _find_column(available, candidate)
        if match:
            expr = f"TRY_CAST({_quote_ident(match)} AS {sql_type})"
            expr = _bounded_temporal_expr(expr, sql_type)
            if sql_type == "VARCHAR":
                expr = f"NULLIF(TRIM({expr}), '')"
            exprs.append(expr)
    if not exprs:
        return f"NULL::{sql_type}"
    if len(exprs) == 1:
        return exprs[0]
    return f"COALESCE({', '.join(exprs)})"


def _bounded_temporal_expr(expr: str, sql_type: str) -> str:
    normalized = sql_type.upper()
    if normalized == "DATE":
        return (
            "CASE "
            f"WHEN {expr} BETWEEN DATE '{MIN_REASONABLE_DATE}' "
            f"AND CAST(CURRENT_DATE + INTERVAL {FUTURE_DATE_SLACK_DAYS} DAY AS DATE) "
            f"THEN {expr} ELSE NULL::DATE END"
        )
    if normalized == "TIMESTAMP":
        return (
            "CASE "
            f"WHEN {expr} BETWEEN CAST(DATE '{MIN_REASONABLE_DATE}' AS TIMESTAMP) "
            f"AND (CURRENT_TIMESTAMP + INTERVAL {FUTURE_DATE_SLACK_DAYS} DAY) "
            f"THEN {expr} ELSE NULL::TIMESTAMP END"
        )
    return expr


def _find_column(available: set[str], candidate: str) -> str | None:
    lowered = {column.lower(): column for column in available}
    return lowered.get(candidate.lower())


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _parquet_columns(con: Any, glob_path: str) -> set[str]:
    rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{_sql_string(glob_path)}', union_by_name=true)"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _first_dataset(*roots: Path) -> Path | None:
    for root in roots:
        if _has_parquet(root):
            return root
    return None


def _has_parquet(root: Path) -> bool:
    return root.exists() and any(root.rglob("*.parquet"))


def _duckdb_glob(root: Path) -> str:
    return str(root / "**" / "*.parquet").replace("\\", "/")


def _sql_string(value: str) -> str:
    return value.replace("'", "''")


def _prepare_output_dir(path: Path, data_lake_dir: Path, overwrite: bool) -> None:
    if path.exists() and overwrite:
        resolved = path.resolve()
        root = data_lake_dir.resolve()
        if root not in resolved.parents and resolved != root:
            raise RuntimeError(f"refusing to delete output outside data lake: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _write_partitioned(con: Any, table_name: str, output_dir: Path) -> None:
    target = _sql_string(str(output_dir).replace("\\", "/"))
    con.execute(
        f"""
        COPY (SELECT * FROM {table_name})
        TO '{target}'
        (FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (prediction_year), OVERWRITE_OR_IGNORE TRUE)
        """
    )


def _write_single_file(con: Any, table_name: str, output_file: Path) -> None:
    target = _sql_string(str(output_file).replace("\\", "/"))
    con.execute(
        f"""
        COPY (SELECT * FROM {table_name})
        TO '{target}'
        (FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE TRUE)
        """
    )


def _write_manifest(output_dir: Path, payload: dict[str, Any]) -> None:
    payload = {
        **payload,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    (output_dir / "_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _count(con: Any, table_name: str) -> int:
    return int(con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _configure_duckdb(con: Any, data_lake_dir: Path) -> None:
    temp_dir = _duckdb_temp_dir(data_lake_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory = '{_sql_string(str(temp_dir).replace('\\', '/'))}'")
    con.execute("PRAGMA enable_progress_bar")


def _duckdb_temp_dir(data_lake_dir: Path) -> Path:
    configured = os.environ.get("DUCKDB_TEMP_DIRECTORY")
    if configured:
        return Path(configured)
    if str(data_lake_dir).startswith("/content/drive/"):
        return Path("/content/pfein_duckdb_tmp")
    return data_lake_dir / "tmp" / "duckdb"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build company-year ML features and risk labels.")
    parser.add_argument("--data-lake-dir", help="Defaults to DATA_LAKE_DIR.")
    parser.add_argument("--start-year", type=int, default=2017)
    parser.add_argument(
        "--end-year",
        type=int,
        default=datetime.now(tz=timezone.utc).year - 1,
        help="Default is previous calendar year, so 12-month labels can exist.",
    )
    parser.add_argument("--max-companies", type=int, help="Optional smoke-test cap.")
    parser.add_argument(
        "--year-batch-size",
        type=int,
        help="Build and write prediction years in smaller batches to reduce peak memory.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    main()
