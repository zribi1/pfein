# ML Run Summary: 20260515-020342_continuity-risk-12m_logreg_time-test-2024_cap-2m_rows-2m

## Dataset And Split

| Item | Value |
|---|---:|
| Eligible rows before cap | 191,592,143 |
| Training dataset rows | 2,000,000 |
| Dataset columns | 42 |
| Feature count | 34 |
| Excluded leakage/identifier columns | 8 |
| Positive rows | 28,172 |
| Negative rows | 1,971,828 |
| Positive rate | 1.41% |
| Train rows | 1,708,530 |
| Train positives | 23,248 |
| Test rows | 291,470 |
| Test positives | 4,924 |
| Missing values in X_train | 26,337,357 |
| Missing values in X_test | 4,444,335 |

## Experimental Design

| Item | Value |
|---|---|
| Run folder | `20260515-020342_continuity-risk-12m_logreg_time-test-2024_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260515-020342` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_12005_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.8087 |
| ROC AUC | 0.7638 |
| Average precision | 0.0606 |
| Precision at 0.5 | 0.0508 |
| Recall at 0.5 | 0.5833 |
| F1 at 0.5 | 0.0934 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 232,844 | 53,702 |
| Actual 1 | 2,052 | 2,872 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 100.00% | 0.0169 | 1.0000 | 0.0332 |
| 0.005 | 100.00% | 0.0169 | 1.0000 | 0.0332 |
| 0.010 | 99.99% | 0.0169 | 1.0000 | 0.0332 |
| 0.020 | 99.30% | 0.0170 | 0.9992 | 0.0334 |
| 0.050 | 99.25% | 0.0170 | 0.9988 | 0.0334 |
| 0.100 | 98.45% | 0.0171 | 0.9972 | 0.0336 |
| 0.200 | 89.25% | 0.0185 | 0.9775 | 0.0363 |
| 0.300 | 70.51% | 0.0219 | 0.9159 | 0.0429 |
| 0.500 | 19.41% | 0.0508 | 0.5833 | 0.0934 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 292 | 0.1541 | 0.0091 | 9.1223 |
| top_0.5% | 1,458 | 0.1303 | 0.0386 | 7.7139 |
| top_1.0% | 2,915 | 0.1146 | 0.0678 | 6.7824 |
| top_5.0% | 14,574 | 0.0773 | 0.2289 | 4.5774 |
| top_10.0% | 29,147 | 0.0663 | 0.3926 | 3.9257 |

## Generated Report Images

| Image | File |
|---|---|
| precision_recall_curve_png | `precision_recall_curve.png` |
| roc_curve_png | `roc_curve.png` |
| confusion_matrix_at_0_5_png | `confusion_matrix_at_0_5.png` |
| score_distribution_by_class_png | `score_distribution_by_class.png` |
| threshold_tradeoff_png | `threshold_tradeoff.png` |
| class_counts_by_year_png | `class_counts_by_year.png` |
| top_feature_coefficients_png | `top_feature_coefficients.png` |

## Interpretation Template

This run should be interpreted as a rare-event ranking experiment. Accuracy is secondary because the target is imbalanced. The strongest evidence is the temporal split strategy, average precision, threshold behavior, top-risk capture, and class balance by year.

## Next Action

Compare this run against previous entries in `model_run_index.jsonl`. If the split is temporal and the average precision remains above the positive base rate, proceed to threshold selection before changing the model family.
