"""
PULSE -- Synthetic Behavioral Session Generator

Generates raw per-session behavioral events for simulated bank users,
with a configurable fraction of sessions deliberately corrupted to look
like anomalous (potential fraud) activity. This is training/eval data
for the Risk Scoring Model -- no real user data is used anywhere here.
"""

import json
import random
import string
import numpy as np

random.seed(42)
np.random.seed(42)

NUM_USERS = 40
SESSIONS_PER_USER = 25
ANOMALY_RATE = 0.15
KEYSTROKES_PER_SESSION = 40

SCREEN_STEPS = ["login", "dashboard", "balance", "transfer", "confirm", "logout"]


def random_hash(n=12):
    return "".join(random.choices(string.hexdigits.lower(), k=n))


def make_user_baseline(user_id):
    return {
        "user_id": user_id,
        "cadence_mean": float(np.random.uniform(120, 220)),   # ms between keystrokes
        "cadence_std": float(np.random.uniform(15, 35)),
        "duration_mean": float(np.random.uniform(60, 240)),   # seconds
        "duration_std": float(np.random.uniform(10, 40)),
        "typical_hour": float(np.random.uniform(6, 23)),
        "device_hash": random_hash(),
        "network_type": random.choice(["wifi_home", "mobile_data"]),
    }


def normal_screen_sequence():
    seq = SCREEN_STEPS.copy()
    if random.random() < 0.3:
        seq.insert(2, "settings")  # occasional detour -- still low-entropy
    return seq


def anomalous_screen_sequence():
    pool = SCREEN_STEPS + ["settings", "beneficiary_add", "limit_change"]
    length = random.randint(3, 6)
    return random.sample(pool, k=min(length, len(pool)))


def generate_session(baseline, session_idx):
    is_anomaly = random.random() < ANOMALY_RATE
    cadence_mean, cadence_std = baseline["cadence_mean"], baseline["cadence_std"]
    duration_mean, duration_std = baseline["duration_mean"], baseline["duration_std"]
    hour = float(np.random.normal(baseline["typical_hour"], 1.5) % 24)
    device_hash = baseline["device_hash"]
    network_type = baseline["network_type"]
    screen_sequence = normal_screen_sequence()

    if is_anomaly:
        # apply 1-3 corruption types, not all of them every time --
        # real attacks don't trip every signal at once
        corruptions = random.sample(
            ["cadence", "hour", "device", "network", "sequence"],
            k=random.randint(1, 3),
        )
        if "cadence" in corruptions:
            direction = random.choice([0.5, 1.8])
            cadence_mean = cadence_mean * direction
            cadence_std = cadence_std * 1.8
        if "hour" in corruptions:
            hour = (baseline["typical_hour"] + random.uniform(8, 14)) % 24
        if "device" in corruptions:
            device_hash = random_hash()
        if "network" in corruptions:
            network_type = "mobile_data" if network_type == "wifi_home" else "wifi_home"
        if "sequence" in corruptions:
            screen_sequence = anomalous_screen_sequence()

    keystroke_intervals = list(np.clip(
        np.random.normal(cadence_mean, cadence_std, KEYSTROKES_PER_SESSION), 40, None
    ))
    session_duration = max(15.0, float(np.random.normal(duration_mean, duration_std)))

    return {
        "session_id": f"{baseline['user_id']}_s{session_idx}",
        "user_id": baseline["user_id"],
        "hour_of_day": round(hour, 2),
        "keystroke_intervals": [round(float(x), 1) for x in keystroke_intervals],
        "session_duration_sec": round(session_duration, 1),
        "screen_sequence": screen_sequence,
        "device_hash": device_hash,
        "network_type": network_type,
        "label": int(is_anomaly),  # ground truth, for evaluation only -- never a model input
    }


def main():
    users = [make_user_baseline(f"user_{i:03d}") for i in range(NUM_USERS)]
    baselines_by_user = {u["user_id"]: u for u in users}

    sessions = []
    for user in users:
        for i in range(SESSIONS_PER_USER):
            sessions.append(generate_session(user, i))

    with open("raw_sessions.json", "w") as f:
        json.dump(sessions, f, indent=2)

    with open("user_baselines.json", "w") as f:
        json.dump(baselines_by_user, f, indent=2)

    n_anom = sum(s["label"] for s in sessions)
    print(f"Generated {len(sessions)} sessions across {NUM_USERS} users.")
    print(f"Anomalous sessions: {n_anom} ({n_anom/len(sessions):.1%})")
    print("Wrote raw_sessions.json and user_baselines.json")


if __name__ == "__main__":
    main()
