from config import TARGET_USER

def get_payload():
    return {
        "user_id": TARGET_USER,
        "keystroke_intervals": [0.12, 0.15, 0.09, 0.21, 0.14, 0.18],
        "session_duration_sec": 45.5,
        "screen_sequence": ["dashboard", "transfer_funds", "confirm_otp"],
        "hour_of_day": 14,
        "device_hash": "human_device_a7b8c9",
        "network_type": "cellular",
        "transaction_amount": 1000.00
    }