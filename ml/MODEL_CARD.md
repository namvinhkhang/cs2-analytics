# Upset Tracker Model Card

## Model

- Name: Upset Tracker
- Version: `v1.0`
- Artifact: `ml/models/upset_tracker_v1.0.joblib`
- Model family: XGBoost binary classifier

## Features

The model uses pre-computed columns from `mart_upset_features`:

- `ranking_delta`
- `score_diff`
- `total_rounds`
- `is_overtime`
- `is_cross_region`
- `team_a_ranking`
- `team_b_ranking`

## Evaluation

Training uses a temporal split: rows are sorted by `played_at`, and the newest 20% of matches
are reserved as the holdout set. The training command writes:

- `ml/evaluation/metrics.json`
- `ml/evaluation/roc_auc.txt`
- `ml/evaluation/calibration_curve.png`
- `ml/evaluation/confusion_matrix.png`

## Explainability

Prediction-time explanations use `shap.TreeExplainer`. The dashboard can compute SHAP values
for a single upcoming match and optionally persist those values as Parquet under `ml/shap/`.

## Known Limitations

- Model quality depends on populated team rankings; unranked teams are filled with `-1` in the
  feature matrix.
- The current warehouse does not contain true halftime score events, so Choke/Clutch comeback
  metrics use available final-score pressure proxies.
- The current warehouse does not contain bracket-position facts, so elimination-match win
  percentages are explicitly unavailable until tournament bracket data is persisted.
