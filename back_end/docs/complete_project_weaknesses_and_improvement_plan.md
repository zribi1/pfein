# Complete Weak Points and Improvement Plan

This document combines all the previous analysis into one Markdown file.

It includes:

1. Weak points in the **report/documentation**
2. Weak points in the **actual project/work**
3. Summary of what can be improved or fixed
4. Priority actions to make the project stronger and more defensible

---

# Part 1 — Weak Points in the Report

## Overall Opinion About the Report

The report is strong as a defense document because it presents the project as more than “just an ML model.”

It correctly emphasizes:

- data foundation before machine learning;
- temporal logic;
- reproducibility;
- leakage control;
- source traceability;
- separation between analytical processing and serving;
- cautious model training.

The architecture is also defensible:

```text
source archives -> Parquet data lake -> clean tables -> feature tables -> MongoDB serving -> FastAPI/frontend
```

This separation makes sense and is well explained.

However, if the report is attacked like a jury member or supervisor would attack it, several weaknesses appear.

---

## 1. The Project Sounds Ambitious but Not Fully Proven Yet

### Weak Point

The report says many things are planned or partially ready:

- INPI is in progress;
- INSEE clean identity is still limited;
- BODACC historical coverage is still needed;
- features are interim;
- model training should wait until readiness checks pass.

This honesty is good, but it exposes the main vulnerability:

```text
The final ML claim is not yet demonstrated.
```

### Possible Attack Question

```text
You say the system can predict continuity risk, but where are the final results?
```

### Better Defense

```text
At this stage, the contribution is the construction of a reliable, temporal, multi-source data pipeline.
The model is intentionally postponed because training on incomplete source coverage would create weak or misleading results.
```

This is a good answer, but you must be ready for this criticism.

---

## 2. “Continuity Risk” Is Broad and May Be Too Vague

### Weak Point

The target includes:

- administrative closure;
- radiation;
- liquidation;
- redressement;
- sauvegarde;
- collective procedure;
- cessation signals.

This is practical, but it mixes different realities.

For example:

```text
voluntary cessation ≠ liquidation judiciaire
radiation can be administrative
inactive company ≠ bankrupt company
legal distress ≠ business closure
```

### Possible Attack Question

```text
Are you predicting bankruptcy, closure, legal risk, or administrative inactivity?
```

### Better Defense

```text
The main target is not bankruptcy alone.
It is a broader 12-month continuity-risk event.
To avoid confusion, the project also separates secondary labels:
legal distress risk, radiation risk, financial weakness risk, and filing anomaly risk.
```

The secondary-label idea is strong and should be emphasized more.

---

## 3. Financial Missing Data Is Dangerous

### Weak Point

The report says financial data is useful, but many companies may have:

- incomplete statements;
- confidential statements;
- delayed financial data;
- unavailable accounts;
- no mandatory publication obligation.

The danger is that the model may learn publication behavior more than real financial health.

### Possible Attack Question

```text
How do you know missing financial statements are a risk signal and not just a legal/accounting normality?
```

### Improvement

Strengthen the report by saying:

```text
Missing financial values are not automatically treated as negative.
The model uses explicit availability indicators, filing recency, and source-coverage features so that absence of data is interpreted carefully.
```

This point should be made very explicit.

---

## 4. Leakage Control Is Described, but Not Proven

### Weak Point

The report has the correct principle:

```text
Features before prediction date.
Labels after prediction date.
```

This is excellent, but a jury may ask for implementation proof.

### Possible Attack Question

```text
How do you guarantee that BODACC or INPI events after the prediction date are not accidentally included in the features?
```

This is dangerous because even one date bug can destroy the validity of the model.

### Improvement

Add concrete examples:

```text
For prediction_year = 2023:

feature window:
all events with event_date <= 2023-12-31

label window:
events with 2024-01-01 <= event_date <= 2024-12-31
```

Add validation checks:

```text
max(feature_event_date) <= prediction_date
min(label_event_date) > prediction_date
```

The report already explains the temporal rule, but it would be stronger with actual quality-control checks.

---

## 5. The Model Part Is Still Too Generic

### Weak Point

