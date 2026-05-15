# ML Experiment Tracking Report

## Purpose

This document records the modelling decisions, evaluation evidence, and next
actions for the company continuity-risk model. Its role is to make model
development reproducible and academically defensible: each experiment must state
what was changed, why it was changed, what evidence was produced, and what the
next correction or comparison should be.

## Research Objective

The current modelling objective is to predict whether a company observed at a
given prediction year will experience a continuity-risk event within the next
12 months. The primary supervised target is:

```text
continuity_risk_12m_label
```

The model is evaluated as a rare-event risk-ranking problem. Therefore, accuracy
is not sufficient. The main evidence should focus on average precision,
precision-recall behavior, temporal validation, threshold analysis, and top-risk
capture.

## Evidence Stored For Each Training Run

The training command now writes a permanent experiment folder for every model
run. The folder name is intentionally descriptive so that final-report evidence
can be distinguished without opening every metadata file:

```text
ML_ARTIFACTS_DIR/runs/<YYYYMMDD-HHMMSS>_<target>_<model>_<split>_<cap>_<rows>/
```

Example:

```text
ML_ARTIFACTS_DIR/runs/20260515-143012_continuity-risk-12m_logreg_time-test-2024_cap-2m_rows-2m/
```

Each run folder stores:

| Artifact | Purpose |
|---|---|
| `metadata.json` | Full configuration, feature list, class counts, split strategy, and metrics |
| `run_summary.md` | Report-ready summary of dataset, split, metrics, threshold results, and generated images |
| `metrics_summary.csv` | One-row metric table for quick comparison or spreadsheet import |
| `threshold_analysis.csv` | Precision, recall, false-positive rate, and flagged rate for several thresholds |
| `top_k_analysis.csv` | Precision, recall, and lift for the highest-risk score segments |
| `class_counts_by_year.json` | Positive and negative label counts by prediction year |
| `feature_coefficients.csv` | Logistic-regression coefficients after preprocessing |
| `precision_recall_curve.png` | Main visual evidence for rare-event performance |
| `roc_curve.png` | Ranking-quality comparison across thresholds |
| `confusion_matrix_at_0_5.png` | Baseline threshold evidence, mainly for diagnosis |
| `score_distribution_by_class.png` | Shows whether positive and negative companies separate in score space |
| `threshold_tradeoff.png` | Visual support for operational threshold choice |
| `class_counts_by_year.png` | Shows temporal class balance and label availability |
| `top_feature_coefficients.png` | Report image showing the strongest positive and negative model coefficients |

The latest run is still copied to:

```text
ML_ARTIFACTS_DIR/model_metadata.json
```

For run-to-run comparison, the trainer appends a compact line to:

```text
ML_ARTIFACTS_DIR/model_run_index.jsonl
```

It also refreshes:

| Artifact | Purpose |
|---|---|
| `model_run_comparison.csv` | Spreadsheet-ready comparison across all training runs |
| `model_run_comparison.png` | Report image showing metric movement across runs |

## Current Experiment Log

| ID | Model | Data cap | Split | Main result | Interpretation | Next action |
|---|---|---:|---|---|---|---|
| E001 | Logistic regression with balanced class weights | 2,000,000 rows | Stratified random split | Accuracy 0.84, average precision 0.0606, positive rate about 0.41% | The model learned signal above random ranking, but random split can overestimate real future performance | Rerun with deterministic hash sampling and latest-year temporal holdout |

The E001 result should be treated as a baseline diagnostic result, not as the
final model claim. Since the positive class is very rare, the average precision
is more meaningful than accuracy. A random classifier would have an expected
average precision close to the positive rate, approximately 0.0041 in this run.
The observed value of 0.0606 is therefore promising, but it must survive a
time-based validation split.

## Immediate Next Experiment

The next experiment should keep the same baseline model and change the
evaluation design:

| Item | Choice |
|---|---|
| Model family | Logistic regression baseline |
| Training cap | `TRAIN_MAX_ROWS = 2_000_000` |
| Sampling | Deterministic hash sample spread across eligible years |
| Validation | Train on older years, test on the latest supervised year |
| Expected metadata | `split_strategy = "time_split_latest_year_2024"` |
| Main metric | Average precision on the 2024 holdout |
| Secondary evidence | ROC AUC, threshold analysis, top-K capture, confusion matrix, class counts by year |

The purpose of this experiment is not to maximize the score immediately. It is
to answer a more important question: does the model still rank future risk when
it is evaluated on a later year that was not mixed into training?

## Baseline Versus Dedicated Models

The project should continue with the baseline continuity model for the next
run. Moving immediately to dedicated models would create more outputs but less
certainty, because the central validation question is still unresolved.

The recommended modelling sequence is:

1. Validate the global continuity baseline with a temporal split.
2. Choose an operational threshold or top-risk segment using the saved
   threshold and top-K artifacts.
3. Compare the baseline with one stronger model family, preferably a calibrated
   tree-based model, only after the temporal baseline is documented.
4. Train dedicated secondary models after the global target is stable:
   `legal_distress_risk_12m_label`, `radiation_risk_12m_label`,
   `financial_weakness_risk_12m_label`, and `filing_anomaly_risk_12m_label`.

This sequence is easier to defend academically because it separates data
validity, validation design, model-family comparison, and target specialization.

## TRAIN_MAX_ROWS Policy

`TRAIN_MAX_ROWS` should not be increased before the next temporal validation
run. The current value of 2,000,000 rows is large enough to test whether the new
sampling and split logic work while still being safer for Colab memory.

Increase the cap only if:

| Condition | Reason |
|---|---|
| The 2,000,000-row temporal run completes without memory errors | Larger pandas training tables may crash Colab |
| The 2024 holdout contains enough positive examples | More rows help only if the test signal is measurable |
| Average precision or threshold behavior is unstable | More positives can reduce variance |
| Runtime remains acceptable | Reproducibility matters more than one oversized run |

If these conditions are satisfied, the next reasonable caps are 3,000,000 and
then 5,000,000 rows. The increase should be documented as a separate experiment,
not mixed with a model-family change.

## Comparison Rules

Each future model run should be compared using the same evidence:

| Evidence | Why It Matters |
|---|---|
| Split strategy | Temporal validation is more honest than random splitting |
| Positive rate by year | Rare-event metrics depend on class prevalence |
| Average precision | Main rare-event ranking metric |
| ROC AUC | Secondary ranking metric |
| Top-K recall and lift | Shows whether the highest-risk companies concentrate true events |
| Threshold table | Supports operational alert threshold selection |
| Confusion matrix | Diagnoses false positives and false negatives at one threshold |
| Feature list | Confirms that no future or identifier leakage entered the model |
| Generated PNG figures | Provides images that can be inserted directly into the final report |

## Report Summary

The project should remain on the baseline continuity-risk model until the
temporal holdout run is documented. The next run should use
`TRAIN_MAX_ROWS = 2_000_000`, deterministic hash sampling, and latest-year
temporal evaluation. The trainer now saves permanent evidence for every run, so
future model progress can be shown through metadata, plots, threshold tables,
run summaries, and cross-run comparison images rather than isolated metric
screenshots.
