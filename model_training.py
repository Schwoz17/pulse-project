"""
PULSE -- Model Training (offline)

Trains the Isolation Forest once on the existing synthetic feature set
and saves everything the live API needs to score new sessions in real
time: the model, the feature column order, and the population-level
cadence/duration stats used as the cold-start fallback.

Run this once (or whenever features.csv changes) before starting api.py.
"""

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURE_COLS = [
    "z_cadence_mean", "z_cadence_std", "z_session_duration",
    "sequence_entropy", "hour_deviation", "device_change_flag", "network_change_flag",
]


def raw_metrics(session):
    intervals = session["keystroke_intervals"]
    return {
        "cadence_mean": float(np.mean(intervals)),
        "cadence_std": float(np.std(intervals)),
        "session_duration_sec": float(session["session_duration_sec"]),
    }


def main():
    df = pd.read_csv("features.csv")
    df_warm = df[df["is_cold_start"] == 0]

    X = df_warm[FEATURE_COLS].values
    contamination = df_warm["label"].mean()
    model = IsolationForest(contamination=contamination, random_state=42)
    model.fit(X)

    # The bounds of the training scores -- needed to rescale a single
    # live session into a comparable 0-1 range. Min-max normalizing one
    # new point against itself is meaningless; it needs the same
    # reference frame the batch pipeline used.
    train_raw_scores = -model.decision_function(X)
    score_min = float(train_raw_scores.min())
    score_max = float(train_raw_scores.max())

    with open("raw_sessions.json") as f:
        sessions = json.load(f)
    all_metrics = [raw_metrics(s) for s in sessions]
    keys = ["cadence_mean", "cadence_std", "session_duration_sec"]
    pop_mean = {k: float(np.mean([m[k] for m in all_metrics])) for k in keys}
    pop_std = {k: float(np.std([m[k] for m in all_metrics])) for k in keys}

    bundle = {
        "model": model,
        "feature_cols": FEATURE_COLS,
        "pop_mean": pop_mean,
        "pop_std": pop_std,
        "score_min": score_min,
        "score_max": score_max,
    }
    joblib.dump(bundle, "model_bundle.joblib")
    print(f"Trained on {len(df_warm)} warm sessions.")
    print("Saved model_bundle.joblib")


if __name__ == "__main__":
    main()
