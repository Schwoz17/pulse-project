# PULSE — AI/ML Pipeline

Behavioral Modeling & Synthetic Data + Personalization Engine & Nudge Generator.
All synthetic data — no real user data anywhere in this pipeline.

## Setup
pip install -r requirements.txt

`nudge_agent.py` and `risk_arbiter.py` call Groq's API (OpenAI-compatible).
Without `GROQ_API_KEY` set as an environment variable, both fall back to
template/default behavior automatically — the pipeline still runs end
to end, just without real LLM reasoning.

## Run order

**Security path:**

1. `synthetic_data.py` — generates raw behavioral sessions (keystrokes, navigation, device/network) for 40 simulated users, ~15% deliberately anomalous. Writes `raw_sessions.json`, `user_baselines.json`.
2. `features.py` — converts raw sessions into the feature vector both the risk model and Backend's API schema depend on. Cadence and duration are z-scored against each user's own prior sessions (not the current or future ones); the first 5 sessions per user are flagged `is_cold_start` since there's no personal history yet to compare against. Writes `features.csv`.
3. `risk_model.py` — two-tier scoring: full Isolation Forest for users with history, a device/network rule for cold-start sessions. Reports precision/recall/F1 for both tiers plus combined. Writes `risk_scores.csv`.

**Personalization path** (continuing the same pipeline):

4. `synthetic_transactions.py` — generates two months of balance history and balance-check timing per user. Writes `daily_balances.json`, `balance_checks.json`, `finance_baselines.json`.
5. `personalization_engine.py` — clusters users into archetypes (K-Means on observed check timing) and projects whether each user's balance covers their next recurring payment, inferred from the balance history itself. Writes `personalization_profiles.json`.
6. `nudge_agent.py` — LLM agent (`openai/gpt-oss-20b` via Groq) that turns a profile into a short, specific notification. Falls back to a template if no API key. Writes `nudges.json`.

**Reasoning layer:**

7. `risk_arbiter.py` — for sessions in the 0.4–0.7 borderline risk band, an LLM (`openai/gpt-oss-120b` via Groq) reasons over context — device/network flags, the user's known rhythm, transaction amount vs. typical recurring payment — to decide approve / soft_challenge / block, instead of a flat threshold. Falls back to `soft_challenge` if no API key. Writes `arbitration_results.json`.

Note: `transaction_amount` and the day-of-week context in `risk_arbiter.py`
are synthesized for demo purposes — the behavioral sessions and the
transaction timeline come from two separate simulations that don't share
a real clock. In production both come from the same request, for free.

## Live API (for Backend)

The pipeline above is batch/offline. `api.py` wraps it into a live
service Backend can actually call — see `API_CONTRACT.md` for exact
request/response examples.
python3 model_training.py      # once, after features.csv exists
uvicorn api:app --port 8000

Two endpoints: `POST /session/event` (send raw session data, get back
a risk score and final decision in one call) and `GET /user/{user_id}/personalization` (dashboard data). Backend needs `API_CONTRACT.md`, not the seven pipeline scripts.

## OTP Verification (Twilio)

`otp.py` backs the `soft_challenge` step with a real one-time code via
Twilio Verify, instead of a cosmetic "type anything" field. Requires
`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_VERIFY_SERVICE_SID`
set as environment variables. Without them, it degrades the same way the
LLM calls do: `send_otp` reports a simulated status, and `verify_otp`
accepts any 4+ digit code, so the demo still runs end to end without a
live SMS provider configured.

## Backend Demo UI

A lightweight demo app is provided under `backend/` that includes:

- a mock banking event simulator capturing the exact screen names used by the risk model
- enforced behavior for `approve`, `soft_challenge`, and `block`
- a dashboard page showing personalization side by side with decision results

A dedicated frontend implementation lives in `frontend/` with the full mock banking UI, event capture, and screen flow matching the model training data.

Run the backend separately with:
uvicorn api:app --host 0.0.0.0 --port 8000

Run the frontend separately with:
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev

Then open the URL shown by Vite (usually `http://localhost:4173`).

## Deployment

The repo includes a deploy-ready `Dockerfile` and `Procfile` for containerized hosting.
The service can run on any platform that supports Docker or a standard Python web host.

## Known, stated limitations

- Real behavioral biometric data isn't public anywhere — this is why everything is synthetic.
- The 94–95% precision/recall numbers reflect clean synthetic separation; real behavioral data would be noisier.
- Cold-start sessions (first 5 per user) show a real, measured recall drop (~63%) since there's no personal baseline yet — a genuine gap, not hidden.
- `hour_deviation`, `device_change_flag`, and `network_change_flag` still compare against the hidden generator baseline rather than a learned one — an inconsistency with the (now-fixed) cadence/duration features, not yet resolved.
- `nudge_agent.py` and `risk_arbiter.py` have been confirmed working with real Groq responses, verified directly against the API both locally and on the deployed backend. End-to-end verification through the frontend UI specifically is still pending confirmation that mock mode is disabled there.
- `send_otp`/`verify_otp` fall back to a simulated, always-accepting check when Twilio credentials aren't configured on the environment running `api.py` — confirm real credentials are set before relying on SMS verification in a live demo.
