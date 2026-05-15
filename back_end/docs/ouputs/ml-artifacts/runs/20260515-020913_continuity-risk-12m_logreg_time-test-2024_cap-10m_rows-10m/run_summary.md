# ML Run Summary: 20260515-020913_continuity-risk-12m_logreg_time-test-2024_cap-10m_rows-10m

## Dataset And Split

| Item | Value |
|---|---:|
| Eligible rows before cap | 191,592,143 |
| Training dataset rows | 10,000,000 |
| Dataset columns | 42 |
| Feature count | 34 |
| Excluded leakage/identifier columns | 8 |
| Positive rows | 140,218 |
| Negative rows | 9,859,782 |
| Positive rate | 1.40% |
| Train rows | 8,539,189 |
| Train positives | 115,280 |
| Test rows | 1,460,811 |
| Test positives | 24,938 |
| Missing values in X_train | 131,617,278 |
| Missing values in X_test | 22,288,039 |

## Experimental Design

| Item | Value |
|---|---|
| Run folder | `20260515-020913_continuity-risk-12m_logreg_time-test-2024_cap-10m_rows-10m` |
| Model version | `continuity-risk-20260515-020913` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_60024_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.8100 |
| ROC AUC | 0.7644 |
| Average precision | 0.0623 |
| Precision at 0.5 | 0.0511 |
| Recall at 0.5 | 0.5763 |
| F1 at 0.5 | 0.0939 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 1,168,955 | 266,918 |
| Actual 1 | 10,565 | 14,373 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 100.00% | 0.0171 | 1.0000 | 0.0336 |
| 0.005 | 100.00% | 0.0171 | 0.9999 | 0.0336 |
| 0.010 | 99.99% | 0.0171 | 0.9998 | 0.0336 |
| 0.020 | 99.29% | 0.0172 | 0.9986 | 0.0338 |
| 0.050 | 99.23% | 0.0172 | 0.9982 | 0.0338 |
| 0.100 | 98.37% | 0.0173 | 0.9961 | 0.0340 |
| 0.200 | 88.08% | 0.0189 | 0.9741 | 0.0370 |
| 0.300 | 69.14% | 0.0226 | 0.9136 | 0.0440 |
| 0.500 | 19.26% | 0.0511 | 0.5763 | 0.0939 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 1,461 | 0.1424 | 0.0083 | 8.3396 |
| top_0.5% | 7,305 | 0.1451 | 0.0425 | 8.5000 |
| top_1.0% | 14,609 | 0.1251 | 0.0733 | 7.3257 |
| top_5.0% | 73,041 | 0.0790 | 0.2313 | 4.6250 |
| top_10.0% | 146,082 | 0.0662 | 0.3880 | 3.8796 |

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