The report says:

- baseline logistic regression first;
- later random forest;
- gradient boosting;
- calibrated boosting models.

This is reasonable, but it does not say enough about the exact evaluation protocol.

### Possible Attack Questions

```text
What is your success criterion?
What metric value is acceptable?
What threshold will you use?
What is the cost of false positives and false negatives?
```

### Improvement

Add a clearer threshold strategy:

```text
The model will not only be evaluated by ROC AUC.
We will choose an operational threshold based on the trade-off between:

- false negatives: risky companies missed by the system;
- false positives: healthy companies incorrectly flagged as risky.
```

This makes the ML part feel more serious.

---

## 6. Source Reliability and Update Timing Need More Discussion

### Weak Point

The report says sources have different formats, sizes, update rhythms, and meanings.

That is good, but for a company intelligence website, freshness matters.

### Possible Attack Question

```text
If INSEE, INPI, BODACC, and financial data update at different times, how do you know the company profile is current?
```

### Improvement

Add a “data freshness” section with:

- source extraction date;
- archive date;
- last update date by source;
- last successful pipeline run;
- confidence level of each profile.

Example:

```json
{
  "siren": "123456789",
  "last_insee_update": "2026-03-01",
  "last_inpi_update": "2026-03-10",
  "last_bodacc_update": "2026-03-15",
  "last_financial_update": "2025-12-31",
  "data_completeness_score": 0.84
}
```

This helps both the defense and the frontend.

---

## 7. MongoDB Serving Strategy Needs Clearer Collection Design

### Weak Point

The report correctly says MongoDB should not store all raw historical data. It should serve compact documents.

This is a strong architectural choice.

However, the report does not show the actual shape of those documents.

### Possible Attack Questions

```text
What exactly is stored in MongoDB?
How do you avoid duplication?
How do you update predictions?
```

### Improvement

Add example collections:

```text
companies
company_profiles
company_events_summary
company_predictions
ingestion_jobs
pipeline_runs
```

Add an example document:

```json
{
  "siren": "123456789",
  "identity": {},
  "latest_prediction": {
    "continuity_risk_score": 0.72,
    "risk_level": "High",
    "prediction_date": "2025-12-31",
    "model_version": "v1"
  },
  "data_freshness": {
    "insee": "2026-03-01",
    "bodacc": "2026-03-15"
  }
}
```

This makes the serving part more concrete.

---

## 8. The Academic Contribution Could Be Sharper

### Weak Point

The report says the contribution is a full data-to-ML platform.

That is good, but it can be phrased more academically.

### Current Idea

```text
We built a data pipeline and ML-ready platform.
```

### Stronger Version

```text
The contribution is a reproducible temporal data architecture for transforming heterogeneous French public company data into company-year risk features and future 12-month continuity labels, while separating analytical processing from operational serving.
```

This sounds more like a PFE defense.

---

## 9. No Clear Comparison With Existing Platforms

### Weak Point

The report mentions company profiles and intelligence, but it does not clearly compare the project to platforms like:

- société.com;
- Pappers;
- Infogreffe-style services;
- commercial risk platforms.

### Possible Attack Question

```text
What makes your platform different from existing company search websites?
```

### Better Defense

```text
Existing platforms mostly display company information.
This project combines public source integration, temporal feature engineering, and ML-based continuity-risk prediction.
The added value is not just showing data, but transforming historical signals into risk indicators.
```

This should be added to the report.

---

## 10. “Financial Weakness Risk Label” May Be Hard to Define

### Weak Point

The report lists:

```text
financial_weakness_risk_12m_label
```

But financial weakness is not an official event like liquidation or radiation.

It needs a precise rule.

### Possible Attack Question

```text
What exactly counts as future financial weakness?
```

### Improvement

Define it clearly:

```text
financial_weakness_risk_12m_label = 1 if, in the next fiscal year, the company shows one or more of:

- negative equity;
- negative net result;
- strong revenue decline;
- high debt-to-assets ratio;
- repeated financial losses.
```

But be careful: this is not the same type of label as BODACC legal events.

It is a derived financial condition, not an official status.

---

# Part 2 — Short Summary of Report Weaknesses and Fixes

