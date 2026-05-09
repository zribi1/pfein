from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import DEFAULT_DRIVE_ROOT, install_deps, paths


LABEL_COLUMNS = [
    "continuity_risk_12m_label",
    "legal_distress_risk_12m_label",
    "radiation_risk_12m_label",
    "financial_weakness_risk_12m_label",
    "filing_anomaly_risk_12m_label",
]

FORBIDDEN_MODEL_COLUMNS = {
    "siren",
    "prediction_date",
    "first_future_legal_event_date",
    *LABEL_COLUMNS,
}

FEATURE_SAFETY = [
    ("siren", "technical_key", "excluded", "Identifiant de jointure, exclu de l'entraînement pour éviter la mémorisation."),
    ("prediction_year", "temporal_key", "safe_historical", "Année d'observation utilisée pour construire la date de coupure."),
    ("prediction_date", "temporal_key", "excluded", "Date de coupure utile pour l'audit, exclue du modèle."),
    ("company_name", "INSEE", "excluded_or_display_only", "Nom utile pour l'affichage et l'audit, pas un signal ML robuste."),
    ("activity_code", "INSEE", "needs_verification", "Code d'activité conservé depuis l'identité; vérifier la validité historique si l'activité change."),
    ("legal_category_code", "INSEE", "needs_verification", "Catégorie juridique potentiellement évolutive; vérifier l'historique source."),
    ("employee_size_bracket", "INSEE", "needs_verification", "Tranche d'effectif potentiellement datée; vérifier la source et l'année."),
    ("administrative_status_at_cutoff", "INSEE", "needs_verification", "Doit provenir d'une période <= prediction_date; point sensible anti-leakage."),
    ("company_age_years", "INSEE", "safe_derived_from_historical_date", "Calculé depuis creation_date et prediction_date."),
    ("legal_events_count_all", "BODACC", "safe_event_based", "Événements filtrés avec event_date <= prediction_date."),
    ("legal_events_count_12m", "BODACC", "safe_event_based", "Événements filtrés dans les 12 mois avant prediction_date."),
    ("legal_risk_events_count_all", "BODACC", "safe_event_based", "Événements risqués passés uniquement."),
    ("legal_risk_events_count_12m", "BODACC", "safe_event_based", "Événements risqués récents passés uniquement."),
    ("legal_distress_events_count_all", "BODACC", "safe_event_based", "Historique passé de procédures collectives."),
    ("radiation_events_count_all", "BODACC", "safe_event_based", "Radiations passées uniquement."),
    ("days_since_last_legal_event", "BODACC", "safe_derived_from_historical_date", "Calculé depuis le dernier event_date passé et prediction_date."),
    ("formalities_count_all", "INPI formalites", "safe_event_based", "Formalités passées uniquement."),
    ("formalities_count_12m", "INPI formalites", "safe_event_based", "Formalités des 12 mois avant prediction_date."),
    ("cessation_formalities_count_all", "INPI formalites", "safe_event_based", "Cessation/radiation/fermeture passées uniquement."),
    ("annual_accounts_count_all", "INPI comptes annuels", "safe_event_based", "Dépôts passés uniquement."),
    ("annual_accounts_count_24m", "INPI comptes annuels", "safe_event_based", "Dépôts des 24 mois avant prediction_date."),
    ("days_since_last_account_filing", "INPI comptes annuels", "safe_derived_from_historical_date", "Calculé depuis le dernier dépôt passé."),
    ("latest_account_closing_year", "INPI comptes annuels", "safe_historical", "Année de clôture max avec dépôt disponible avant prediction_date."),
    ("latest_revenue", "financials", "safe_historical", "Dernière valeur avec financial_year <= prediction_year."),
    ("latest_net_result", "financials", "safe_historical", "Dernière valeur avec financial_year <= prediction_year."),
    ("latest_equity", "financials", "safe_historical", "Dernière valeur avec financial_year <= prediction_year."),
    ("latest_debt", "financials", "safe_historical", "Dernière valeur avec financial_year <= prediction_year."),
    ("latest_total_assets", "financials", "safe_historical", "Dernière valeur avec financial_year <= prediction_year."),
    ("latest_net_margin", "financials", "safe_historical", "Ratio issu de la dernière année financière passée."),
    ("latest_debt_to_assets", "financials", "safe_historical", "Ratio issu de la dernière année financière passée."),
    ("latest_equity_ratio", "financials", "safe_historical", "Ratio issu de la dernière année financière passée."),
    ("latest_debt_to_equity", "financials", "safe_historical", "Ratio issu de la dernière année financière passée."),
    ("has_negative_result_history", "financials", "safe_historical", "Historique financier jusqu'à prediction_year."),
    ("has_negative_equity_history", "financials", "safe_historical", "Historique financier jusqu'à prediction_year."),
    ("has_financial_data", "financials", "safe_derived", "Indicateur de disponibilité, pas une valeur future."),
    ("financial_years_available", "financials", "safe_historical", "Nombre d'années disponibles jusqu'à prediction_year."),
    ("latest_financial_year", "financials", "safe_historical", "Doit être <= prediction_year."),
    ("years_since_last_financial_statement", "financials", "safe_derived_from_historical_date", "Calculé avec prediction_year et latest_financial_year."),
    ("has_confidential_financials", "financials", "safe_historical", "Indicateur de confidentialité observé dans l'historique."),
    ("revenue_growth_1y", "financials", "safe_historical", "Compare latest_revenue à prediction_year - 1."),
    ("net_result_change_1y", "financials", "safe_historical", "Compare latest_net_result à prediction_year - 1."),
]


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    if args.install_deps:
        install_deps(repo_dir)

    p = paths(args.drive_root)
    report_dir = p["drive_root"] / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    profile = build_ml_readiness_profile(p["data_lake"], sample_rows=args.sample_rows)

    json_path = report_dir / "ml_readiness_audit.json"
    json_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    outputs = {
        "label_audit.md": render_label_audit(profile),
        "leakage_audit.md": render_leakage_audit(profile),
        "feature_safety_audit.md": render_feature_safety_audit(profile),
    }
    for filename, content in outputs.items():
        path = report_dir / filename
        path.write_text(content, encoding="utf-8")
        print(f"[ml-audit] wrote {path}")
    print(f"[ml-audit] wrote {json_path}")


