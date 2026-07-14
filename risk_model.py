"""
PULSE -- Risk Scoring Model

Two tiers, not one:

  - Warm sessions (a user has at least MIN_HISTORY prior sessions):
    full Isolation Forest over personalized z-scored behavioral
    features, same as before.
  - Cold-start sessions (a new user, or one still building history):
    z-scores against a personal baseline don't mean anything yet, so
    the model doesn't get to see them. Risk is decided by device and
    network fingerprint only -- which is closer to how real banking
    apps actually treat brand-new sessions, leaning on device trust
    and step-up auth rather than behavioral pattern-matching they
    don't have data for yet.

A Logistic Regression baseline is still reported on the warm subset,
for the same reason as before: something to point to if asked "why
not just use labels."
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

FEATURE_COLS = [
    "z_cadence_mean", "z_cadence_std", "z_session_duration",
    "sequence_entropy", "hour_deviation", "device_change_flag", "network_change_flag",
]

COLD_START_RISK_IF_FLAGGED = 0.85   # device or network changed during cold start
COLD_START_RISK_IF_CLEAN = 0.3      # no external flag, but still no behavioral history


def min_max(x):
    x = np.asarray(x, dtype=float)
    return (x - x.min()) / (x.max() - x.min() + 1e-9)


def score_warm(df_warm):
    X = df_warm[FEATURE_COLS].values
    contamination = df_warm["label"].mean()  # known here because it's synthetic --
    # in production this is a fixed assumption, not read from ground truth
    model = IsolationForest(contamination=contamination, random_state=42)
    model.fit(X)

    raw_scores = -model.decision_function(X)
    risk_score = min_max(raw_scores)
    predicted = (model.predict(X) == -1).astype(int)
    return risk_score, predicted


def score_cold_start(df_cold):
    flagged = (df_cold["device_change_flag"] == 1) | (df_cold["network_change_flag"] == 1)
    risk_score = np.where(flagged, COLD_START_RISK_IF_FLAGGED, COLD_START_RISK_IF_CLEAN)
    predicted = (risk_score >= 0.5).astype(int)
    return risk_score, predicted


def run_logistic_baseline(df_warm):
    X = df_warm[FEATURE_COLS].values
    y = df_warm["label"].values
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    return y_test, y_pred, y_prob


def report(name, y_true, y_pred, y_score=None):
    print(f"\n--- {name} ---")
    print(f"n:         {len(y_true)}")
    print(f"Precision: {precision_score(y_true, y_pred, zero_division=0):.3f}")
    print(f"Recall:    {recall_score(y_true, y_pred, zero_division=0):.3f}")
    print(f"F1:        {f1_score(y_true, y_pred, zero_division=0):.3f}")
    if y_score is not None and len(set(y_true)) > 1:
        print(f"ROC-AUC:   {roc_auc_score(y_true, y_score):.3f}")


def main():
    df = pd.read_csv("features.csv")
    df_warm = df[df["is_cold_start"] == 0].copy()
    df_cold = df[df["is_cold_start"] == 1].copy()

    warm_score, warm_pred = score_warm(df_warm)
    df_warm["risk_score"] = warm_score
    df_warm["predicted_anomaly"] = warm_pred
    report("Warm sessions -- Isolation Forest", df_warm["label"], warm_pred, warm_score)

    cold_score, cold_pred = score_cold_start(df_cold)
    df_cold["risk_score"] = cold_score
    df_cold["predicted_anomaly"] = cold_pred
    report("Cold-start sessions -- device/network rule", df_cold["label"], cold_pred, cold_score)

    combined = pd.concat([df_warm, df_cold], ignore_index=True)
    report("Combined (warm + cold-start)", combined["label"], combined["predicted_anomaly"], combined["risk_score"])

    y_test, y_pred, y_prob = run_logistic_baseline(df_warm)
    report("Logistic Regression baseline (warm subset only)", y_test, y_pred, y_prob)

    combined[["session_id", "user_id", "is_cold_start", "label", "risk_score", "predicted_anomaly"]].to_csv(
        "risk_scores.csv", index=False
    )
    print("\nWrote risk_scores.csv")


if __name__ == "__main__":
    main()