| Weak Point | Why It Is a Problem | How to Improve or Fix It |
|---|---|---|
| Project not fully proven yet | The report explains the architecture well, but final ML results are not shown yet. | Add final dataset stats, train/test split, model metrics, confusion matrix, and threshold analysis once ready. |
| Target is too broad | “Continuity risk” mixes closure, radiation, legal distress, and inactivity. | Clearly define the main target and separate secondary risks: legal risk, radiation risk, financial weakness, filing anomaly. |
| Financial missing data risk | Missing financial statements may be normal, not necessarily a bad signal. | Add missingness indicators and explain that missing financial data is not automatically treated as negative. |
| Leakage control is explained but not proven | Saying “we avoid future data” is not enough for defense. | Add validation checks proving features use dates ≤ prediction date and labels use dates after prediction date. |
| Model evaluation is still generic | Metrics are mentioned, but no clear success criterion or business threshold is defined. | Explain how you choose the alert threshold based on false positives vs false negatives. |
| Source freshness not clear enough | Different sources update at different times, so profiles may be outdated. | Add source freshness fields: last INSEE update, last INPI update, last BODACC update, last financial update. |
| MongoDB serving design is not concrete enough | The report says MongoDB stores compact serving documents, but not exactly what. | Add example collections and one example MongoDB document. |
| Academic contribution could be sharper | The contribution is good, but it can sound like “we just made a pipeline.” | Rephrase contribution as a temporal, reproducible, multi-source risk-prediction architecture. |
| No comparison with existing platforms | Jury may ask what makes this different from société.com or Pappers. | Add a section explaining that your platform adds ML-based future risk prediction, not only company display. |
| Financial weakness label is vague | Unlike radiation or liquidation, financial weakness is not an official event. | Define exact rules: negative equity, repeated losses, strong revenue decline, high debt/assets, etc. |

---

## Most Important Fixes for the Report

Focus first on these:

```text
1. Add a “Limitations and Improvements” section.
2. Add dataset statistics.
3. Add leakage validation proof.
4. Clarify the target.
5. Add model evaluation plan or results.
6. Add frontend/platform value.
```

The best strategy is not to hide the weaknesses.

Instead, add them as controlled limitations with solutions.  
That makes the report look more serious and defensible.

---

# Part 3 — Weak Points in the Actual Project / Work

This section focuses on the project itself, not the report.

The project is strong in architecture and ambition, but the dangerous part is data validity, not coding.

The real question is not:

```text
Can we train a model?
```

Yes, we can.

The real question is:

```text
Are the features historically correct, leakage-free, complete enough, and meaningful?
```

That is what will decide whether the project is genuinely strong or only technically impressive.

---

# 1. The Project Is Still Mostly a Data Platform, Not Yet a Proven ML Product

## Weak Point

Right now, the strongest part of the project is the architecture:

- source collection;
- data lake;
- Parquet storage;
- MongoDB serving;
- FastAPI backend;
- Colab execution;
- feature generation.

However, the prediction system is not fully validated yet.

## Why This Is a Problem

A technical reviewer, supervisor, or jury member could say:

```text
You built the pipeline, but where is the proof that the model predicts well?
```

Without final model results, the project looks more like a data engineering platform than a complete intelligent predictive system.

## How to Improve or Fix It

Add a final experimental phase containing:

```text
- final dataset size
- number of companies
- number of company-year rows
- number of positive risk labels
- number of negative labels
- train/test years
- model results
- confusion matrix
- threshold analysis
- feature importance
- example predictions
```

This will prove that the pipeline does not only work technically, but also produces useful predictive signals.

---

# 2. The Target May Be Too Broad

## Weak Point

The objective is to predict whether a company may:

- become inactive;
- close;
- be radiated;
- enter serious legal distress;
- show continuity risk within 12 months.

This is useful, but it mixes several different realities.

For example:

```text
radiation ≠ liquidation
inactive company ≠ bankrupt company
cessation volontaire ≠ financial distress
redressement judiciaire ≠ simple administrative closure
```

## Why This Is a Problem

The model may learn a confused target.

