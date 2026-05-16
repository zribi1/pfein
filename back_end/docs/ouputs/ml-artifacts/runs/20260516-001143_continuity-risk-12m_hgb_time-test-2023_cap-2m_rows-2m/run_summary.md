# ML Run Summary: 20260516-001143_continuity-risk-12m_hgb_time-test-2023_cap-2m_rows-2m

## Dataset And Split

| Item | Value |
|---|---:|
| Eligible rows before cap | 163,621,282 |
| Training dataset rows | 2,000,000 |
| Dataset columns | 42 |
| Feature count | 33 |
| Excluded leakage/identifier columns | 9 |
| Positive rows | 67,662 |
| Negative rows | 1,932,338 |
| Positive rate | 3.38% |
| Train rows | 1,673,493 |
| Train positives | 53,579 |
| Test rows | 326,507 |
| Test positives | 14,083 |
| Missing values in X_train | 26,012,906 |
| Missing values in X_test | 4,992,441 |

## Experimental Design

| Item | Value |
|---|---|
| Run folder | `20260516-001143_continuity-risk-12m_hgb_time-test-2023_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260516-001143` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_14057_of_1000000` |
| Split strategy | `time_split_latest_year_2023` |
| Train year range | 2017 to 2023 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.7397 |
| ROC AUC | 0.8771 |
| Average precision | 0.2987 |
| Precision at 0.5 | 0.1274 |
| Recall at 0.5 | 0.8611 |
| F1 at 0.5 | 0.2220 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 229,399 | 83,025 |
| Actual 1 | 1,956 | 12,127 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 100.00% | 0.0431 | 1.0000 | 0.0827 |
| 0.005 | 100.00% | 0.0431 | 1.0000 | 0.0827 |
| 0.010 | 100.00% | 0.0431 | 1.0000 | 0.0827 |
| 0.020 | 93.38% | 0.0462 | 0.9995 | 0.0883 |
| 0.050 | 81.72% | 0.0527 | 0.9976 | 0.1000 |
| 0.100 | 71.37% | 0.0600 | 0.9924 | 0.1131 |
| 0.200 | 57.22% | 0.0738 | 0.9788 | 0.1372 |
| 0.300 | 48.60% | 0.0851 | 0.9593 | 0.1564 |
| 0.500 | 29.14% | 0.1274 | 0.8611 | 0.2220 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 327 | 0.8135 | 0.0189 | 18.8595 |
| top_0.5% | 1,633 | 0.5873 | 0.0681 | 13.6154 |
| top_1.0% | 3,266 | 0.5364 | 0.1244 | 12.4370 |
| top_5.0% | 16,326 | 0.3215 | 0.3726 | 7.4527 |
| top_10.0% | 32,651 | 0.2308 | 0.5350 | 5.3504 |

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
