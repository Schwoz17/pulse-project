"""
PULSE -- OTP Verification (Twilio Verify)

Backs the soft_challenge step shown in the frontend's DecisionGate with a
real one-time code instead of a cosmetic "type anything" field. Twilio
Verify generates, sends, and checks the code itself -- PULSE never stores
or compares codes directly, which also means there's nothing here that
needs its own expiry/rate-limit logic.

Falls back to a simulated response if Twilio isn't configured (no
TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_VERIFY_SERVICE_SID set) --
same "degrade, don't fail" pattern as nudge_agent.py and risk_arbiter.py.
Without real credentials, send_otp reports status "simulated" and
verify_otp accepts any 4+ digit code, so the demo still runs end to end.
"""

import os

try:
    from twilio.base.exceptions import TwilioRestException
    from twilio.rest import Client as TwilioClient

    _SID = os.environ.get("TWILIO_ACCOUNT_SID")
    _TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
    _VERIFY_SERVICE_SID = os.environ.get("TWILIO_VERIFY_SERVICE_SID")
    _CLIENT = TwilioClient(_SID, _TOKEN) if (_SID and _TOKEN and _VERIFY_SERVICE_SID) else None
except ImportError:
    _CLIENT = None
    _VERIFY_SERVICE_SID = None
    TwilioRestException = Exception  # type: ignore[assignment,misc]


def send_otp(phone_e164: str) -> dict:
    """Triggers a real SMS via Twilio Verify. Returns {"status": ..., "simulated": bool}."""
    if _CLIENT is None:
        return {"status": "simulated", "simulated": True}
    try:
        verification = _CLIENT.verify.v2.services(_VERIFY_SERVICE_SID).verifications.create(
            to=phone_e164, channel="sms"
        )
        return {"status": verification.status, "simulated": False}
    except TwilioRestException as e:
        return {"status": f"failed: {e.msg}", "simulated": False, "error": True}


def verify_otp(phone_e164: str, code: str) -> dict:
    """Checks a code against Twilio Verify. Returns {"approved": bool, "status": ..., "simulated": bool}."""
    if _CLIENT is None:
        # No live credentials -- demo-scale check: any plausible-looking
        # code passes, same spirit as the LLM fallbacks elsewhere in this
        # codebase. Real verification requires real credentials.
        approved = len(code.strip()) >= 4
        return {"approved": approved, "status": "simulated", "simulated": True}
    try:
        check = _CLIENT.verify.v2.services(_VERIFY_SERVICE_SID).verification_checks.create(
            to=phone_e164, code=code
        )
        return {"approved": check.status == "approved", "status": check.status, "simulated": False}
    except TwilioRestException as e:
        return {"approved": False, "status": f"failed: {e.msg}", "simulated": False, "error": True}
