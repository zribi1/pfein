# ML Run Summary: 20260515-203559_continuity-risk-12m_logreg_time-test-2024_cap-2m_rows-2m

## Dataset And Split

| Item | Value |
|---|---:|
| Eligible rows before cap | 191,592,143 |
| Training dataset rows | 2,000,000 |
| Dataset columns | 42 |
| Feature count | 34 |
| Excluded leakage/identifier columns | 8 |
| Positive rows | 67,133 |
| Negative rows | 1,932,867 |
| Positive rate | 3.36% |
| Train rows | 1,708,530 |
| Train positives | 57,951 |
| Test rows | 291,470 |
| Test positives | 9,182 |
| Missing values in X_train | 28,131,575 |
| Missing values in X_test | 4,729,946 |

## Experimental Design

| Item | Value |
|---|---|
| Run folder | `20260515-203559_continuity-risk-12m_logreg_time-test-2024_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260515-203559` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_12005_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.6715 |
| ROC AUC | 0.7475 |
| Average precision | 0.0831 |
| Precision at 0.5 | 0.0664 |
| Recall at 0.5 | 0.7215 |
| F1 at 0.5 | 0.1215 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 189,084 | 93,204 |
| Actual 1 | 2,557 | 6,625 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 99.99% | 0.0315 | 1.0000 | 0.0611 |
| 0.005 | 98.82% | 0.0319 | 0.9997 | 0.0618 |
| 0.010 | 97.34% | 0.0323 | 0.9991 | 0.0626 |
| 0.020 | 94.87% | 0.0331 | 0.9978 | 0.0641 |
| 0.050 | 87.08% | 0.0359 | 0.9934 | 0.0694 |
| 0.100 | 82.88% | 0.0375 | 0.9867 | 0.0723 |
| 0.200 | 68.41% | 0.0426 | 0.9261 | 0.0815 |
| 0.300 | 59.39% | 0.0476 | 0.8965 | 0.0903 |
| 0.500 | 34.25% | 0.0664 | 0.7215 | 0.1215 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 292 | 0.2363 | 0.0075 | 7.5011 |
| top_0.5% | 1,458 | 0.1331 | 0.0211 | 4.2238 |
| top_1.0% | 2,915 | 0.1437 | 0.0456 | 4.5628 |
| top_5.0% | 14,574 | 0.1072 | 0.1702 | 3.4044 |
| top_10.0% | 29,147 | 0.0944 | 0.2997 | 2.9972 |

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
