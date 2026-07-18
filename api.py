"""
PULSE -- Live API

The one file Backend needs to run. Wraps the risk model, the
personalization profiles, and the risk arbiter behind two HTTP
endpoints, so Backend never has to read or run the individual
pipeline scripts directly -- they call an endpoint, they get JSON back.

Start with:
    uvicorn api:app --reload --port 8000

Requires model_bundle.joblib (run model_training.py once first) and
personalization_profiles.json (already produced by personalization_engine.py)
in the same directory as this file.

Known simplification, stated plainly: per-user history lives in memory
and resets if the server restarts. Fine for a hackathon demo. A real
deployment would persist this in the `sessions` / `behavioral_events`
tables Backend already owns per the technical doc, not in a Python dict.
"""

import json
import math
from collections import defaultdict, Counter
from typing import List, Optional

import joblib
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from risk_arbiter import arbitrate

MIN_HISTORY = 5
EPS = 1e-6
LOW, HIGH = 0.4, 0.7  # borderline band routed to the LLM arbiter

app = FastAPI(title="PULSE API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bundle = joblib.load("model_bundle.joblib")
MODEL = bundle["model"]
FEATURE_COLS = bundle["feature_cols"]
POP_MEAN = bundle["pop_mean"]
POP_STD = bundle["pop_std"]
SCORE_MIN = bundle["score_min"]
SCORE_MAX = bundle["score_max"]

with open("personalization_profiles.json") as f:
    PROFILES = {p["user_id"]: p for p in json.load(f)}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

USER_HISTORY = defaultdict(lambda: {
    "cadence_mean": [], "cadence_std": [], "session_duration_sec": [],
    "device_hash": None, "network_type": None, "typical_hour": None,
})


class SessionEvent(BaseModel):
    user_id: str
    keystroke_intervals: List[float]
    session_duration_sec: float
    screen_sequence: List[str]
    hour_of_day: float
    device_hash: str
    network_type: str
    transaction_amount: Optional[float] = None  # only present if this session is a transfer


def shannon_entropy(sequence):
    if len(sequence) <= 1:
        return 0.0
    counts = Counter(sequence)
    total = len(sequence)
    probs = [c / total for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs)


def circular_hour_distance(a, b):
    diff = abs(a - b) % 24
    return min(diff, 24 - diff)


def score_session(event: SessionEvent):
    hist = USER_HISTORY[event.user_id]
    is_cold_start = len(hist["cadence_mean"]) < MIN_HISTORY

    cadence_mean = float(np.mean(event.keystroke_intervals))
    cadence_std = float(np.std(event.keystroke_intervals))
    duration = event.session_duration_sec

    def z(key, value):
        if is_cold_start:
            return (value - POP_MEAN[key]) / (POP_STD[key] + EPS)
        prior = hist[key]
        # Floor the personal std at 5% of the population std for this
        # feature -- a user with genuinely near-zero session-to-session
        # variance shouldn't turn a trivial difference into an extreme
        # z-score just because the denominator collapsed toward zero.
        std_ref = max(float(np.std(prior)), POP_STD[key] * 0.05)
        return (value - float(np.mean(prior))) / (std_ref + EPS)

    z_cadence_mean = z("cadence_mean", cadence_mean)
    z_cadence_std = z("cadence_std", cadence_std)
    z_duration = z("session_duration_sec", duration)

    # First session establishes this user's live baseline -- a real
    # learned reference, not the hidden generator ground truth the
    # offline batch pipeline used for hour/device/network.
    if hist["typical_hour"] is None:
        hist["typical_hour"] = event.hour_of_day
        hist["device_hash"] = event.device_hash
        hist["network_type"] = event.network_type

    hour_deviation = circular_hour_distance(event.hour_of_day, hist["typical_hour"])
    device_change_flag = int(event.device_hash != hist["device_hash"])
    network_change_flag = int(event.network_type != hist["network_type"])
    sequence_entropy = shannon_entropy(event.screen_sequence)

    features = {
        "z_cadence_mean": z_cadence_mean,
        "z_cadence_std": z_cadence_std,
        "z_session_duration": z_duration,
        "sequence_entropy": sequence_entropy,
        "hour_deviation": hour_deviation,
        "device_change_flag": device_change_flag,
        "network_change_flag": network_change_flag,
    }

    # Update history AFTER scoring -- this session must never be part
    # of its own baseline. Typical hour drifts slowly toward new
    # sessions rather than being overwritten outright.
    hist["cadence_mean"].append(cadence_mean)
    hist["cadence_std"].append(cadence_std)
    hist["session_duration_sec"].append(duration)
    hist["typical_hour"] = (hist["typical_hour"] * 0.8) + (event.hour_of_day * 0.2)

    if is_cold_start:
        flagged = device_change_flag or network_change_flag
        risk_score = 0.85 if flagged else 0.3
    else:
        X = np.array([[features[c] for c in FEATURE_COLS]])
        raw_score = -MODEL.decision_function(X)[0]
        risk_score = float(np.clip((raw_score - SCORE_MIN) / (SCORE_MAX - SCORE_MIN + EPS), 0, 1))

    return risk_score, is_cold_start, features


def decide(event: SessionEvent, risk_score, is_cold_start, features):
    if risk_score < LOW:
        return {"decision": "approve", "reasoning": "Risk score below the borderline band.", "source": "threshold"}
    if risk_score > HIGH:
        return {"decision": "block", "reasoning": "Risk score above the borderline band.", "source": "threshold"}

    # Borderline -- hand off to the same LLM arbiter used offline,
    # built with live context instead of synthetic context.
    profile = PROFILES.get(event.user_id)
    if profile is None:
        return {"decision": "soft_challenge", "reasoning": "Borderline risk, no personalization profile on file.", "source": "fallback_no_profile"}

    context = {
        "session_id": f"{event.user_id}_live",
        "user_id": event.user_id,
        "risk_score": round(risk_score, 3),
        "device_change_flag": features["device_change_flag"],
        "network_change_flag": features["network_change_flag"],
        "hour_deviation_hours": round(features["hour_deviation"], 1),
        "sequence_entropy": round(features["sequence_entropy"], 2),
        "user_archetype": profile["archetype"],
        "user_usual_active_day": DAY_NAMES[profile["preferred_check_day"]],
        "user_usual_active_hour": profile["preferred_check_hour"],
        "user_typical_recurring_payment": profile["estimated_recurring_amount"],
        "transaction_amount": event.transaction_amount if event.transaction_amount is not None else profile["estimated_recurring_amount"],
    }
    return arbitrate(context)


@app.post("/session/event")
def session_event(event: SessionEvent):
    """
    One call in, one decision out. Send a session's raw behavioral
    data; get back a risk score plus a final decision -- approve,
    soft_challenge, or block -- with a stated reason.
    """
    risk_score, is_cold_start, features = score_session(event)
    outcome = decide(event, risk_score, is_cold_start, features)
    return {
        "user_id": event.user_id,
        "risk_score": round(risk_score, 3),
        "is_cold_start": is_cold_start,
        **outcome,
    }


@app.get("/user/{user_id}/personalization")
def get_personalization(user_id: str):
    """Returns the precomputed archetype + nudge-relevant profile for the dashboard."""
    profile = PROFILES.get(user_id)
    if profile is None:
        return {"error": "no profile found for this user_id"}
    return profile


@app.get("/health")
def health():
    return {"status": "ok", "users_with_history": len(USER_HISTORY)}