def build_ml_readiness_profile(data_lake: Path, *, sample_rows: int) -> dict[str, Any]:
    import duckdb

    con = duckdb.connect()
    try:
        register_views(con, data_lake)
        feature_columns = table_columns(con, "features")
        label_columns = table_columns(con, "labels")
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_lake_dir": str(data_lake),
            "datasets": dataset_status(data_lake),
            "label_audit": build_label_audit(con, sample_rows),
            "leakage_audit": build_leakage_audit(con, feature_columns, label_columns),
            "feature_safety_audit": build_feature_safety_audit(feature_columns),
        }
    finally:
        con.close()


def register_views(con: Any, data_lake: Path) -> None:
    create_view(con, "features", data_lake / "features" / "company_year_features")
    create_view(con, "labels", data_lake / "features" / "risk_labels")
    create_view(con, "legal_events", data_lake / "clean" / "legal_events")
    create_view(con, "formalities_events", data_lake / "clean" / "formalities_events")
    create_view(con, "company_identity", data_lake / "clean" / "company_identity")
    create_view(con, "financials", data_lake / "clean" / "financials")
    create_view(con, "annual_accounts", data_lake / "clean" / "annual_accounts")


def create_view(con: Any, name: str, root: Path) -> None:
    if has_parquet(root):
        con.execute(
            f"CREATE OR REPLACE TEMP VIEW {name} AS SELECT * FROM read_parquet('{sql_string(glob(root))}', union_by_name=true)"
        )
        return
    con.execute(f"CREATE OR REPLACE TEMP VIEW {name} AS {empty_view_sql(name)}")


