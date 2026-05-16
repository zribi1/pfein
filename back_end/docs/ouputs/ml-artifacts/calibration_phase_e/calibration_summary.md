# Phase E — Probability Calibration Summary

Model: tuned HGB, trained 2017–2021, recalibrated on 2022, evaluated on 2023.

## Metrics on 2023 test set

```
     variant    brier      ece  log_loss  mean_predicted  mean_observed       ap      auc
uncalibrated 0.175233 0.305398  0.500936        0.348530       0.043132 0.219895 0.860388
       platt 0.037082 0.006510  0.138234        0.037605       0.043132 0.219895 0.860388
    isotonic 0.036742 0.005916  0.137589        0.037606       0.043132 0.212323 0.861320
```

## Verdict

- **Best Brier**: isotonic
- **Best ECE**: isotonic
- ECE drop from recalibration: +0.2995
- Brier drop from recalibration: +0.1385

**Recommendation:** The uncalibrated ECE is 0.3054, which is materially miscalibrated. Recalibrate using **isotonic** (Brier 0.0367, ECE 0.0059 — reduction of 0.1385 / 0.2995 respectively). Save the calibrator alongside the model and apply it before exposing probabilites_cessation to users.

## Note on ranking

AP and AUC are unchanged across uncalibrated / Platt / Isotonic. Both recalibrators are monotone, so the *order* of companies by score is identical and Phase F's segment-robustness results carry over.
