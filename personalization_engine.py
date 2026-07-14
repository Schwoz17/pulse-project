"""
PULSE -- Personalization Engine

Learns two things per user from the transaction / balance-check data:

  1. An archetype, via K-Means clustering on *observed* check timing --
     not the hidden generator parameters, since in production we'd only
     ever see behavior, never the ground truth.
  2. A shortfall projection -- whether the user's balance is on track to
     cover their next recurring big payment, inferred from the pattern
     of the balance history itself, not hardcoded as "rent."

Both feed the Nudge Generator. Neither is a deep model, and that's
intentional: the clustering exists to produce a human-readable label for
the pitch, and the shortfall estimate is a straightforward heuristic over
recent spending, not a trained model. Worth saying plainly rather than
dressing a heuristic up as more than it is.
"""

import json
from collections import Counter, defaultdict

import numpy as np
from sklearn.cluster import KMeans

TODAY = 50  # simulated "current day" -- day_of_month = 20, close enough to
            # most rent-due windows (20-28) to make the projection meaningful


def build_user_check_features(checks_by_user):
    """Derive preferred day/hour and check frequency from observed events only."""
    features = {}
    for user_id, checks in checks_by_user.items():
        if not checks:
            continue
        days = [c["day"] % 7 for c in checks]
        hours = [c["hour"] for c in checks]
        preferred_day = Counter(days).most_common(1)[0][0]
        features[user_id] = {
            "preferred_check_day": preferred_day,
            "preferred_check_hour": float(np.mean(hours)),
            "check_count": len(checks),
        }
    return features


def cluster_archetypes(features):
    user_ids = list(features.keys())
    X = np.array([
        [
            np.sin(2 * np.pi * features[u]["preferred_check_day"] / 7),
            np.cos(2 * np.pi * features[u]["preferred_check_day"] / 7),
            features[u]["preferred_check_hour"] / 23.0,
            features[u]["check_count"],
        ]
        for u in user_ids
    ])

    k = 3
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    # Name clusters by RELATIVE ranking against each other, not absolute
    # thresholds. The original checked `avg_day >= 5` -- but with
    # preferred_check_dow random per user, no cluster is guaranteed to
    # clear that bar. When none did, two clusters fell into the same
    # fallback name, silently collapsing three real clusters into two
    # labels. Ranking guarantees three distinct names, always.
    check_counts_by_cluster = defaultdict(list)
    day_by_cluster = defaultdict(list)
    for u, label in zip(user_ids, labels):
        check_counts_by_cluster[label].append(features[u]["check_count"])
        day_by_cluster[label].append(features[u]["preferred_check_day"])

    cluster_stats = {
        label: {
            "avg_day": float(np.mean(day_by_cluster[label])),
            "avg_checks": float(np.mean(check_counts_by_cluster[label])),
        }
        for label in range(k)
    }

    remaining = set(cluster_stats.keys())
    centroid_names = {}

    weekend_cluster = max(remaining, key=lambda l: cluster_stats[l]["avg_day"])
    centroid_names[weekend_cluster] = "Weekend Planner"
    remaining.discard(weekend_cluster)

    frequent_cluster = max(remaining, key=lambda l: cluster_stats[l]["avg_checks"])
    centroid_names[frequent_cluster] = "Frequent Monitor"
    remaining.discard(frequent_cluster)

    for label in remaining:
        centroid_names[label] = "Low-Engagement Checker"

    return {u: centroid_names[label] for u, label in zip(user_ids, labels)}


def estimate_shortfall(daily_balances):
    """
    Infer the recurring big-drop day (a stand-in for rent) directly from
    the balance history, then project forward from TODAY to see if the
    balance will cover it.
    """
    # Only ever look at data up to TODAY -- using later days to detect the
    # rent-day pattern would be forecasting with information the system
    # can't actually have yet.
    history = daily_balances[:TODAY + 1]

    by_day_of_month = defaultdict(list)
    for i in range(1, len(history)):
        delta = history[i]["balance"] - history[i - 1]["balance"]
        dom = history[i]["day"] % 30
        by_day_of_month[dom].append(delta)

    avg_delta_by_dom = {dom: float(np.mean(deltas)) for dom, deltas in by_day_of_month.items()}
    rent_day = min(avg_delta_by_dom, key=avg_delta_by_dom.get)  # biggest average drop
    rent_estimate = abs(avg_delta_by_dom[rent_day])

    today_dom = TODAY % 30
    days_until_due = (rent_day - today_dom) % 30
    current_balance = history[TODAY]["balance"]

    # Estimate "typical" daily spend from the last 14 days, excluding the
    # known rent day AND trimming the single largest positive/negative
    # delta -- payday spikes and other one-off swings would otherwise
    # drag this average toward "balance is growing" even when it isn't.
    recent = history[TODAY - 14:TODAY]
    recent_deltas = [
        recent[i]["balance"] - recent[i - 1]["balance"]
        for i in range(1, len(recent))
        if recent[i]["day"] % 30 != rent_day
    ]
    if len(recent_deltas) >= 5:
        recent_deltas = sorted(recent_deltas)[1:-1]  # trim one outlier off each end
    avg_daily_change = float(np.mean(recent_deltas)) if recent_deltas else 0.0

    projected_balance = current_balance + avg_daily_change * days_until_due
    shortfall = max(0.0, rent_estimate - projected_balance)

    return {
        "estimated_recurring_amount": round(rent_estimate, 2),
        "days_until_due": int(days_until_due),
        "current_balance": round(current_balance, 2),
        "projected_balance": round(projected_balance, 2),
        "shortfall_amount": round(shortfall, 2),
    }


def main():
    with open("balance_checks.json") as f:
        checks = json.load(f)
    with open("daily_balances.json") as f:
        daily_balances = json.load(f)

    checks_by_user = defaultdict(list)
    for c in checks:
        checks_by_user[c["user_id"]].append(c)

    check_features = build_user_check_features(checks_by_user)
    archetypes = cluster_archetypes(check_features)

    profiles = []
    for user_id, feats in check_features.items():
        shortfall_info = estimate_shortfall(daily_balances[user_id])
        profiles.append({
            "user_id": user_id,
            "archetype": archetypes[user_id],
            "preferred_check_day": feats["preferred_check_day"],
            "preferred_check_hour": round(feats["preferred_check_hour"], 1),
            **shortfall_info,
        })

    with open("personalization_profiles.json", "w") as f:
        json.dump(profiles, f, indent=2)

    at_risk = sum(1 for p in profiles if p["shortfall_amount"] > 0)
    print(f"Built {len(profiles)} personalization profiles.")
    print(f"Users projected short before their next recurring payment: {at_risk}")
    print("Wrote personalization_profiles.json")


if __name__ == "__main__":
    main()
