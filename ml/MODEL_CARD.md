# Upset Tracker Model Card

## Model

- Name: Upset Tracker
- Version: `v1.0`
- Artifact: `ml/models/upset_tracker_v1.0.joblib`
- Model family: XGBoost binary classifier

## Features

The model uses pre-computed columns from `mart_upset_features`:

- `ranking_delta`
- `is_cross_region`
- `team_a_ranking`
- `team_b_ranking`

## Evaluation

Training uses a temporal split: rows are sorted by `played_at`; the oldest 60% train the
model, the next 20% select the decision threshold, and the newest 20% are reserved as the
holdout set. The training command writes:

- `ml/evaluation/metrics.json`
- `ml/evaluation/roc_auc.txt`
- `ml/evaluation/decision_threshold.txt`
- `ml/evaluation/calibration_curve.png`
- `ml/evaluation/confusion_matrix.png`

Current local training on the CS API-backed mart uses a validation-selected F0.75 threshold
of `0.3841`, capped so validation predictions cannot exceed the validation upset base rate.
On the newest temporal holdout, it reports ROC-AUC `0.7258`, upset precision `0.4370`,
upset recall `0.4522`, and a predicted upset rate of `0.2604` versus an actual upset rate
of `0.2516`.

## Explainability

Prediction-time explanations use `shap.TreeExplainer`. The dashboard can compute SHAP values
for a single upcoming match and optionally persist those values as Parquet under `ml/shap/`.
Use the saved decision threshold for binary upset flags; calling the raw XGBoost
`model.predict()` method will use the default `0.5` cutoff and miss most upsets.

## Known Limitations

- The model is now a pre-match predictor: it intentionally excludes final-score columns such
  as `score_diff`, `total_rounds`, and `is_overtime`.
- The selected threshold is balanced and slightly conservative: it avoids over-alerting above
  the validation upset base rate, so it will miss more upsets than the recall-heavy threshold.
- Ranking features must represent what was known before each match. If an upstream mart joins
  old matches to today's rankings, the model can still receive softer ranking leakage.
- Model quality depends on populated team rankings; unranked teams are filled with `-1` in the
  feature matrix.
- The current warehouse does not contain true halftime score events, so Choke/Clutch comeback
  metrics use available final-score pressure proxies.
- The current warehouse does not contain bracket-position facts, so elimination-match win
  percentages are explicitly unavailable until tournament bracket data is persisted.
