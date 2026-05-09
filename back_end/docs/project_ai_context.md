# Project AI Context And Decision Memory

## Purpose

This file is a compact knowledge-base entry for future discussions with Codex,
another AI assistant, supervisors, or teammates. It summarizes the project logic,
current risk posture, and the non-negotiable rules that should guide future
implementation.

## Project Identity

The project is a French company intelligence and continuity-risk platform. It
combines INSEE, INPI/RNE, BODACC, and financial data to build:

- a reproducible data lake;
- clean company and event tables;
- company-year ML features;
- 12-month continuity-risk labels;
- future MongoDB serving documents for the API/frontend.

The system architecture is:

```text
source archives -> raw Parquet -> clean Parquet -> feature Parquet -> MongoDB serving -> FastAPI/frontend
```

## Current Strategic Position

The project is strong as a data platform. The ML part must be defended carefully
because final predictive value depends on historical correctness, leakage
prevention, source completeness, and validation metrics.

The most important framing is:

```text
Do not train or defend final model performance until the feature dataset is
complete, historically valid, and leakage-checked.
```

## Non-Negotiable ML Rules

| Rule | Meaning |
|---|---|
| Prediction rows are company-year rows | One row per `(siren, prediction_year)` |
| Feature cutoff is mandatory | Features must use data available at or before `prediction_date` |
| Labels are future-only | Labels use events after `prediction_date` and within the horizon |
| No identifier memorization | `siren` is a join key, not a model feature |
| No future event columns in training | Future dates, label columns, and target columns must be excluded |
| Temporal validation comes first | Main validation should train on older years and test on the latest year |
| Missing financial data is not automatically bad | Missingness must be represented explicitly |
| Metrics must match risk use | Report PR-AUC, recall/precision, top-K capture, and calibration, not accuracy only |
| Explanations must be evidence-grounded | Do not let generated text invent reasons not supported by features/source evidence |

## Highest-Risk Weak Points

| Risk | Current Mitigation Direction |
|---|---|
| Fake historical reconstruction from current snapshots | Classify features as historical-safe or current-only |
| Data leakage from future events | Maintain forbidden columns and feature safety registry |
| Incomplete BODACC/INPI source coverage | Block final training until coverage/audit passes |
| Ambiguous broad target | Keep global continuity score plus secondary risk labels |
| Financial missingness ambiguity | Add `has_financial_data`, recency, availability, and confidentiality features |
| Random split inflation | Prefer temporal split and document company overlap risk |
| Weak explainability | Ground explanations in model features and source evidence |
| Source freshness ambiguity | Track source-level update dates and profile completeness |
| Vague serving model | Keep MongoDB documents compact and frontend-oriented |
| Weak comparison to existing platforms | Emphasize that the project adds temporal ML risk prediction, not only company display |

## Current Implementation Priorities

1. Keep improving the Colab pipeline so source download, export, clean, feature,
   audit, and later training can run reproducibly.
2. Use the audit report before training to inspect source coverage, column
   missingness, duplicate company-year rows, and label balance by year.
3. Add or maintain feature safety documentation so future contributors know which
   fields are valid model inputs.
4. Treat the baseline logistic-regression model as a validation baseline, not the
   final proof of predictive value.
5. Add source freshness and data completeness fields to future serving documents.
6. Evaluate risk models with temporal split, PR-AUC, calibration, and top-K risk
   capture before claiming predictive value.

## Defense Framing

If challenged on missing final model results, answer:

```text
The current contribution is a reproducible temporal data architecture and
training-ready pipeline. Final model claims are intentionally gated behind source
coverage, leakage checks, and validation metrics.
```

If challenged on existing platforms, answer:

```text
Existing company-information platforms mainly display company records. This
project transforms historical public signals into cutoff-safe company-year
features and future continuity-risk labels.
```

If challenged on broad target definition, answer:

```text
The global continuity target is broad by design, but secondary labels separate
legal distress, radiation, financial weakness, and filing anomaly risk.
```

## Reference Documents

- `docs/project_weak_points_and_improvement_plan.md`
- `docs/complete_project_weaknesses_and_improvement_plan.md`
- `docs/project_defense_report.md`
- `docs/feature_safety_registry.md`
- `docs/colab_data_preparation_pipeline_report.md`
- `docs/ml_continuity_risk_pipeline.md`
- `docs/model_validation_report.md`
- `docs/data_quality_report.md`
- `docs/dataset_readiness_report.md`
