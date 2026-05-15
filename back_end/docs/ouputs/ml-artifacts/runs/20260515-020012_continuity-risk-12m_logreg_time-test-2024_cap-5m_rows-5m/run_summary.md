# ML Run Summary: 20260515-020012_continuity-risk-12m_logreg_time-test-2024_cap-5m_rows-5m

## Dataset And Split

| Item | Value |
|---|---:|
| Eligible rows before cap | 191,592,143 |
| Training dataset rows | 5,000,000 |
| Dataset columns | 42 |
| Feature count | 34 |
| Excluded leakage/identifier columns | 8 |
| Positive rows | 69,959 |
| Negative rows | 4,930,041 |
| Positive rate | 1.40% |
| Train rows | 4,271,016 |
| Train positives | 57,556 |
| Test rows | 728,984 |
| Test positives | 12,403 |
| Missing values in X_train | 65,836,604 |
| Missing values in X_test | 11,122,847 |

## Experimental Design

| Item | Value |
|---|---|
| Run folder | `20260515-020012_continuity-risk-12m_logreg_time-test-2024_cap-5m_rows-5m` |
| Model version | `continuity-risk-20260515-020012` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_30012_of_1000000` |
| Split strategy | `time_split_latest_year_2024` |
| Train year range | 2017 to 2024 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.8107 |
| ROC AUC | 0.7649 |
| Average precision | 0.0624 |
| Precision at 0.5 | 0.0511 |
| Recall at 0.5 | 0.5764 |
| F1 at 0.5 | 0.0939 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 583,826 | 132,755 |
| Actual 1 | 5,254 | 7,149 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 100.00% | 0.0170 | 1.0000 | 0.0335 |
| 0.005 | 100.00% | 0.0170 | 1.0000 | 0.0335 |
| 0.010 | 99.99% | 0.0170 | 0.9999 | 0.0335 |
| 0.020 | 99.28% | 0.0171 | 0.9990 | 0.0337 |
| 0.050 | 99.22% | 0.0171 | 0.9984 | 0.0337 |
| 0.100 | 98.37% | 0.0172 | 0.9963 | 0.0339 |
| 0.200 | 88.07% | 0.0188 | 0.9734 | 0.0369 |
| 0.300 | 69.20% | 0.0224 | 0.9117 | 0.0438 |
| 0.500 | 19.19% | 0.0511 | 0.5764 | 0.0939 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 729 | 0.1523 | 0.0089 | 8.9493 |
| top_0.5% | 3,645 | 0.1418 | 0.0417 | 8.3365 |
| top_1.0% | 7,290 | 0.1225 | 0.0720 | 7.1997 |
| top_5.0% | 36,450 | 0.0790 | 0.2320 | 4.6407 |
| top_10.0% | 72,899 | 0.0664 | 0.3902 | 3.9022 |

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
