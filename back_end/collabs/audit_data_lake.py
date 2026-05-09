from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import DEFAULT_DRIVE_ROOT, install_deps, paths


DATASETS = {
    "raw_insee": "raw/insee",
    "raw_financials": "raw/financials",
    "raw_inpi": "raw/inpi",
    "raw_bodacc": "raw/bodacc",
    "clean_company_identity": "clean/company_identity",
    "clean_financials": "clean/financials",
    "clean_legal_events": "clean/legal_events",
    "clean_formalities_events": "clean/formalities_events",
    "clean_annual_accounts": "clean/annual_accounts",
    "features_company_year": "features/company_year_features",
    "features_risk_labels": "features/risk_labels",
    "features_company": "features/company_features",
}

IMPORTANT_COLUMNS = {
    "siren",
    "prediction_year",
    "prediction_date",
    "event_date",
    "date_parution",
    "date_depot",
    "date_cloture",
    "closing_date",
    "filing_date",
    "financial_year",
    "revenue",
    "net_result",
    "equity",
    "debt",
    "total_assets",
    "activity_code",
    "legal_category_code",
    "administrative_status",
    "company_age_years",
    "legal_events_count_12m",
    "legal_distress_events_count_all",
    "radiation_events_count_all",
    "annual_accounts_count_24m",
    "days_since_last_account_filing",
    "continuity_risk_12m_label",
    "legal_distress_risk_12m_label",
    "radiation_risk_12m_label",
    "financial_weakness_risk_12m_label",
    "filing_anomaly_risk_12m_label",
    "has_financial_data",
    "financial_years_available",
    "latest_financial_year",
    "years_since_last_financial_statement",
    "has_confidential_financials",
}

EXACT_DISTINCT_ROW_LIMIT = 5_000_000


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    if args.install_deps:
        install_deps(repo_dir)

    p = paths(args.drive_root)
    data_lake = p["data_lake"]
    report_dir = p["drive_root"] / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    profile = audit_data_lake(
        data_lake,
        sample_rows=args.sample_rows,
        max_columns=args.max_columns,
        max_categories=args.max_categories,
    )
    json_path = Path(args.output_json) if args.output_json else report_dir / "data_lake_audit.json"
    md_path = Path(args.output_md) if args.output_md else report_dir / "data_lake_audit.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(profile), encoding="utf-8")
    print(f"[audit] wrote JSON: {json_path}")
    print(f"[audit] wrote Markdown: {md_path}")


def audit_data_lake(
    data_lake: Path,
    *,
    sample_rows: int,
    max_columns: int,
    max_categories: int,
) -> dict[str, Any]:
    import duckdb

    con = duckdb.connect()
    try:
        datasets = {}
        for name, rel in DATASETS.items():
            root = data_lake / rel
            datasets[name] = profile_dataset(
                con,
                name=name,
                root=root,
                sample_rows=sample_rows,
                max_columns=max_columns,
                max_categories=max_categories,
            )
        quality_checks = build_quality_checks(con, datasets)
        readiness = build_readiness(datasets)
        insights = build_insights(datasets)
        return {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "data_lake_dir": str(data_lake),
            "datasets": datasets,
            "quality_checks": quality_checks,
            "readiness": readiness,
            "insights": insights,
        }
    finally:
        con.close()


def profile_dataset(
    con: Any,
    *,
    name: str,
    root: Path,
    sample_rows: int,
    max_columns: int,
    max_categories: int,
) -> dict[str, Any]:
    files = sorted(root.rglob("*.parquet")) if root.exists() else []
    manifest = read_json(root / "_manifest.json")
    if not files:
        return {
            "exists": False,
            "root": str(root),
            "parquet_files": 0,
            "manifest": manifest,
            "rows": 0,
            "columns": [],
            "column_profile": {},
            "sample_rows": [],
        }

    sql = read_parquet_sql(root)
    rows = int(con.execute(f"SELECT COUNT(*) FROM {sql}").fetchone()[0] or 0)
    describe_rows = con.execute(f"DESCRIBE SELECT * FROM {sql}").fetchall()
    columns = [{"name": str(row[0]), "type": str(row[1])} for row in describe_rows]
    selected = select_profile_columns(columns, max_columns=max_columns)
    column_profile = {
        column["name"]: profile_column(con, sql, column["name"], column["type"], rows, max_categories=max_categories)
        for column in selected
    }
    sample = sample_rows_for_report(con, sql, selected, sample_rows)
    return {
        "exists": True,
        "root": str(root),
        "parquet_files": len(files),
        "manifest": manifest,
        "rows": rows,
        "columns": columns,
        "column_profile": column_profile,
        "sample_rows": sample,
    }