It may predict that “something bad or administrative happens,” but without clearly distinguishing what type of risk it is.

## How to Improve or Fix It

Keep one global score, but separate the risk types:

```text
continuity_risk_12m
legal_distress_risk_12m
radiation_risk_12m
administrative_inactivity_risk_12m
financial_weakness_risk_12m
```

Then the frontend can display something like:

```text
Global continuity risk: 72%
Main reason: legal distress signals
Secondary reason: delayed filings
```

This is stronger than one vague risk score.

---

# 3. Historical Data Coverage Is Probably the Biggest Technical Danger

## Weak Point

The project uses company-year modeling:

```text
one row = one company observed at one prediction year
```

This is the correct design.

However, the dangerous question is:

```text
Do we really have historical snapshots for each year, or only current snapshots plus historical event dates?
```

For example, an INSEE current file may describe the company’s current identity or administrative status, not necessarily its exact state in 2020, 2021, or 2022.

## Why This Is a Problem

You may accidentally create fake historical rows using today’s company information.

That would make the dataset look temporal, but it would not be truly historical.

## How to Improve or Fix It

For every source, classify fields into four categories:

```text
A. truly historical fields
B. current snapshot fields
C. event-based fields with dates
D. fields that cannot safely be backfilled
```

Example:

```text
Safe for 2021 feature:
- BODACC events before 2021-12-31
- INPI formalities before 2021-12-31
- financial statement for fiscal year <= 2021

Dangerous for 2021 feature:
- current administrative status from a 2026 INSEE file
- current legal category if it changed after 2021
- current number of establishments if not historically reconstructed
```

This is one of the most important points in the whole project.

---

# 4. Leakage Risk Is Still High

## Weak Point

The correct rule is:

```text
features before prediction date
labels after prediction date
```

But in the actual implementation, leakage can happen silently.

## Examples of Dangerous Leakage

```text
Using dateRadiation as a feature
Using current administrative status for old prediction years
Using future BODACC events in event counts
Using "days since last event" calculated from today's date instead of prediction date
Using full financial history, including years after the prediction year
Using cessation/radiation labels inside feature columns
```

## Why This Is a Problem

The model may produce excellent metrics, but only because it has accidentally seen the future.

This would make the model invalid.

## How to Improve or Fix It

Add automatic leakage tests:

```python
assert max(feature_event_date) <= prediction_date
assert min(label_event_date) > prediction_date
```

Also create a forbidden columns list:

```text
date_radiation
date_cessation
future_event_date
etat_actuel if not historical
label columns
target columns
prediction result columns
```

Before training, automatically block these columns.

---

# 5. Financial Data Can Mislead the Model

## Weak Point

Financial data is useful, but many companies do not publish complete accounts.

Missing financial data can mean many different things:

```text
small company not required to publish
confidential accounts
delay
source coverage issue
real inactivity
bad data extraction
```

## Why This Is a Problem

The model may punish companies simply because financial data is missing.

This is dangerous because missing financial data is not always a negative signal.

## How to Improve or Fix It

Do not treat missing financial values as automatically bad.

Instead, create separate features:

```text
has_financial_data
years_since_last_financial_statement
financial_data_confidential
number_of_financial_years_available
latest_financial_year
```

This helps the model distinguish between:

```text
company has bad financials
```

and:

```text
financials are unavailable
```

This difference is very important.

---

# 6. BODACC Events May Be Both Features and Labels

## Weak Point

BODACC is one of the most important sources because it contains official legal announcements.

However, it can create a subtle modeling problem:

- past BODACC events are features;
- future BODACC events are labels.

This is correct only if dates are handled perfectly.

## Why This Is a Problem

If the same event family is used incorrectly, the model may detect companies already in distress instead of predicting future distress.

## How to Improve or Fix It

Separate clearly:

```text
BODACC before prediction date = history feature
BODACC after prediction date = label
```

Also separate event types:

```text
past account deposit event = feature
future liquidation event = label
past liquidation event = maybe exclude or special case
```

If a company already had liquidation before the prediction date, predicting liquidation again may not make sense.

---

# 7. Company-Year Dataset May Create Duplicate-Like Rows

