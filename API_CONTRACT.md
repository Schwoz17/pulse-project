# PULSE API — Contract for Backend

One file to run, two endpoints to call. This replaces needing to read or
run any of the seven pipeline scripts directly.

## Setup (once)

```
pip install -r requirements.txt
python3 model_training.py      # trains and saves model_bundle.joblib -- rerun only if features.csv changes
uvicorn api:app --port 8000
```

Needs `model_bundle.joblib`, `personalization_profiles.json`, and
`risk_arbiter.py` in the same folder as `api.py`. All already produced
by the rest of the pipeline.

If `ANTHROPIC_API_KEY` isn't set as an environment variable, borderline
decisions fall back to a default `soft_challenge` instead of calling
the LLM — the API still works, just without live reasoning on the
ambiguous cases.

---

## POST /session/event

The main endpoint. Send a session's raw behavioral data; get back a
risk score and a final decision in one call.

**Request:**
```json
{
  "user_id": "user_014",
  "keystroke_intervals": [150.2, 148.7, 155.1, 152.3, 149.8, 151.0, 153.4, 150.9],
  "session_duration_sec": 120,
  "screen_sequence": ["login", "dashboard", "balance", "logout"],
  "hour_of_day": 19.5,
  "device_hash": "abc123",
  "network_type": "wifi_home",
  "transaction_amount": 45000
}
```

`transaction_amount` is optional — include it only when the session
involves an actual transfer. Omit it for a plain login/balance-check
session.

**Response:**
```json
{
  "user_id": "user_014",
  "risk_score": 0.509,
  "is_cold_start": false,
  "decision": "soft_challenge",
  "reasoning": "New device, but timing and amount match this user's known Sunday-night rent payment pattern.",
  "source": "llm"
}
```

`decision` is always one of: `approve`, `soft_challenge`, `block`.
`source` tells you whether the decision came from a simple threshold
(`threshold`), the LLM arbiter (`llm`), or a fallback default when the
LLM wasn't available (`fallback_default`) — useful for logging, not
something the UI needs to show the user.

`is_cold_start: true` means this user has fewer than 5 sessions of
history on file — risk scoring for them currently relies on device and
network checks only, not behavioral pattern-matching. This is a known,
stated limitation, not a bug.

---

## GET /user/{user_id}/personalization

**Response:**
```json
{
  "user_id": "user_014",
  "archetype": "Weekend Planner",
  "preferred_check_day": 5,
  "preferred_check_hour": 19.2,
  "estimated_recurring_amount": 85000.0,
  "days_until_due": 6,
  "current_balance": 62000.0,
  "projected_balance": 48000.0,
  "shortfall_amount": 37000.0
}
```

`shortfall_amount` of `0` means this user is on track. Anything above
`0` is the amount they're projected to be short by their next recurring
payment — this is what feeds the nudge shown on the dashboard.

---

## GET /health

```json
{ "status": "ok", "users_with_history": 12 }
```

Quick check that the server is up and how many users it currently has
behavioral history for (resets on restart — see note below).

---

## What's a simplification, stated plainly

- Per-user history lives in memory. Restarting the server wipes it —
  everyone starts back at cold-start. Fine for a demo; a real
  deployment persists this in the database Backend already owns.
- `transaction_amount`, when omitted, defaults internally to the
  user's typical recurring payment for arbitration purposes — not a
  real transaction amount. Always send the real one when the session
  is an actual transfer.