def profile_column(con: Any, sql: str, column: str, dtype: str, rows: int, *, max_categories: int) -> dict[str, Any]:
    ident = quote_ident(column)
    dtype_upper = dtype.upper()
    if is_complex_type(dtype_upper):
        nulls_row = con.execute(
            f"SELECT SUM(CASE WHEN {ident} IS NULL THEN 1 ELSE 0 END) AS nulls FROM {sql}"
        ).fetchone()
        nulls = int(nulls_row[0] or 0)
        return {
            "type": dtype,
            "nulls": nulls,
            "coverage_rate": round((rows - nulls) / rows, 6) if rows else None,
            "distinct_values": None,
            "summary": "complex column; coverage only",
        }

    distinct_expr = (
        f"COUNT(DISTINCT {ident})"
        if rows <= EXACT_DISTINCT_ROW_LIMIT
        else f"APPROX_COUNT_DISTINCT({ident})"
    )
    base = con.execute(
        f"""
        SELECT
          SUM(CASE WHEN {ident} IS NULL THEN 1 ELSE 0 END) AS nulls,
          {distinct_expr} AS distinct_values
        FROM {sql}
        """
    ).fetchone()
    nulls = int(base[0] or 0)
    profile: dict[str, Any] = {
        "type": dtype,
        "nulls": nulls,
        "coverage_rate": round((rows - nulls) / rows, 6) if rows else None,
        "distinct_values": int(base[1] or 0),
        "distinct_is_approximate": rows > EXACT_DISTINCT_ROW_LIMIT,
    }
    if is_numeric_type(dtype_upper):
        stats = con.execute(
            f"SELECT MIN({ident}), MAX({ident}), AVG(CAST({ident} AS DOUBLE)) FROM {sql}"
        ).fetchone()
        profile.update({"min": stats[0], "max": stats[1], "avg": stats[2]})
    elif is_temporal_type(dtype_upper):
        stats = con.execute(f"SELECT MIN({ident}), MAX({ident}) FROM {sql}").fetchone()
        profile.update({"min": stats[0], "max": stats[1]})
    elif profile["distinct_values"] <= max_categories:
        values = con.execute(
            f"""
            SELECT CAST({ident} AS VARCHAR) AS value, COUNT(*) AS rows
            FROM {sql}
            WHERE {ident} IS NOT NULL
            GROUP BY {ident}
            ORDER BY rows DESC
            LIMIT {int(max_categories)}
            """
        ).fetchall()
        profile["top_values"] = [{"value": row[0], "rows": int(row[1])} for row in values]
    return profile


def sample_rows_for_report(con: Any, sql: str, columns: list[dict[str, str]], sample_rows: int) -> list[dict[str, Any]]:
    if sample_rows <= 0 or not columns:
        return []
    select_parts = []
    for column in columns:
        ident = quote_ident(column["name"])
        alias = quote_ident(column["name"])
        if is_complex_type(column["type"].upper()):
            select_parts.append(f"CAST({ident} AS VARCHAR) AS {alias}")
        else:
            select_parts.append(f"{ident} AS {alias}")
    return (
        con.execute(f"SELECT {', '.join(select_parts)} FROM {sql} LIMIT {int(sample_rows)}")
        .fetchdf()
        .to_dict(orient="records")
    )


