# ML Run Summary: 20260515-213856_continuity-risk-12m_hgb_time-test-2024_cap-2m_rows-2m

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
| Run folder | `20260515-213856_continuity-risk-12m_hgb_time-test-2024_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260515-213856` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_12005_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.7409 |
| ROC AUC | 0.8024 |
| Average precision | 0.1552 |
| Precision at 0.5 | 0.0826 |
| Recall at 0.5 | 0.7150 |
| F1 at 0.5 | 0.1481 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 209,389 | 72,899 |
| Actual 1 | 2,617 | 6,565 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 100.00% | 0.0315 | 1.0000 | 0.0611 |
| 0.005 | 98.30% | 0.0320 | 0.9996 | 0.0621 |
| 0.010 | 95.31% | 0.0330 | 0.9992 | 0.0639 |
| 0.020 | 88.37% | 0.0356 | 0.9974 | 0.0687 |
| 0.050 | 78.07% | 0.0400 | 0.9912 | 0.0769 |
| 0.100 | 67.40% | 0.0455 | 0.9735 | 0.0869 |
| 0.200 | 54.59% | 0.0527 | 0.9133 | 0.0997 |
| 0.300 | 46.59% | 0.0597 | 0.8829 | 0.1118 |
| 0.500 | 27.26% | 0.0826 | 0.7150 | 0.1481 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 292 | 0.8493 | 0.0270 | 26.9603 |
| top_0.5% | 1,458 | 0.4005 | 0.0636 | 12.7149 |
| top_1.0% | 2,915 | 0.2806 | 0.0891 | 8.9078 |
| top_5.0% | 14,574 | 0.1455 | 0.2309 | 4.6176 |
| top_10.0% | 29,147 | 0.1217 | 0.3862 | 3.8619 |

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
