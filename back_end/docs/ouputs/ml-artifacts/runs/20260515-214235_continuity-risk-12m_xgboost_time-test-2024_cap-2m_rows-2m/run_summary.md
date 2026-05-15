# ML Run Summary: 20260515-214235_continuity-risk-12m_xgboost_time-test-2024_cap-2m_rows-2m

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
| Run folder | `20260515-214235_continuity-risk-12m_xgboost_time-test-2024_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260515-214235` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_12005_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.7542 |
| ROC AUC | 0.7345 |
| Average precision | 0.1031 |
| Precision at 0.5 | 0.0689 |
| Recall at 0.5 | 0.5432 |
| F1 at 0.5 | 0.1222 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 214,832 | 67,456 |
| Actual 1 | 4,194 | 4,988 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 100.00% | 0.0315 | 1.0000 | 0.0611 |
| 0.005 | 99.37% | 0.0317 | 0.9991 | 0.0614 |
| 0.010 | 98.42% | 0.0320 | 0.9985 | 0.0619 |
| 0.020 | 90.68% | 0.0345 | 0.9935 | 0.0667 |
| 0.050 | 78.01% | 0.0387 | 0.9585 | 0.0744 |
| 0.100 | 67.40% | 0.0428 | 0.9162 | 0.0818 |
| 0.200 | 57.04% | 0.0482 | 0.8718 | 0.0913 |
| 0.300 | 46.96% | 0.0532 | 0.7931 | 0.0997 |
| 0.500 | 24.85% | 0.0689 | 0.5432 | 0.1222 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 292 | 0.5240 | 0.0167 | 16.6328 |
| top_0.5% | 1,458 | 0.2888 | 0.0459 | 9.1660 |
| top_1.0% | 2,915 | 0.2161 | 0.0686 | 6.8605 |
| top_5.0% | 14,574 | 0.1158 | 0.1838 | 3.6766 |
| top_10.0% | 29,147 | 0.0949 | 0.3011 | 3.0113 |

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
