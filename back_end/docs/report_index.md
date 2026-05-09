# Report Index And Documentation Review

## Purpose

This index summarizes the current Markdown report set, the role of each file,
and the remaining documentation gaps. It is intended as a quick handover page
before copying sections into the final end-of-studies report.

## Current Report Set

| File | Status | Role |
|---|---|---|
| `docs/system_data_architecture.md` | Updated | Global architecture across INPI, BODACC, INSEE, financial data, data lake, MongoDB, API, and ML |
| `docs/data_lake_pipeline.md` | Updated | Operational reference for data-lake paths, exporters, feature tables, manifests, and monitoring |
| `docs/inpi_report_section.md` | Reviewed | Source-specific INPI/RNE pipeline section |
| `docs/bodacc_report_section.md` | Reviewed | Source-specific BODACC pipeline section |
| `docs/bodacc_report_section_fr.md` | Regenerated | French BODACC section with clean UTF-8 text |
| `docs/insee_report_section.md` | Updated | Source-specific INSEE Sirene pipeline section |
| `docs/financial_report_section.md` | Updated | Source-specific financial Parquet pipeline section with full clean-build evidence |
| `docs/ml_continuity_risk_pipeline.md` | Updated | ML feature, label, training, scoring, and publishing section |
| `docs/model_validation_report.md` | Updated with interim status | Validation checks, metrics, leakage review, and publishing gate |
| `docs/data_quality_report.md` | Updated with current evidence | Data-lake quality checks, reproducibility evidence, and source-specific checks |
| `docs/dataset_readiness_report.md` | Added | Local source-completeness gate before feature rebuilds and training |
| `docs/data_collection_checklist.md` | Added | Incremental checklist for source inventory, collection, feature building, and training gates |
| `docs/backend_api_operations_report.md` | Added | Missing API, worker, scheduler, endpoint, and operations section |
| `docs/docker_runtime_strategy.md` | Added | Clarifies Docker as the final runtime and host volumes as storage |
| `docs/project_ai_context.md` | Added | Compact decision memory for AI-assisted work and teammate handover |
| `docs/colab_user_guide.md` | Added | Copy-paste Google Colab user guide for fresh notebooks, downloads, rebuilds, audits, and troubleshooting |
| `docs/project_weak_points_and_improvement_plan.md` | Added | Honest risk register for project weaknesses and improvement priorities |
| `docs/complete_project_weaknesses_and_improvement_plan.md` | Added | Consolidated report and project weakness analysis with defense attack questions |
| `docs/feature_safety_registry.md` | Added | Feature/label safety registry for historical validity and leakage control |
| `docs/report_markdown_rules.md` | Updated | Documentation style, structure, vocabulary, and checklist rules |

## Coverage Matrix

| Topic | Covered In |
|---|---|
| Global storage architecture | `system_data_architecture.md` |
| Data-lake paths and commands | `data_lake_pipeline.md` |
| INPI annual accounts and formalities | `inpi_report_section.md` |
| BODACC legal events and risk flags | `bodacc_report_section.md` |
| INSEE identity and status | `insee_report_section.md` |
| Financial Parquet data | `financial_report_section.md` |
| Company-year ML features and labels | `ml_continuity_risk_pipeline.md` |
| Model validation process | `model_validation_report.md` |
| Data-quality and reproducibility checks | `data_quality_report.md` |
| Dataset readiness gate | `dataset_readiness_report.md` |
| Incremental collection plan | `data_collection_checklist.md` |
| Prediction publishing to MongoDB | `ml_continuity_risk_pipeline.md`, `backend_api_operations_report.md` |
| FastAPI endpoints and scheduler jobs | `backend_api_operations_report.md` |
| Docker runtime and host/local boundary | `docker_runtime_strategy.md` |
| AI/project decision memory | `project_ai_context.md` |
| Google Colab user workflow | `colab_user_guide.md` |
| Project weak points and improvement plan | `project_weak_points_and_improvement_plan.md` |
| Consolidated weakness analysis and defense questions | `complete_project_weaknesses_and_improvement_plan.md` |
| Feature leakage and historical safety registry | `feature_safety_registry.md` |
| Report writing rules | `report_markdown_rules.md` |

## Review Findings

| Finding | Action Taken |
|---|---|
| Financial data was referenced in architecture and ML docs but had no dedicated report section | Added `financial_report_section.md` |
| API and worker operations were described only indirectly in code and `CLAUDE.md` | Added `backend_api_operations_report.md` |
| ML report did not describe the implemented feature columns, label columns, or explanation factors | Expanded `ml_continuity_risk_pipeline.md` |
| Data-lake report did not document financial handling or feature-source fallback order | Updated `data_lake_pipeline.md` |
| Architecture limitations still described feature generation as not implemented | Updated limitations to reflect current CLI tooling and remaining orchestration gap |
| French BODACC report contained visible encoding artifacts | Regenerated the section with clean UTF-8 French text |
| INSEE report still framed bulk Sirene support as future work | Updated it to reflect the implemented bulk exporter and remaining clean-layer work |
| Model validation and data-quality reports were missing | Added report templates that can be populated after real runs |
| First BODACC and feature-builder smoke tests were executed | Recorded row counts, manifests, label balance, and training blocker |
| Financial full clean build and interim multi-year features were completed | Recorded full financial rows, interim feature rows, and rebuild blocker |
| Partial data could be confused with training-ready data | Added `scripts/check_dataset_readiness.py` and `dataset_readiness_report.md` |
| Runtime boundary was unclear between host Python and Docker | Added `docker_runtime_strategy.md` and copied operational scripts into the Docker image |

## Remaining Documentation Gaps

| Gap | Recommended Next Step |
|---|---|
| Financial ratios are not implemented yet | Add margin, leverage, liquidity, and trend features after schema review |
| Final Mongo serving model is still partly conceptual | Add a report section after implementing `company_profiles`, `company_events_summary`, and `company_search` |
| Model validation metrics are not populated yet | Finish INPI, INSEE, and historical BODACC coverage, rebuild features, then train and update `docs/model_validation_report.md` |
| Full data-quality measurements are not populated yet | Update `docs/data_quality_report.md` after final full exports |
| Feature safety registry is currently documentation-backed | Optionally add a training-time registry loader to block unsafe columns automatically |

## Recommended Reading Order

1. `docs/system_data_architecture.md`
2. `docs/data_lake_pipeline.md`
3. Source sections: INSEE, INPI, BODACC, financial
4. `docs/ml_continuity_risk_pipeline.md`
5. `docs/model_validation_report.md`
6. `docs/data_quality_report.md`
7. `docs/dataset_readiness_report.md`
8. `docs/backend_api_operations_report.md`
9. `docs/docker_runtime_strategy.md`
10. `docs/report_markdown_rules.md`
11. `docs/project_ai_context.md`
12. `docs/colab_user_guide.md`
13. `docs/project_weak_points_and_improvement_plan.md`
14. `docs/feature_safety_registry.md`

## Report Summary

The report set now covers the main source pipelines, the data-lake architecture,
the first continuity-risk ML pipeline, and backend operations. The largest
remaining documentation tasks are tied to implementation work that is still in
progress: full INPI/INSEE/BODACC coverage, final Mongo serving documents, model
validation results, financial ratios, and measured data-quality evidence.