## Weak Point

Company-year modeling is correct, but it can create many similar rows for the same company:

```text
Company A 2020
Company A 2021
Company A 2022
Company A 2023
```

These rows may be very similar.

## Why This Is a Problem

If you use a random split, the same company can appear in both train and test.

This can make the model look better than it really is.

## How to Improve or Fix It

For final validation, use:

```text
Train: older years
Test: latest year
```

Even better, also test with a company-group split:

```text
The same company should not appear in both train and test.
```

Best final validation:

```text
Temporal split + no future leakage + company-level sanity checks
```

---

# 8. The Project Needs a Stronger Data Quality Layer

## Weak Point

The project has a readiness checker, which is good.

However, for a project this large, you need more aggressive data quality checks.

## Why This Is a Problem

You may train on:

- broken joins;
- missing source coverage;
- duplicate rows;
- wrong dates;
- invalid SIREN values;
- incomplete labels;
- future data inside features.

## How to Improve or Fix It

Add checks like:

```text
% valid SIREN
% companies matched between INSEE and BODACC
% companies matched between INSEE and INPI
% companies with financial data
% rows with prediction_year
% labels by year
% positive labels by year
duplicate company-year rows
date ranges per source
future dates inside features
```

You should produce a data quality report before training.

---

# 9. MongoDB Serving Is Good, But It Can Become Messy

## Weak Point

The decision to keep heavy historical data in Parquet and use MongoDB only for compact serving documents is good.

The danger is implementation.

## Why This Is a Problem

MongoDB can become messy if raw INPI, BODACC, and financial records are dumped into it without a clear serving strategy.

## How to Improve or Fix It

Keep MongoDB for:

```text
company profile summary
latest prediction
risk explanation
source freshness
job status
frontend-ready documents
```

Do not use MongoDB as the full historical analytical database.

Example of a good MongoDB serving document:

```json
{
  "siren": "123456789",
  "company_name": "...",
  "risk_score": 0.72,
  "risk_level": "High",
  "main_risk_factors": [
    "recent legal event",
    "late account filing",
    "negative equity"
  ],
  "prediction_date": "2025-12-31",
  "model_version": "v1",
  "source_freshness": {
    "insee": "2026-03-01",
    "bodacc": "2026-03-15",
    "inpi": "2026-03-10",
    "financials": "2025-12-31"
  }
}
```

---

# 10. Explainability Is Not Solved Yet

## Weak Point

The system aims to provide explanations and recommended actions.

This is one of the hardest parts of the project.

## Why This Is a Problem

If the model outputs only:

```text
risk_score = 0.81
```

the platform is not very useful.

But if explanations are generated incorrectly, the system may say things that are not supported by the model.

## How to Improve or Fix It

Use a structured explanation system:

```text
1. model score
2. top contributing features
3. source evidence
4. human-readable explanation
5. cautious recommended action
```

Example:

```text
Risk score: 78%

Main factors:
- 2 legal-risk BODACC events in last 12 months
- no recent account filing
- negative equity in latest available financial statement

Recommended action:
Review legal announcements and request updated financial documents before engagement.
```

Do not let an LLM invent explanations.

The explanation must come from:

```text
model features + source evidence
```

---

# 11. The Baseline Model May Be Too Weak for Final Performance

## Weak Point

Logistic regression is a good first baseline, but the final risk model may require more powerful models.

Company risk probably has nonlinear patterns.

Example:

```text
young company + no financials = normal
old company + no filings + recent legal event = risky
```

Logistic regression may not capture these interactions well.

## How to Improve or Fix It

Use logistic regression as a baseline, then compare with:

```text
LightGBM
XGBoost
CatBoost
Random Forest
calibrated gradient boosting
```

Do not jump directly to complex models before validating the dataset.

---

# 12. Probability Calibration Is Needed

## Weak Point

For a risk platform, the probability must mean something.

If the model says:

```text
risk = 80%
```

that should roughly mean:

```text
Among similar companies, around 80% had a continuity-risk event.
```

Many ML models give badly calibrated probabilities.

## Why This Is a Problem

The score may look precise but not be reliable.