def empty_view_sql(name: str) -> str:
    schemas = {
        "features": """
            SELECT
                NULL::VARCHAR AS siren,
                NULL::INTEGER AS prediction_year,
                NULL::DATE AS prediction_date,
                NULL::INTEGER AS latest_financial_year
            WHERE FALSE
        """,
        "labels": """
            SELECT
                NULL::VARCHAR AS siren,
                NULL::INTEGER AS prediction_year,
                NULL::DATE AS prediction_date,
                NULL::BOOLEAN AS continuity_risk_12m_label,
                NULL::BOOLEAN AS legal_distress_risk_12m_label,
                NULL::BOOLEAN AS radiation_risk_12m_label,
                NULL::BOOLEAN AS financial_weakness_risk_12m_label,
                NULL::BOOLEAN AS filing_anomaly_risk_12m_label,
                NULL::DATE AS first_future_legal_event_date
            WHERE FALSE
        """,
        "legal_events": """
            SELECT
                NULL::VARCHAR AS siren,
                NULL::DATE AS event_date,
                NULL::BOOLEAN AS flag_liquidation,
                NULL::BOOLEAN AS flag_redressement,
                NULL::BOOLEAN AS flag_sauvegarde,
                NULL::BOOLEAN AS flag_procedure_collective,
                NULL::BOOLEAN AS is_radiation
            WHERE FALSE
        """,
        "formalities_events": """
            SELECT
                NULL::VARCHAR AS siren,
                NULL::DATE AS event_date,
                NULL::VARCHAR AS event_type,
                NULL::VARCHAR AS event_text
            WHERE FALSE
        """,
        "company_identity": """
            SELECT
                NULL::VARCHAR AS siren,
                NULL::DATE AS closure_date,
                NULL::VARCHAR AS administrative_status,
                NULL::DATE AS status_period_start
            WHERE FALSE
        """,
        "financials": """
            SELECT
                NULL::VARCHAR AS siren,
                NULL::INTEGER AS financial_year,
                NULL::DOUBLE AS net_result,
                NULL::DOUBLE AS equity
            WHERE FALSE
        """,
        "annual_accounts": """
            SELECT
                NULL::VARCHAR AS siren,
                NULL::DATE AS filing_date
            WHERE FALSE
        """,
    }
    return schemas.get(name, "SELECT 1 AS _empty WHERE FALSE")


def build_label_audit(con: Any, sample_rows: int) -> dict[str, Any]:
    labels_available = has_table_column(con, "labels", "continuity_risk_12m_label")
    if not labels_available:
        return {"available": False, "reason": "risk_labels table or continuity label missing"}

    by_year = query_dicts(
        con,
        """
        SELECT
            prediction_year,
            COUNT(*) AS rows,
            SUM(continuity_risk_12m_label::INTEGER) AS continuity_positive,
            AVG(continuity_risk_12m_label::INTEGER) AS continuity_rate,
            SUM(legal_distress_risk_12m_label::INTEGER) AS legal_distress_positive,
            SUM(radiation_risk_12m_label::INTEGER) AS radiation_positive,
            SUM(financial_weakness_risk_12m_label::INTEGER) AS financial_weakness_positive,
            SUM(filing_anomaly_risk_12m_label::INTEGER) AS filing_anomaly_positive
        FROM labels
        GROUP BY prediction_year
        ORDER BY prediction_year
        """,
    )

    source_breakdown = source_label_breakdown(con)
    event_breakdown = event_label_breakdown(con)
    positive_examples = query_dicts(
        con,
        f"""
        SELECT *
        FROM labels
        WHERE continuity_risk_12m_label = true
        ORDER BY prediction_year, siren
        LIMIT {int(sample_rows)}
        """,
    )
    zero_positive_years = [
        int(row["prediction_year"])
        for row in by_year
        if int(row.get("continuity_positive") or 0) == 0
    ]

    return {
        "available": True,
        "by_year": by_year,
        "source_breakdown": source_breakdown,
        "event_breakdown": event_breakdown,
        "positive_examples": positive_examples,
        "zero_positive_years": zero_positive_years,
        "diagnosis": diagnose_label_distribution(by_year, source_breakdown),
    }


