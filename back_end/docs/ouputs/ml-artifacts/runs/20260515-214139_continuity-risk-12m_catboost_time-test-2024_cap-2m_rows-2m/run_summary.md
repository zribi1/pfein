# ML Run Summary: 20260515-214139_continuity-risk-12m_catboost_time-test-2024_cap-2m_rows-2m

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
| Run folder | `20260515-214139_continuity-risk-12m_catboost_time-test-2024_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260515-214139` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_12005_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.7315 |
| ROC AUC | 0.7897 |
| Average precision | 0.1483 |
| Precision at 0.5 | 0.0798 |
| Recall at 0.5 | 0.7146 |
| F1 at 0.5 | 0.1436 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 206,650 | 75,638 |
| Actual 1 | 2,621 | 6,561 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 100.00% | 0.0315 | 1.0000 | 0.0611 |
| 0.005 | 99.97% | 0.0315 | 1.0000 | 0.0611 |
| 0.010 | 99.89% | 0.0315 | 1.0000 | 0.0611 |
| 0.020 | 96.07% | 0.0328 | 0.9990 | 0.0634 |
| 0.050 | 82.69% | 0.0377 | 0.9905 | 0.0727 |
| 0.100 | 70.36% | 0.0422 | 0.9436 | 0.0809 |
| 0.200 | 58.01% | 0.0498 | 0.9174 | 0.0945 |
| 0.300 | 48.12% | 0.0573 | 0.8745 | 0.1075 |
| 0.500 | 28.20% | 0.0798 | 0.7146 | 0.1436 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 292 | 0.8459 | 0.0269 | 26.8516 |
| top_0.5% | 1,458 | 0.3896 | 0.0619 | 12.3665 |
| top_1.0% | 2,915 | 0.2686 | 0.0853 | 8.5267 |
| top_5.0% | 14,574 | 0.1435 | 0.2277 | 4.5544 |
| top_10.0% | 29,147 | 0.1209 | 0.3837 | 3.8369 |

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
