import hashlib
from typing import Any, Dict, List, Optional

import requests


class PulseApiClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    @staticmethod
    def stable_device_hash(user_id: str, user_agent: str) -> str:
        return hashlib.sha256(f"{user_id}:{user_agent}".encode()).hexdigest()[:16]

    def build_session_event(
        self,
        user_id: str,
        keystroke_intervals: List[float],
        session_duration_sec: float,
        screen_sequence: List[str],
        hour_of_day: float,
        device_hash: str,
        network_type: str,
        transaction_amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        event = {
            "user_id": user_id,
            "keystroke_intervals": keystroke_intervals,
            "session_duration_sec": session_duration_sec,
            "screen_sequence": screen_sequence,
            "hour_of_day": hour_of_day,
            "device_hash": device_hash,
            "network_type": network_type,
        }
        if transaction_amount is not None:
            event["transaction_amount"] = transaction_amount
        return event

    def post_session_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(f"{self.base_url}/session/event", json=event)
        response.raise_for_status()
        return response.json()

    def get_personalization(self, user_id: str) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/user/{user_id}/personalization")
        response.raise_for_status()
        return response.json()
