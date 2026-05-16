# Phase F — Per-Segment Performance Summary

Model: tuned HGB, trained 2017–2022, evaluated on 2023.

### NAF section
- Cells reported: 11 (after 1000-row min-size cut)
- AP range: 0.105 (0) – 0.572 (unknown)
- AUC range: 0.811 – 0.918
- Lift over base rate: 4.4× – 38.8× (worst: 4)

### Legal-form bucket
- Cells reported: 13 (after 1000-row min-size cut)
- AP range: 0.008 (unknown) – 0.373 (52)
- AUC range: 0.464 – 0.919
- Lift over base rate: 2.0× – 50.7× (worst: 21)

### Company age bucket
- Cells reported: 5 (after 1000-row min-size cut)
- AP range: 0.009 (unknown) – 0.378 (<3y)
- AUC range: 0.755 – 0.882
- Lift over base rate: 3.2× – 11.2× (worst: <3y)

## Interpretation guide
- A tight AP range (<2× spread) means the model is segment-robust.
- A wide AUC range (>0.10 spread) means ranking quality varies materially across segments.
- A segment with low lift (<1.5×) is one where the model adds little over predicting the base rate.