def source_label_breakdown(con: Any) -> list[dict[str, Any]]:
    return query_dicts(
        con,
        """
        WITH base AS (
            SELECT siren, prediction_year, prediction_date FROM labels
        ),
        bodacc AS (
            SELECT
                b.prediction_year,
                COUNT(*) FILTER (
                    WHERE e.event_date > b.prediction_date
                      AND e.event_date <= b.prediction_date + INTERVAL 12 MONTH
                      AND (
                        COALESCE(e.flag_liquidation, false)
                        OR COALESCE(e.flag_redressement, false)
                        OR COALESCE(e.flag_sauvegarde, false)
                        OR COALESCE(e.flag_procedure_collective, false)
                        OR COALESCE(e.is_radiation, false)
                      )
                ) AS bodacc_future_label_events
            FROM base b
            LEFT JOIN legal_events e ON e.siren = b.siren
            GROUP BY b.prediction_year
        ),
        inpi AS (
            SELECT
                b.prediction_year,
                COUNT(*) FILTER (
                    WHERE f.event_date > b.prediction_date
                      AND f.event_date <= b.prediction_date + INTERVAL 12 MONTH
                      AND (
                        lower(COALESCE(f.event_type, '') || ' ' || COALESCE(f.event_text, '')) LIKE '%cessation%'
                        OR lower(COALESCE(f.event_type, '') || ' ' || COALESCE(f.event_text, '')) LIKE '%radiation%'
                        OR lower(COALESCE(f.event_type, '') || ' ' || COALESCE(f.event_text, '')) LIKE '%fermeture%'
                      )
                ) AS inpi_future_label_events
            FROM base b
            LEFT JOIN formalities_events f ON f.siren = b.siren
            GROUP BY b.prediction_year
        ),
        insee AS (
            SELECT
                b.prediction_year,
                COUNT(*) FILTER (
                    WHERE (
                        i.closure_date > b.prediction_date
                        AND i.closure_date <= b.prediction_date + INTERVAL 12 MONTH
                    ) OR (
                        upper(COALESCE(i.administrative_status, '')) IN ('C', 'CESSEE', 'FERMEE', 'INACTIVE')
                        AND i.status_period_start > b.prediction_date
                        AND i.status_period_start <= b.prediction_date + INTERVAL 12 MONTH
                    )
                ) AS insee_future_label_events
            FROM base b
            LEFT JOIN company_identity i ON i.siren = b.siren
            GROUP BY b.prediction_year
        ),
        financial AS (
            SELECT
                b.prediction_year,
                COUNT(*) FILTER (
                    WHERE fin.financial_year = b.prediction_year + 1
                      AND (COALESCE(fin.net_result, 0) < 0 OR COALESCE(fin.equity, 0) < 0)
                ) AS financial_future_label_events
            FROM base b
            LEFT JOIN financials fin ON fin.siren = b.siren
            GROUP BY b.prediction_year
        )
        SELECT
            b.prediction_year,
            COALESCE(bodacc.bodacc_future_label_events, 0) AS bodacc_events,
            COALESCE(inpi.inpi_future_label_events, 0) AS inpi_events,
            COALESCE(insee.insee_future_label_events, 0) AS insee_events,
            COALESCE(financial.financial_future_label_events, 0) AS financial_events
        FROM (SELECT DISTINCT prediction_year FROM base) b
        LEFT JOIN bodacc USING (prediction_year)
        LEFT JOIN inpi USING (prediction_year)
        LEFT JOIN insee USING (prediction_year)
        LEFT JOIN financial USING (prediction_year)
        ORDER BY b.prediction_year
        """,
    )


