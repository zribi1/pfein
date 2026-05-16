# ML Run Summary: 20260515-235051_continuity-risk-12m_hgb_time-test-2024_cap-2m_rows-2m

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
| Run folder | `20260515-235051_continuity-risk-12m_hgb_time-test-2024_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260515-235051` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_12005_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.7451 |
| ROC AUC | 0.8031 |
| Average precision | 0.1531 |
| Precision at 0.5 | 0.0839 |
| Recall at 0.5 | 0.7149 |
| F1 at 0.5 | 0.1502 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 210,608 | 71,680 |
| Actual 1 | 2,618 | 6,564 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 100.00% | 0.0315 | 1.0000 | 0.0611 |
| 0.005 | 100.00% | 0.0315 | 1.0000 | 0.0611 |
| 0.010 | 100.00% | 0.0315 | 1.0000 | 0.0611 |
| 0.020 | 93.16% | 0.0337 | 0.9979 | 0.0653 |
| 0.050 | 79.54% | 0.0394 | 0.9940 | 0.0757 |
| 0.100 | 67.88% | 0.0448 | 0.9645 | 0.0856 |
| 0.200 | 54.82% | 0.0527 | 0.9168 | 0.0996 |
| 0.300 | 46.68% | 0.0597 | 0.8850 | 0.1119 |
| 0.500 | 26.84% | 0.0839 | 0.7149 | 0.1502 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 292 | 0.9178 | 0.0292 | 29.1346 |
| top_0.5% | 1,458 | 0.3800 | 0.0603 | 12.0617 |
| top_1.0% | 2,915 | 0.2600 | 0.0826 | 8.2544 |
| top_5.0% | 14,574 | 0.1421 | 0.2255 | 4.5108 |
| top_10.0% | 29,147 | 0.1209 | 0.3839 | 3.8390 |

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
