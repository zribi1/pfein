# ML Run Summary: 20260515-003859_continuity-risk-12m_logreg_time-test-2024_cap-2m_rows-2m

## Dataset And Split

| Item | Value |
|---|---:|
| Eligible rows before cap | 191,592,143 |
| Training dataset rows | 2,000,000 |
| Dataset columns | 42 |
| Feature count | 38 |
| Excluded leakage/identifier columns | 4 |
| Positive rows | 28,172 |
| Negative rows | 1,971,828 |
| Positive rate | 1.41% |
| Train rows | 1,708,530 |
| Train positives | 23,248 |
| Test rows | 291,470 |
| Test positives | 4,924 |
| Missing values in X_train | 26,357,546 |
| Missing values in X_test | 4,447,148 |

## Experimental Design

| Item | Value |
|---|---|
| Run folder | `20260515-003859_continuity-risk-12m_logreg_time-test-2024_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260515-003859` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_12005_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.7932 |
| ROC AUC | 0.8688 |
| Average precision | 0.1337 |
| Precision at 0.5 | 0.0626 |
| Recall at 0.5 | 0.8050 |
| F1 at 0.5 | 0.1162 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 227,233 | 59,313 |
| Actual 1 | 960 | 3,964 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 96.71% | 0.0175 | 0.9996 | 0.0343 |
| 0.005 | 92.59% | 0.0182 | 0.9980 | 0.0358 |
| 0.010 | 90.71% | 0.0186 | 0.9963 | 0.0364 |
| 0.020 | 85.38% | 0.0196 | 0.9931 | 0.0385 |
| 0.050 | 75.18% | 0.0222 | 0.9860 | 0.0433 |
| 0.100 | 63.76% | 0.0259 | 0.9760 | 0.0504 |
| 0.200 | 49.87% | 0.0318 | 0.9387 | 0.0615 |
| 0.300 | 42.83% | 0.0357 | 0.9048 | 0.0687 |
| 0.500 | 21.71% | 0.0626 | 0.8050 | 0.1162 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 292 | 0.2568 | 0.0152 | 15.2039 |
| top_0.5% | 1,458 | 0.2606 | 0.0772 | 15.4277 |
| top_1.0% | 2,915 | 0.2473 | 0.1464 | 14.6411 |
| top_5.0% | 14,574 | 0.1366 | 0.4043 | 8.0866 |
| top_10.0% | 29,147 | 0.1025 | 0.6068 | 6.0682 |

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
