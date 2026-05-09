# Feature Safety Registry

## Purpose

This registry classifies the main feature and label columns by historical safety
and leakage risk. It is a defensive document: when a future contributor or AI
assistant proposes a feature, it should be checked against this registry before
training.

## Rules

| Rule | Meaning |
|---|---|
| `allowed_as_feature` | The field may be used as a model input if cutoff logic is respected |
| `allowed_as_label` | The field may be used to construct a target label |
| `requires_cutoff_filter` | The field is only valid if its source date is `<= prediction_date` |
| `historical_safe` | The value can represent the prediction year without using future knowledge |
| `leakage_risk` | Risk level if the field is used incorrectly |

## Registry

| Column / Family | Source | Allowed As Feature | Allowed As Label | Requires Cutoff | Historical Safe | Leakage Risk | Notes |
|---|---|---:|---:|---:|---:|---|---|
| `siren` | All | no | no | no | yes | high | Join key only; exclude from model inputs |
| `prediction_date` | Feature builder | no | no | no | yes | high | Cutoff metadata, not a feature |
| `prediction_year` | Feature builder | yes | no | no | yes | medium | Useful for temporal effects, but monitor drift |
| `company_age_years` | INSEE | yes | no | yes | yes | low | Derived from creation date and prediction date |
| `activity_code` | INSEE | yes | no | yes | conditional | medium | Safe only if period-aware or accepted as latest-known context |
| `legal_category_code` | INSEE | yes | no | yes | conditional | medium | Legal category can change; document assumptions |
| `administrative_status_at_cutoff` | INSEE | yes | no | yes | conditional | high | Dangerous if sourced from current-only snapshot |
| `closure_date` / `date_cessation` | INSEE | no | yes | yes | no | high | Future closure is label information |
| `legal_events_count_*` | BODACC | yes | no | yes | yes | medium | Counts must include only events before cutoff |
| `legal_risk_events_count_*` | BODACC | yes | no | yes | yes | medium | Past risk history only |
| `legal_distress_events_count_all` | BODACC | yes | no | yes | yes | medium | Past distress can indicate history; future distress is label |
| `radiation_events_count_all` | BODACC | yes | no | yes | yes | high | Past only; future radiation is label |
| `days_since_last_legal_event` | BODACC | yes | no | yes | yes | medium | Must be computed relative to `prediction_date` |
| `formalities_count_*` | INPI | yes | no | yes | yes | medium | Past registry activity only |
| `cessation_formalities_count_all` | INPI | yes | no | yes | yes | high | Past only; future cessation contributes to label |
| `annual_accounts_count_*` | INPI | yes | no | yes | yes | low | Filing behavior feature |
| `days_since_last_account_filing` | INPI | yes | no | yes | yes | medium | Computed relative to `prediction_date` |
| `latest_account_closing_year` | INPI | yes | no | yes | yes | low | Must be `<= prediction_year` |
| `latest_revenue`, `latest_net_result`, `latest_equity`, `latest_debt` | Financials | yes | no | yes | yes | medium | Use only financial years available at cutoff |
| `has_financial_data` | Financials | yes | no | yes | yes | low | Separates missing source coverage from financial weakness |
| `financial_years_available` | Financials | yes | no | yes | yes | low | Measures observed financial history |
| `years_since_last_financial_statement` | Financials | yes | no | yes | yes | low | Missingness/recency feature |
| `has_confidential_financials` | Financials | yes | no | yes | yes | low | Helps avoid punishing confidential filings as weakness |
| `continuity_risk_12m_label` | Labels | no | yes | future-only | yes | high | Primary target |
| `legal_distress_risk_12m_label` | Labels | no | yes | future-only | yes | high | Secondary target |
| `radiation_risk_12m_label` | Labels | no | yes | future-only | yes | high | Secondary target |
| `financial_weakness_risk_12m_label` | Labels | no | yes | future-only | yes | high | Secondary target |
| `filing_anomaly_risk_12m_label` | Labels | no | yes | future-only | yes | high | Secondary target |
| `first_future_legal_event_date` | Labels | no | yes | future-only | yes | high | Audit/explanation metadata, never model input |

## Report Summary

The safest first model uses interpretable, cutoff-safe counts, recency variables,
financial values available at cutoff, and missingness indicators. Direct future
event fields, label columns, raw source paths, long text, and identifiers must be
excluded from training.