def is_complex_type(dtype_upper: str) -> bool:
    normalized = dtype_upper.strip()
    return (
        normalized.startswith(("MAP", "STRUCT", "LIST", "UNION", "ARRAY"))
        or "[]" in normalized
        or any(token in normalized for token in (" MAP(", " STRUCT(", " LIST(", " UNION(", " ARRAY("))
    )


def is_numeric_type(dtype_upper: str) -> bool:
    normalized = dtype_upper.split("(", 1)[0].strip()
    return normalized in {
        "TINYINT",
        "SMALLINT",
        "INTEGER",
        "BIGINT",
        "HUGEINT",
        "UTINYINT",
        "USMALLINT",
        "UINTEGER",
        "UBIGINT",
        "FLOAT",
        "DOUBLE",
        "REAL",
        "DECIMAL",
    }


def is_temporal_type(dtype_upper: str) -> bool:
    normalized = dtype_upper.split("(", 1)[0].strip()
    return normalized in {"DATE", "TIME", "TIMESTAMP", "TIMESTAMP WITH TIME ZONE"}


def select_profile_columns(columns: list[dict[str, str]], *, max_columns: int) -> list[dict[str, str]]:
    by_name = {col["name"]: col for col in columns}
    selected = [by_name[name] for name in sorted(IMPORTANT_COLUMNS) if name in by_name]
    for col in columns:
        if len(selected) >= max_columns:
            break
        if col not in selected and not is_complex_type(col["type"].upper()):
            selected.append(col)
    return selected[:max_columns]


def build_insights(datasets: dict[str, Any]) -> list[str]:
    insights: list[str] = []
    for name, dataset in datasets.items():
        if not dataset["exists"]:
            insights.append(f"{name}: missing; no feature or quality conclusion can be drawn yet.")
            continue
        rows = dataset["rows"]
        insights.append(f"{name}: available with {rows:,} rows and {len(dataset['columns'])} columns.")
        siren = dataset["column_profile"].get("siren")
        if siren:
            insights.append(f"{name}: siren coverage is {siren['coverage_rate']}; this controls join reliability.")
        for label in (
            "continuity_risk_12m_label",
            "legal_distress_risk_12m_label",
            "radiation_risk_12m_label",
        ):
            prof = dataset["column_profile"].get(label)
            if prof:
                insights.append(f"{name}: {label} coverage is {prof['coverage_rate']}.")
    return insights


def build_readiness(datasets: dict[str, Any]) -> dict[str, Any]:
    checks = []

    def add(name: str, ok: bool, summary: str) -> None:
        checks.append({"name": name, "ok": ok, "summary": summary})

    add(
        "insee_raw",
        datasets["raw_insee"]["exists"] and datasets["raw_insee"]["rows"] > 0,
        "INSEE raw data is required for company identity and administrative status.",
    )
    add(
        "financials",
        (datasets["raw_financials"]["exists"] or datasets["clean_financials"]["exists"])
        and (datasets["raw_financials"]["rows"] > 0 or datasets["clean_financials"]["rows"] > 0),
        "Financial raw or clean data is required for accounting features.",
    )
    add(
        "bodacc",
        datasets["raw_bodacc"]["exists"] and datasets["raw_bodacc"]["rows"] > 0,
        "BODACC raw data is required for legal distress and radiation labels.",
    )
    add(
        "features",
        datasets["features_company_year"]["exists"] and datasets["features_risk_labels"]["exists"],
        "Feature and label tables are required before training.",
    )

    labels = datasets["features_risk_labels"]
    label_profile = labels.get("column_profile", {}) if labels["exists"] else {}
    add(
        "continuity_label_column",
        "continuity_risk_12m_label" in label_profile,
        "The primary continuity-risk label must exist.",
    )

    blockers = [check for check in checks if not check["ok"]]
    return {
        "training_ready": not blockers,
        "checks": checks,
        "blockers": blockers,
    }


