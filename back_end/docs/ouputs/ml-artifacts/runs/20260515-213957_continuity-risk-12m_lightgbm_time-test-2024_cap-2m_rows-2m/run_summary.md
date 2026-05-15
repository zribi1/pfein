# ML Run Summary: 20260515-213957_continuity-risk-12m_lightgbm_time-test-2024_cap-2m_rows-2m

## Dataset And Split

| Item | Value |
|---|---:|
| Eligible rows before cap | 191,592,143 |
| Training dataset rows | 2,000,000 |
| Dataset columns | 42 |
| Feature count | 33 |
| Excluded leakage/identifier columns | 9 |
| Positive rows | 67,133 |
| Negative rows | 1,932,867 |
| Positive rate | 3.36% |
| Train rows | 1,708,530 |
| Train positives | 57,951 |
| Test rows | 291,470 |
| Test positives | 9,182 |
| Missing values in X_train | 26,485,868 |
| Missing values in X_test | 4,450,264 |

## Experimental Design

| Item | Value |
|---|---|
| Run folder | `20260515-213957_continuity-risk-12m_lightgbm_time-test-2024_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260515-213957` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_12005_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.7656 |
| ROC AUC | 0.7966 |
| Average precision | 0.1379 |
| Precision at 0.5 | 0.0855 |
| Recall at 0.5 | 0.6645 |
| F1 at 0.5 | 0.1515 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 217,052 | 65,236 |
| Actual 1 | 3,081 | 6,101 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 97.08% | 0.0324 | 0.9995 | 0.0628 |
| 0.005 | 87.53% | 0.0359 | 0.9966 | 0.0692 |
| 0.010 | 83.02% | 0.0377 | 0.9931 | 0.0726 |
| 0.020 | 77.69% | 0.0401 | 0.9898 | 0.0771 |
| 0.050 | 69.65% | 0.0443 | 0.9789 | 0.0847 |
| 0.100 | 60.60% | 0.0488 | 0.9387 | 0.0928 |
| 0.200 | 49.14% | 0.0567 | 0.8838 | 0.1065 |
| 0.300 | 42.00% | 0.0630 | 0.8400 | 0.1172 |
| 0.500 | 24.47% | 0.0855 | 0.6645 | 0.1515 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 292 | 0.6130 | 0.0195 | 19.4593 |
| top_0.5% | 1,458 | 0.3717 | 0.0590 | 11.8004 |
| top_1.0% | 2,915 | 0.2614 | 0.0830 | 8.2980 |
| top_5.0% | 14,574 | 0.1411 | 0.2239 | 4.4782 |
| top_10.0% | 29,147 | 0.1187 | 0.3767 | 3.7672 |

## Generated Report Images

| Image | File |
|---|---|
| precision_recall_curve_png | `precision_recall_curve.png` |
| roc_curve_png | `roc_curve.png` |
| confusion_matrix_at_0_5_png | `confusion_matrix_at_0_5.png` |
| score_distribution_by_class_png | `score_distribution_by_class.png` |
| threshold_tradeoff_png | `threshold_tradeoff.png` |
| class_counts_by_year_png | `class_counts_by_year.png` |
| top_feature_importances_png | `top_feature_importances.png` |

## Interpretation Template

This run should be interpreted as a rare-event ranking experiment. Accuracy is secondary because the target is imbalanced. The strongest evidence is the temporal split strategy, average precision, threshold behavior, top-risk capture, and class balance by year.

## Next Action

Compare this run against previous entries in `model_run_index.jsonl`. If the split is temporal and the average precision remains above the positive base rate, proceed to threshold selection before changing the model family.