def event_label_breakdown(con: Any) -> list[dict[str, Any]]:
    return query_dicts(
        con,
        """
        WITH base AS (
            SELECT siren, prediction_year, prediction_date FROM labels
        ),
        events AS (
            SELECT 'liquidation' AS event_family, 'BODACC' AS source, COUNT(*) AS event_count
            FROM base b JOIN legal_events e ON e.siren = b.siren
            WHERE e.event_date > b.prediction_date AND e.event_date <= b.prediction_date + INTERVAL 12 MONTH
              AND COALESCE(e.flag_liquidation, false)
            UNION ALL
            SELECT 'redressement', 'BODACC', COUNT(*)
            FROM base b JOIN legal_events e ON e.siren = b.siren
            WHERE e.event_date > b.prediction_date AND e.event_date <= b.prediction_date + INTERVAL 12 MONTH
              AND COALESCE(e.flag_redressement, false)
            UNION ALL
            SELECT 'sauvegarde', 'BODACC', COUNT(*)
            FROM base b JOIN legal_events e ON e.siren = b.siren
            WHERE e.event_date > b.prediction_date AND e.event_date <= b.prediction_date + INTERVAL 12 MONTH
              AND COALESCE(e.flag_sauvegarde, false)
            UNION ALL
            SELECT 'procedure_collective', 'BODACC', COUNT(*)
            FROM base b JOIN legal_events e ON e.siren = b.siren
            WHERE e.event_date > b.prediction_date AND e.event_date <= b.prediction_date + INTERVAL 12 MONTH
              AND COALESCE(e.flag_procedure_collective, false)
            UNION ALL
            SELECT 'radiation', 'BODACC', COUNT(*)
            FROM base b JOIN legal_events e ON e.siren = b.siren
            WHERE e.event_date > b.prediction_date AND e.event_date <= b.prediction_date + INTERVAL 12 MONTH
              AND COALESCE(e.is_radiation, false)
            UNION ALL
            SELECT 'cessation_radiation_fermeture', 'INPI formalites', COUNT(*)
            FROM base b JOIN formalities_events f ON f.siren = b.siren
            WHERE f.event_date > b.prediction_date AND f.event_date <= b.prediction_date + INTERVAL 12 MONTH
              AND (
                lower(COALESCE(f.event_type, '') || ' ' || COALESCE(f.event_text, '')) LIKE '%cessation%'
                OR lower(COALESCE(f.event_type, '') || ' ' || COALESCE(f.event_text, '')) LIKE '%radiation%'
                OR lower(COALESCE(f.event_type, '') || ' ' || COALESCE(f.event_text, '')) LIKE '%fermeture%'
              )
            UNION ALL
            SELECT 'negative_result_or_equity', 'financials', COUNT(*)
            FROM base b JOIN financials fin ON fin.siren = b.siren
            WHERE fin.financial_year = b.prediction_year + 1
              AND (COALESCE(fin.net_result, 0) < 0 OR COALESCE(fin.equity, 0) < 0)
        )
        SELECT * FROM events ORDER BY source, event_family
        """,
    )


def diagnose_label_distribution(by_year: list[dict[str, Any]], source_breakdown: list[dict[str, Any]]) -> list[str]:
    notes = []
    zero_years = [row["prediction_year"] for row in by_year if int(row.get("continuity_positive") or 0) == 0]
    if zero_years:
        notes.append(
            "Certaines années ont zéro positif continuity_risk_12m_label: "
            + ", ".join(str(year) for year in zero_years)
            + ". Vérifier la présence des événements futurs, le parsing des dates et le mapping des événements."
        )
    for row in source_breakdown:
        total_events = sum(int(row.get(key) or 0) for key in ("bodacc_events", "inpi_events", "insee_events"))
        if total_events == 0:
            notes.append(
                f"Aucun événement futur légal/registre/INSEE détecté pour prediction_year={row['prediction_year']} dans les sources reconstruites."
            )
    if not notes:
        notes.append("La distribution des labels ne présente pas d'année totalement vide pour le label principal.")
    return notes


