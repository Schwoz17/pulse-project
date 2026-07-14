"""
PULSE -- Synthetic Transaction & Balance-Check Generator

Generates two months of simulated account activity per user: a daily
balance history, and a sparser stream of balance-check events (the user
opening the app to look at their balance). This is what the
Personalization Engine learns a "financial rhythm" from -- a separate
signal from the behavioral session data used for the Risk Scoring Model.
One is about how someone transacts, the other is about how someone types.
"""

import json
import random
import numpy as np

random.seed(7)
np.random.seed(7)

NUM_USERS = 40
NUM_DAYS = 60  # roughly two months


def make_finance_baseline(user_id):
    return {
        "user_id": user_id,
        "monthly_income": float(np.random.uniform(80000, 300000)),
        "rent_amount": float(np.random.uniform(30000, 120000)),
        "rent_due_day_of_month": int(np.random.randint(20, 29)),
        "daily_spend_mean": float(np.random.uniform(500, 3000)),
        "preferred_check_dow": int(np.random.randint(0, 7)),  # 0 = Monday
        "preferred_check_hour": float(np.random.uniform(17, 22)),  # evenings, mostly
        "check_probability": float(np.random.uniform(0.4, 0.9)),
    }


def simulate_user(baseline):
    balance = baseline["monthly_income"]
    daily_balances = []
    checks = []

    for day in range(NUM_DAYS):
        day_of_month = day % 30
        if day_of_month == 0:
            balance += baseline["monthly_income"]
        if day_of_month == baseline["rent_due_day_of_month"]:
            balance -= baseline["rent_amount"]

        spend = max(0.0, float(np.random.normal(
            baseline["daily_spend_mean"], baseline["daily_spend_mean"] * 0.4
        )))
        balance -= spend
        daily_balances.append({"day": day, "balance": round(balance, 2)})

        dow = day % 7
        if dow == baseline["preferred_check_dow"] and random.random() < baseline["check_probability"]:
            hour = float(np.clip(np.random.normal(baseline["preferred_check_hour"], 1.0), 0, 23))
            checks.append({
                "user_id": baseline["user_id"],
                "day": day,
                "hour": round(hour, 1),
                "balance_at_check": round(balance, 2),
            })

    return daily_balances, checks


def main():
    users = [make_finance_baseline(f"user_{i:03d}") for i in range(NUM_USERS)]

    all_balances = {}
    all_checks = []
    for baseline in users:
        balances, checks = simulate_user(baseline)
        all_balances[baseline["user_id"]] = balances
        all_checks.extend(checks)

    with open("daily_balances.json", "w") as f:
        json.dump(all_balances, f, indent=2)
    with open("balance_checks.json", "w") as f:
        json.dump(all_checks, f, indent=2)
    with open("finance_baselines.json", "w") as f:
        json.dump({u["user_id"]: u for u in users}, f, indent=2)

    print(f"Simulated {NUM_USERS} users over {NUM_DAYS} days.")
    print(f"Total balance-check events: {len(all_checks)}")
    print("Wrote daily_balances.json, balance_checks.json, finance_baselines.json")


if __name__ == "__main__":
    main()
