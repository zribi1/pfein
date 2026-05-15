# ML Run Summary: 20260515-193645_continuity-risk-12m_logreg_time-test-2024_cap-2m_rows-2m

## Dataset And Split

| Item | Value |
|---|---:|
| Eligible rows before cap | 191,592,143 |
| Training dataset rows | 2,000,000 |
| Dataset columns | 42 |
| Feature count | 38 |
| Excluded leakage/identifier columns | 4 |
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
| Run folder | `20260515-193645_continuity-risk-12m_logreg_time-test-2024_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260515-193645` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_12005_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.6624 |
| ROC AUC | 0.7435 |
| Average precision | 0.0809 |
| Precision at 0.5 | 0.0647 |
| Recall at 0.5 | 0.7216 |
| F1 at 0.5 | 0.1187 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 186,441 | 95,847 |
| Actual 1 | 2,556 | 6,626 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 100.00% | 0.0315 | 1.0000 | 0.0611 |
| 0.005 | 99.56% | 0.0316 | 1.0000 | 0.0613 |
| 0.010 | 98.35% | 0.0320 | 0.9997 | 0.0621 |
| 0.020 | 95.73% | 0.0329 | 0.9986 | 0.0636 |
| 0.050 | 89.81% | 0.0349 | 0.9955 | 0.0675 |
| 0.100 | 84.92% | 0.0367 | 0.9880 | 0.0707 |
| 0.200 | 70.19% | 0.0415 | 0.9247 | 0.0794 |
| 0.300 | 59.80% | 0.0470 | 0.8931 | 0.0894 |
| 0.500 | 35.16% | 0.0647 | 0.7216 | 0.1187 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 292 | 0.2123 | 0.0068 | 6.7401 |
| top_0.5% | 1,458 | 0.1646 | 0.0261 | 5.2253 |
| top_1.0% | 2,915 | 0.1341 | 0.0426 | 4.2579 |
| top_5.0% | 14,574 | 0.1016 | 0.1612 | 3.2236 |
| top_10.0% | 29,147 | 0.0911 | 0.2890 | 2.8904 |

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