## How to Improve or Fix It

After training, test calibration using:

```text
calibration curve
Brier score
reliability diagram
```

Then use calibration methods such as:

```text
Platt scaling
isotonic calibration
CalibratedClassifierCV
```

This is very important for a risk score.

---

# 13. Class Imbalance Can Make Results Misleading

## Weak Point

Continuity-risk events are probably rare.

If 95% of companies are normal and 5% are risky, a model can get high accuracy by predicting “normal” for everyone.

Example:

```text
95% active
5% risky

A dumb model predicts "active" for everyone.
Accuracy = 95%
But it detects 0 risky companies.
```

## How to Improve or Fix It

Use metrics such as:

```text
precision
recall
F1
average precision
PR-AUC
confusion matrix
recall at fixed precision
precision at top K%
```

For business use, top-K risk ranking may be very useful:

```text
Among the top 5% highest-risk companies, how many actually had events?
```

---

# 14. The Platform Value Must Be Separated from the ML Value

## Weak Point

The project contains two different products:

```text
1. company intelligence platform
2. ML risk prediction system
```

Both are valuable, but they should not be confused.

## Why This Is a Problem

If the ML is not ready, people may think the whole project is weak.

## How to Improve or Fix It

Defend the project in layers:

```text
Layer 1: data collection and normalization
Layer 2: company profile and search platform
Layer 3: historical event monitoring
Layer 4: ML feature generation
Layer 5: risk prediction
Layer 6: explanation and recommendation
```

Even if the ML is still baseline, the platform still has value.

---

# Part 4 — Most Serious Weaknesses to Fix First

## Priority 1 — Historical Correctness

Make sure your company-year rows are real and not fake historical snapshots.

For every feature, ask:

```text
Was this value truly known at prediction_year?
```

If not, remove it or mark it as current-only.

---

## Priority 2 — Leakage Prevention

Add automatic checks that block future information from features.

This is non-negotiable. Leakage can destroy the whole ML validity.

---

## Priority 3 — Data Coverage Report

Before training, produce a report showing:

```text
source coverage
matched companies
missing values
labels per year
positive class ratio
duplicates
date ranges
```

This tells you whether the dataset is actually usable.

---

## Priority 4 — Clear Target Definition

Decide exactly what the main prediction means:

```text
continuity risk = legal distress OR radiation OR administrative closure within 12 months
```

Then keep secondary risk scores separate.

---

## Priority 5 — Final Evaluation Protocol

Use temporal split and report:

```text
ROC-AUC
PR-AUC
precision
recall
F1
confusion matrix
threshold
calibration
top-K risk performance
```

---

# Part 5 — Final Judgment

The project is strong in architecture and ambition.

However, the dangerous part is data validity, not coding.

The main question is not:

```text
Can we train a model?
```

Yes, we can.

The real question is:

```text
Are the features historically correct, leakage-free, complete enough, and meaningful?
```

That is what will decide whether the project is genuinely strong or only technically impressive.

The project’s biggest weaknesses are:

```text
1. incomplete source coverage
2. possible fake historical reconstruction
3. leakage risk
4. vague target definition
5. missing final ML validation
6. financial missingness ambiguity
7. weak explainability if not grounded in features
```

If these points are fixed, the project becomes much more defensible, professional, and credible.

---

# Part 6 — Recommended Next Actions

## Immediate Actions

```text
1. Build a data quality report.
2. Classify every feature as historical, current snapshot, event-based, or unsafe.
3. Add leakage tests before training.
4. Define the main target and secondary labels clearly.
5. Build one clean baseline evaluation with temporal split.
```

## After That

```text
1. Add calibration analysis.
2. Add top-K risk evaluation.
3. Add SHAP or feature contribution explanations.
4. Add MongoDB serving document examples.
5. Add source freshness tracking.
6. Add frontend explanation format.
```

## Final Goal

The final system should be able to produce:

```text
- a company profile;
- a source freshness summary;
- a continuity-risk score;
- separate legal, financial, registry, and administrative risk indicators;
- top reasons for the score;
- source evidence supporting the explanation;
- cautious recommended actions;
- model version and prediction date.
```
