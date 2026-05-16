# ML Run Summary: 20260516-000931_continuity-risk-12m_hgb_time-test-2022_cap-2m_rows-2m

## Dataset And Split

| Item | Value |
|---|---:|
| Eligible rows before cap | 136,849,242 |
| Training dataset rows | 2,000,000 |
| Dataset columns | 42 |
| Feature count | 33 |
| Excluded leakage/identifier columns | 9 |
| Positive rows | 63,989 |
| Negative rows | 1,936,011 |
| Positive rate | 3.20% |
| Train rows | 1,626,373 |
| Train positives | 50,222 |
| Test rows | 373,627 |
| Test positives | 13,767 |
| Missing values in X_train | 25,327,236 |
| Missing values in X_test | 5,760,985 |

## Experimental Design

| Item | Value |
|---|---|
| Run folder | `20260516-000931_continuity-risk-12m_hgb_time-test-2022_cap-2m_rows-2m` |
| Model version | `continuity-risk-20260516-000931` |
| Target | `continuity_risk_12m_label` |
| Horizon | 12 months |
| Sampling strategy | `deterministic_hash_sample_threshold_16807_of_1000000` |
| Split strategy | `time_split_latest_year_2022` |
| Train year range | 2017 to 2022 |

## Main Metrics

| Metric | Value |
|---|---:|
| Accuracy | 0.6934 |
| ROC AUC | 0.8503 |
| Average precision | 0.1996 |
| Precision at 0.5 | 0.0948 |
| Recall at 0.5 | 0.8568 |
| F1 at 0.5 | 0.1708 |

## Confusion Matrix At Threshold 0.5

| Actual / Predicted | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | 247,287 | 112,573 |
| Actual 1 | 1,971 | 11,796 |

## Threshold Analysis

| Threshold | Flagged rate | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 0.001 | 100.00% | 0.0368 | 1.0000 | 0.0711 |
| 0.005 | 100.00% | 0.0368 | 1.0000 | 0.0711 |
| 0.010 | 100.00% | 0.0368 | 1.0000 | 0.0711 |
| 0.020 | 93.85% | 0.0392 | 0.9996 | 0.0755 |
| 0.050 | 82.25% | 0.0447 | 0.9974 | 0.0855 |
| 0.100 | 74.33% | 0.0492 | 0.9931 | 0.0938 |
| 0.200 | 59.78% | 0.0600 | 0.9735 | 0.1130 |
| 0.300 | 51.17% | 0.0686 | 0.9531 | 0.1280 |
| 0.500 | 33.29% | 0.0948 | 0.8568 | 0.1708 |

## Top-Risk Capture

| Segment | Rows | Precision | Recall | Lift |
|---|---:|---:|---:|---:|
| top_0.1% | 374 | 0.8209 | 0.0223 | 22.2775 |
| top_0.5% | 1,869 | 0.4842 | 0.0657 | 13.1413 |
| top_1.0% | 3,737 | 0.3168 | 0.0860 | 8.5986 |
| top_5.0% | 18,682 | 0.1919 | 0.2604 | 5.2079 |
| top_10.0% | 37,363 | 0.1799 | 0.4882 | 4.8819 |

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