def build_quality_checks(con: Any, datasets: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    features = datasets["features_company_year"]
    labels = datasets["features_risk_labels"]
    if features["exists"]:
        sql = read_parquet_sql(Path(features["root"]))
        checks["feature_duplicate_company_year"] = duplicate_key_check(con, sql, ("siren", "prediction_year"))
        checks["feature_siren_quality"] = siren_quality_check(con, sql)
    if labels["exists"]:
        sql = read_parquet_sql(Path(labels["root"]))
        checks["label_duplicate_company_year"] = duplicate_key_check(con, sql, ("siren", "prediction_year"))
        checks["label_balance_by_year"] = label_balance_by_year(con, sql)
        checks["label_siren_quality"] = siren_quality_check(con, sql)
    return checks


def duplicate_key_check(con: Any, sql: str, columns: tuple[str, ...]) -> dict[str, Any]:
    available = {str(row[0]) for row in con.execute(f"DESCRIBE SELECT * FROM {sql}").fetchall()}
    missing = [column for column in columns if column not in available]
    if missing:
        return {"key": list(columns), "ok": False, "reason": f"missing key columns: {', '.join(missing)}"}
    key_expr = ", ".join(quote_ident(col) for col in columns)
    row = con.execute(
        f"""
        WITH grouped AS (
            SELECT {key_expr}, COUNT(*) AS rows
            FROM {sql}
            GROUP BY {key_expr}
            HAVING COUNT(*) > 1
        )
        SELECT COUNT(*) AS duplicate_keys, COALESCE(SUM(rows), 0) AS duplicate_rows
        FROM grouped
        """
    ).fetchone()
    return {
        "key": list(columns),
        "duplicate_keys": int(row[0] or 0),
        "duplicate_rows": int(row[1] or 0),
        "ok": int(row[0] or 0) == 0,
    }


def siren_quality_check(con: Any, sql: str) -> dict[str, Any]:
    columns = {str(row[0]) for row in con.execute(f"DESCRIBE SELECT * FROM {sql}").fetchall()}
    if "siren" not in columns:
        return {"ok": False, "reason": "missing siren column"}
    row = con.execute(
        f"""
        SELECT
            COUNT(*) AS rows,
            SUM(CASE WHEN regexp_matches(CAST(siren AS VARCHAR), '^[0-9]{{9}}$') THEN 1 ELSE 0 END) AS valid_siren,
            SUM(CASE WHEN siren IS NULL THEN 1 ELSE 0 END) AS null_siren
        FROM {sql}
        """
    ).fetchone()
    rows = int(row[0] or 0)
    valid = int(row[1] or 0)
    return {
        "rows": rows,
        "valid_siren": valid,
        "null_siren": int(row[2] or 0),
        "valid_rate": round(valid / rows, 6) if rows else None,
        "ok": rows > 0 and valid == rows,
    }


def label_balance_by_year(con: Any, sql: str) -> list[dict[str, Any]]:
    columns = {str(row[0]) for row in con.execute(f"DESCRIBE SELECT * FROM {sql}").fetchall()}
    labels = [
        "continuity_risk_12m_label",
        "legal_distress_risk_12m_label",
        "radiation_risk_12m_label",
        "financial_weakness_risk_12m_label",
        "filing_anomaly_risk_12m_label",
    ]
    selected = [label for label in labels if label in columns]
    if "prediction_year" not in columns or not selected:
        return []
    select_parts = ["prediction_year", "COUNT(*) AS rows"]
    for label in selected:
        ident = quote_ident(label)
        select_parts.append(
            f"SUM(CASE WHEN COALESCE(TRY_CAST({ident} AS BOOLEAN), false) THEN 1 ELSE 0 END) "
            f"AS {quote_ident(label + '_positive')}"
        )
    rows = con.execute(
        f"""
        SELECT {", ".join(select_parts)}
        FROM {sql}
        GROUP BY prediction_year
        ORDER BY prediction_year
        """
    ).fetchall()
    result = []
    for row in rows:
        item = {"prediction_year": int(row[0]), "rows": int(row[1] or 0)}
        for index, label in enumerate(selected, start=2):
            positives = int(row[index] or 0)
            item[f"{label}_positive"] = positives
            item[f"{label}_rate"] = round(positives / item["rows"], 6) if item["rows"] else None
        result.append(item)
    return result


def render_markdown(profile: dict[str, Any]) -> str:
    total_rows = sum(dataset["rows"] for dataset in profile["datasets"].values())
    available = sum(1 for dataset in profile["datasets"].values() if dataset["exists"])
    missing = len(profile["datasets"]) - available
    blockers = profile["readiness"]["blockers"]
    lines = [
        "# Data Lake Audit Report",
        "",
        "> This report is generated automatically from the Parquet data lake. It is intended to support data validation, feature selection, and the decision to train or postpone model training.",
        "",
        "## Executive View",
        "",
        "| Item | Value |",
        "|---|---:|",
        f"| Generated at | `{profile['generated_at']}` |",
        f"| Data lake | `{profile['data_lake_dir']}` |",
        f"| Datasets available | {available} / {len(profile['datasets'])} |",
        f"| Datasets missing | {missing} |",
        f"| Total profiled rows | {total_rows:,} |",
        f"| Training ready | **{'yes' if profile['readiness']['training_ready'] else 'no'}** |",
        "",
        "## Purpose",
        "",
        "This report profiles raw, clean, and feature Parquet datasets before final model training. "
        "It is used to understand schema coverage, missingness, date ranges, join quality, and "
        "which columns are reliable enough to become model features.",
        "",
        "## Readiness Gate",
        "",
        decision_sentence(profile["readiness"]["training_ready"]),
        "",
        "| Check | OK | Meaning |",
        "|---|---:|---|",
    ]
    for check in profile["readiness"]["checks"]:
        lines.append(f"| `{check['name']}` | {status_text(check['ok'])} | {check['summary']} |")
    if blockers:
        lines.extend(["", "### Current Blockers", ""])
        for blocker in blockers:
            lines.append(f"- `{blocker['name']}`: {blocker['summary']}")
    lines.extend(render_quality_section(profile.get("quality_checks", {})))
    lines.extend([
        "",
        "## Dataset Summary",
        "",
        "| Dataset | Status | Rows | Files | Columns | Main Role |",
        "|---|---:|---:|---:|---:|---|",
    ])
    for name, dataset in profile["datasets"].items():
        lines.append(
            f"| `{name}` | {dataset_status(dataset)} | {dataset['rows']:,} | "
            f"{dataset['parquet_files']} | {len(dataset['columns'])} | {dataset_role(name)} |"
        )

    for name, dataset in profile["datasets"].items():
        lines.extend(["", f"## {name}", ""])
        if not dataset["exists"]:
            lines.append("**Status:** missing. No files were found for this dataset.")
            continue
        lines.extend(
            [
                f"**Path:** `{dataset['root']}`",
                "",
                f"**Rows:** {dataset['rows']:,}",
                "",
                f"**Files:** {dataset['parquet_files']}",
                "",
                "### Column Coverage",
                "",
                "| Column | Type | Coverage | Distinct | Min | Max | Avg |",
                "|---|---|---:|---:|---|---|---:|",
            ]
        )
        for column, stats in dataset["column_profile"].items():
            lines.append(
                f"| `{column}` | `{stats['type']}` | {stats.get('coverage_rate')} | "
                f"{stats.get('distinct_values')} | {fmt(stats.get('min'))} | "
                f"{fmt(stats.get('max'))} | {fmt(stats.get('avg'))} |"
            )
        if dataset["sample_rows"]:
            lines.extend(["", "### Sample Rows", "", "```json"])
            lines.append(json.dumps(dataset["sample_rows"][:3], ensure_ascii=False, indent=2, default=str))
            lines.append("```")

    lines.extend(["", "## Initial Insights", ""])
    for insight in profile["insights"]:
        lines.append(f"- {insight}")
    lines.extend(["", "## Recommendations", ""])
    lines.extend(recommendations(profile))
    lines.extend(
        [
            "",
            "## How This Improves Feature Selection",
            "",
            "Columns with high coverage and clear temporal meaning are stronger candidates for the first model. "
            "Columns with weak coverage may still be useful, but they should be transformed into robust features "
            "such as missingness indicators, counts, recency variables, or source-availability flags. Raw source "
            "lineage columns should remain available for auditability but should not be used directly as model inputs.",
            "",
        ]
    )
    return "\n".join(lines)


def render_quality_section(checks: dict[str, Any]) -> list[str]:
    lines = ["", "## Quality Checks", ""]
    if not checks:
        lines.append("No feature or label quality checks were available yet.")
        return lines
    for name, check in checks.items():
        if name == "label_balance_by_year":
            lines.extend(["", "### Label Balance By Year", ""])
            if not check:
                lines.append("Label balance could not be computed.")
                continue
            headers = list(check[0].keys())
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join("---" for _ in headers) + "|")
            for row in check:
                lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
            continue
        ok = check.get("ok")
        lines.append(f"- `{name}`: {status_text(bool(ok))} `{json.dumps(check, ensure_ascii=False, default=str)}`")
    return lines