def build_leakage_audit(con: Any, feature_columns: list[str], label_columns: list[str]) -> dict[str, Any]:
    forbidden_in_features = sorted(set(feature_columns) & FORBIDDEN_MODEL_COLUMNS)
    label_date_violations = scalar(
        con,
        """
        SELECT COUNT(*)
        FROM labels
        WHERE first_future_legal_event_date IS NOT NULL
          AND (
            first_future_legal_event_date <= prediction_date
            OR first_future_legal_event_date > prediction_date + INTERVAL 12 MONTH
          )
        """,
    ) if "first_future_legal_event_date" in label_columns else None
    financial_future_violations = scalar(
        con,
        """
        SELECT COUNT(*)
        FROM features
        WHERE latest_financial_year IS NOT NULL
          AND latest_financial_year > prediction_year
        """,
    ) if "latest_financial_year" in feature_columns else None

    checks = [
        check("Forbidden columns absent from feature table", not forbidden_in_features, {"forbidden_found": forbidden_in_features}),
        check("Target columns are stored outside feature table", not (set(LABEL_COLUMNS) & set(feature_columns)), {}),
        check("first_future_legal_event_date not in feature table", "first_future_legal_event_date" not in feature_columns, {}),
        check("siren excluded by training tool", "siren" in feature_columns, {"note": "siren exists for joins but is excluded by train_continuity_model.EXCLUDE_COLUMNS"}),
        check("Future legal label dates inside 12-month window", label_date_violations == 0, {"violations": label_date_violations}),
        check("Financial feature years not after prediction year", financial_future_violations == 0, {"violations": financial_future_violations}),
    ]
    return {"checks": checks, "overall_pass": all(item["ok"] for item in checks)}


def build_feature_safety_audit(feature_columns: list[str]) -> dict[str, Any]:
    existing = set(feature_columns)
    rows = []
    for feature, source, status, note in FEATURE_SAFETY:
        rows.append(
            {
                "feature": feature,
                "source": source,
                "status": status if feature in existing else "not_present",
                "present": feature in existing,
                "note": note,
            }
        )
    undocumented = sorted(existing - {row[0] for row in FEATURE_SAFETY})
    return {
        "features": rows,
        "undocumented_feature_columns": undocumented,
        "needs_verification": [row for row in rows if row["status"] == "needs_verification"],
    }


def dataset_status(data_lake: Path) -> dict[str, dict[str, Any]]:
    roots = {
        "company_year_features": data_lake / "features" / "company_year_features",
        "risk_labels": data_lake / "features" / "risk_labels",
        "company_identity": data_lake / "clean" / "company_identity",
        "legal_events": data_lake / "clean" / "legal_events",
        "formalities_events": data_lake / "clean" / "formalities_events",
        "annual_accounts": data_lake / "clean" / "annual_accounts",
        "financials": data_lake / "clean" / "financials",
    }
    return {
        name: {"path": str(root), "available": has_parquet(root), "parquet_files": len(list(root.rglob("*.parquet"))) if root.exists() else 0}
        for name, root in roots.items()
    }


def render_label_audit(profile: dict[str, Any]) -> str:
    audit = profile["label_audit"]
    lines = header("Label Audit", profile)
    lines.extend(
        [
            "## Objectif",
            "",
            "Ce rapport vérifie la distribution des labels futurs et cherche à expliquer les années avec peu ou zéro positifs.",
            "",
        ]
    )
    if not audit["available"]:
        lines.append(f"**Audit indisponible:** {audit['reason']}")
        return "\n".join(lines) + "\n"
    lines.extend(["## Labels Positifs Par Année", "", markdown_table(audit["by_year"]), ""])
    lines.extend(["## Événements Futurs Par Source", "", markdown_table(audit["source_breakdown"]), ""])
    lines.extend(["## Événements Utilisés Comme Labels Par Type", "", markdown_table(audit["event_breakdown"]), ""])
    lines.extend(["## Diagnostic", ""])
    lines.extend(f"- {note}" for note in audit["diagnosis"])
    lines.extend(["", "## Exemples De Labels Positifs", "", json_block(audit["positive_examples"])])
    return "\n".join(lines) + "\n"


