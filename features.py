"""
PULSE -- Feature Engineering Pipeline

Converts raw per-session behavioral events into the fixed feature vector
that both the Risk Scoring Model and the Personalization Engine read from.
This is the shared contract between the ML side and Backend -- if the
schema here changes, Backend's API payload needs to change with it.

Cadence and session-duration are expressed as z-scores against each
user's OWN prior sessions -- never the current session, never future
ones -- the same discipline used for hour_deviation. A brand-new user
has no prior sessions to compare against, which is the cold-start
problem: the first MIN_HISTORY sessions get flagged with
is_cold_start=1 and fall back to a population-level baseline instead
of a personal one, since there's no personal pattern yet to measure
against.

Known asymmetry, worth stating plainly rather than hiding: hour_deviation,
device_change_flag, and network_change_flag still compare against the
hidden generator baseline (user_baselines.json) rather than something
learned from observed sessions. That's a shortcut carried over from the
original build, not fixed here -- only cadence and duration were in scope
for this change. Fixing the rest would mean hour/device/network face the
same cold-start problem cadence and duration now correctly face.
"""

import json
import math
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

MIN_HISTORY = 5  # sessions needed before a personal baseline is trusted
EPS = 1e-6


def shannon_entropy(sequence):
    if len(sequence) <= 1:
        return 0.0
    counts = Counter(sequence)
    total = len(sequence)
    probs = [c / total for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs)


def circular_hour_distance(a, b):
    """Shortest distance between two hours on a 24-hour clock."""
    diff = abs(a - b) % 24
    return min(diff, 24 - diff)


def raw_session_metrics(session):
    intervals = session["keystroke_intervals"]
    return {
        "cadence_mean": float(np.mean(intervals)),
        "cadence_std": float(np.std(intervals)),
        "session_duration_sec": float(session["session_duration_sec"]),
    }


def main():
    with open("raw_sessions.json") as f:
        sessions = json.load(f)
    with open("user_baselines.json") as f:
        baselines = json.load(f)

    # Sessions come out of synthetic_data.py already grouped by user, in
    # generation order -- group explicitly here so we're not relying on
    # that being an accident of how the file happens to be written.
    sessions_by_user = defaultdict(list)
    for s in sessions:
        sessions_by_user[s["user_id"]].append(s)

    # Population-level fallback stats, for cold-start sessions that have
    # no personal history yet. Computed once, up front, from the whole
    # dataset -- a real system would build this from its existing
    # customer base, not from any single new user's own timeline.
    all_metrics = [raw_session_metrics(s) for s in sessions]
    pop_mean = {k: float(np.mean([m[k] for m in all_metrics])) for k in all_metrics[0]}
    pop_std = {k: float(np.std([m[k] for m in all_metrics])) for k in all_metrics[0]}

    rows = []
    for user_id, user_sessions in sessions_by_user.items():
        baseline = baselines[user_id]
        history = defaultdict(list)  # this user's own metrics, prior sessions only

        for idx, session in enumerate(user_sessions):
            raw = raw_session_metrics(session)
            is_cold_start = idx < MIN_HISTORY

            z = {}
            for key in ["cadence_mean", "cadence_std", "session_duration_sec"]:
                if is_cold_start or len(history[key]) < MIN_HISTORY:
                    # not enough personal history -- fall back to how this
                    # session compares to the population, not to the user
                    mean_ref, std_ref = pop_mean[key], pop_std[key]
                else:
                    mean_ref = float(np.mean(history[key]))
                    std_ref = float(np.std(history[key]))
                z[key] = (raw[key] - mean_ref) / (std_ref + EPS)

            rows.append({
                "session_id": session["session_id"],
                "user_id": user_id,
                "z_cadence_mean": z["cadence_mean"],
                "z_cadence_std": z["cadence_std"],
                "z_session_duration": z["session_duration_sec"],
                "sequence_entropy": shannon_entropy(session["screen_sequence"]),
                "hour_deviation": circular_hour_distance(session["hour_of_day"], baseline["typical_hour"]),
                "device_change_flag": int(session["device_hash"] != baseline["device_hash"]),
                "network_change_flag": int(session["network_type"] != baseline["network_type"]),
                "is_cold_start": int(is_cold_start),
                "label": session["label"],  # kept for evaluation, dropped before training
            })

            # Only append to history AFTER computing this session's
            # z-score -- a session must never be part of its own baseline.
            for key in ["cadence_mean", "cadence_std", "session_duration_sec"]:
                history[key].append(raw[key])

    df = pd.DataFrame(rows)
    df.to_csv("features.csv", index=False)

    n_cold = df["is_cold_start"].sum()
    print(f"Wrote features.csv -- {len(df)} rows, {df.shape[1]} columns")
    print(f"Cold-start rows: {n_cold} ({n_cold/len(df):.1%})")
    print(df.drop(columns=["session_id", "user_id"]).describe().round(2))


if __name__ == "__main__":
    main()