def decision_sentence(training_ready: bool) -> str:
    if training_ready:
        return "**Decision:** the audited data lake passes the basic readiness gate for a baseline training run."
    return "**Decision:** training should wait. The data lake still has blockers that should be resolved or explicitly accepted before model training."


def status_text(ok: bool) -> str:
    return "**pass**" if ok else "**blocker**"


def dataset_status(dataset: dict[str, Any]) -> str:
    if not dataset["exists"]:
        return "**missing**"
    if dataset["rows"] == 0:
        return "**empty**"
    return "**available**"


def dataset_role(name: str) -> str:
    roles = {
        "raw_insee": "identity source",
        "raw_financials": "financial source",
        "raw_inpi": "registry source",
        "raw_bodacc": "legal event source",
        "clean_company_identity": "normalized identity",
        "clean_financials": "normalized financials",
        "clean_legal_events": "normalized legal events",
        "clean_formalities_events": "normalized registry events",
        "clean_annual_accounts": "normalized filings",
        "features_company_year": "model features",
        "features_risk_labels": "model labels",
        "features_company": "latest company snapshot",
    }
    return roles.get(name, "")


def recommendations(profile: dict[str, Any]) -> list[str]:
    items: list[str] = []
    datasets = profile["datasets"]
    readiness = profile["readiness"]
    if not readiness["training_ready"]:
        items.append("- Do not train the final model yet; resolve or document the blockers above first.")
    if datasets["clean_company_identity"]["exists"] is False and datasets["raw_insee"]["exists"]:
        items.append("- Rebuild clean core sources so raw INSEE bulk data becomes `clean/company_identity`.")
    if datasets["raw_bodacc"]["exists"] is False:
        items.append("- Add BODACC historical `PCL` and `RCS-B` archives to improve legal distress and radiation labels.")
    if datasets["raw_inpi"]["exists"] is False:
        items.append("- Add INPI formalities and annual accounts to improve registry activity and filing-behavior features.")
    if datasets["features_company_year"]["exists"]:
        items.append("- Review high-coverage feature columns first; sparse columns should become missingness or recency features before model use.")
    if not items:
        items.append("- The basic audit is healthy. Proceed to deeper validation: target balance, temporal split, leakage review, and baseline training.")
    return items


def read_parquet_sql(root: Path) -> str:
    pattern = str(root / "**" / "*.parquet").replace("\\", "/").replace("'", "''")
    return f"read_parquet('{pattern}', union_by_name=true)"


def quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile Colab data-lake datasets and write JSON/Markdown reports.")
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    parser.add_argument("--sample-rows", type=int, default=5)
    parser.add_argument("--max-columns", type=int, default=40)
    parser.add_argument("--max-categories", type=int, default=20)
    return parser.parse_args()


if __name__ == "__main__":
    main()
