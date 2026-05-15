# ML Run Summary: 20260515-012825_continuity-risk-12m_logreg_time-test-2024_cap-2m_rows-2m

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
| Run folder | `20260515-012825_continuity-risk-12m_logreg_time-test-2024_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260515-012825` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_12005_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.7873 |
| ROC AUC | 0.8587 |
| Average precision | 0.1213 |
| Precision at 0.5 | 0.0599 |
| Recall at 0.5 | 0.7892 |
| F1 at 0.5 | 0.1114 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 225,581 | 60,965 |
| Actual 1 | 1,038 | 3,886 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 98.89% | 0.0171 | 1.0000 | 0.0336 |
| 0.005 | 95.77% | 0.0176 | 0.9994 | 0.0346 |
| 0.010 | 94.21% | 0.0179 | 0.9984 | 0.0352 |
| 0.020 | 90.05% | 0.0187 | 0.9965 | 0.0367 |
| 0.050 | 81.50% | 0.0206 | 0.9923 | 0.0403 |
| 0.100 | 70.95% | 0.0233 | 0.9779 | 0.0455 |
| 0.200 | 56.17% | 0.0284 | 0.9439 | 0.0551 |
| 0.300 | 42.74% | 0.0357 | 0.9023 | 0.0686 |
| 0.500 | 22.25% | 0.0599 | 0.7892 | 0.1114 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 292 | 0.2329 | 0.0138 | 13.7848 |
| top_0.5% | 1,458 | 0.2298 | 0.0680 | 13.6008 |
| top_1.0% | 2,915 | 0.2237 | 0.1324 | 13.2399 |
| top_5.0% | 14,574 | 0.1300 | 0.3846 | 7.6927 |
| top_10.0% | 29,147 | 0.0995 | 0.5887 | 5.8875 |

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
