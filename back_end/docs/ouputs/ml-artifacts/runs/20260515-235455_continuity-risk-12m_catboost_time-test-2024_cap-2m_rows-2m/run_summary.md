# ML Run Summary: 20260515-235455_continuity-risk-12m_catboost_time-test-2024_cap-2m_rows-2m

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
| Run folder | `20260515-235455_continuity-risk-12m_catboost_time-test-2024_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260515-235455` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_12005_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.7268 |
| ROC AUC | 0.7991 |
| Average precision | 0.1554 |
| Precision at 0.5 | 0.0810 |
| Recall at 0.5 | 0.7416 |
| F1 at 0.5 | 0.1461 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 205,039 | 77,249 |
| Actual 1 | 2,373 | 6,809 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 100.00% | 0.0315 | 1.0000 | 0.0611 |
| 0.005 | 99.71% | 0.0316 | 1.0000 | 0.0613 |
| 0.010 | 99.15% | 0.0318 | 0.9998 | 0.0616 |
| 0.020 | 87.02% | 0.0361 | 0.9977 | 0.0697 |
| 0.050 | 77.14% | 0.0401 | 0.9812 | 0.0770 |
| 0.100 | 70.22% | 0.0425 | 0.9476 | 0.0814 |
| 0.200 | 53.46% | 0.0537 | 0.9120 | 0.1015 |
| 0.300 | 45.65% | 0.0604 | 0.8753 | 0.1130 |
| 0.500 | 28.84% | 0.0810 | 0.7416 | 0.1461 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 292 | 0.8493 | 0.0270 | 26.9603 |
| top_0.5% | 1,458 | 0.4204 | 0.0668 | 13.3463 |
| top_1.0% | 2,915 | 0.2957 | 0.0939 | 9.3870 |
| top_5.0% | 14,574 | 0.1445 | 0.2294 | 4.5871 |
| top_10.0% | 29,147 | 0.1217 | 0.3863 | 3.8630 |

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