def render_leakage_audit(profile: dict[str, Any]) -> str:
    audit = profile["leakage_audit"]
    lines = header("Leakage Audit", profile)
    lines.extend(
        [
            "## Objectif",
            "",
            "Ce rapport vérifie les principaux risques de fuite temporelle ou de fuite de target dans les entrées du modèle.",
            "",
            f"**Résultat global:** {'PASS' if audit['overall_pass'] else 'FAIL'}",
            "",
            "## Checks",
            "",
            markdown_table(audit["checks"]),
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def render_feature_safety_audit(profile: dict[str, Any]) -> str:
    audit = profile["feature_safety_audit"]
    lines = header("Feature Safety Audit", profile)
    lines.extend(
        [
            "## Objectif",
            "",
            "Ce rapport classe chaque feature selon son niveau de sécurité historique et indique les champs qui nécessitent une vérification.",
            "",
            "## Registre Des Features",
            "",
            markdown_table(audit["features"]),
            "",
            "## Features À Vérifier",
            "",
            markdown_table(audit["needs_verification"]) if audit["needs_verification"] else "Aucune feature présente n'est marquée needs_verification.",
            "",
            "## Colonnes Non Documentées",
            "",
            json_block(audit["undocumented_feature_columns"]),
        ]
    )
    return "\n".join(lines) + "\n"


def header(title: str, profile: dict[str, Any]) -> list[str]:
    return [
        f"# {title}",
        "",
        f"| Élément | Valeur |",
        "|---|---|",
        f"| Généré le | `{profile['generated_at']}` |",
        f"| Data lake | `{profile['data_lake_dir']}` |",
        "",
    ]


def check(name: str, ok: bool, details: dict[str, Any]) -> dict[str, Any]:
    return {"check": name, "ok": bool(ok), "result": "PASS" if ok else "FAIL", "details": details}


def table_columns(con: Any, table: str) -> list[str]:
    try:
        return [str(row[0]) for row in con.execute(f"DESCRIBE SELECT * FROM {table}").fetchall()]
    except Exception:
        return []


def has_table_column(con: Any, table: str, column: str) -> bool:
    return column in table_columns(con, table)


def query_dicts(con: Any, sql: str) -> list[dict[str, Any]]:
    rows = con.execute(sql).fetchall()
    columns = [desc[0] for desc in con.description]
    return [dict(zip(columns, row)) for row in rows]


def scalar(con: Any, sql: str) -> int:
    return int(con.execute(sql).fetchone()[0] or 0)


def markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_Aucune ligne._"
    columns = list(rows[0].keys())
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(format_cell(row.get(column)) for column in columns) + " |")
    return "\n".join(lines)


def format_cell(value: Any) -> str:
    if isinstance(value, dict):
        return "`" + json.dumps(value, ensure_ascii=False, default=str) + "`"
    if isinstance(value, float):
        return f"{value:.6g}"
    if value is None:
        return ""
    return str(value).replace("|", "\\|")


def json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n```"


def has_parquet(root: Path) -> bool:
    return root.exists() and any(root.rglob("*.parquet"))


def glob(root: Path) -> str:
    return str(root / "**" / "*.parquet").replace("\\", "/")


def sql_string(value: str) -> str:
    return value.replace("'", "''")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ML label, leakage, and feature safety audits.")
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--sample-rows", type=int, default=20)
    return parser.parse_args()


if __name__ == "__main__":
    main()
