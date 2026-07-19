from config import TARGET_USER

def get_payload():
    """Build a borderline session payload (Expected outcome: soft_challenge)"""
    return {
        "user_id": TARGET_USER,
        "keystroke_intervals": [0.08, 0.07, 0.09, 0.06, 0.08], # Fast, slightly suspicious pace
        "session_duration_sec": 40.2,
        "screen_sequence": ["dashboard", "transfer_funds", "confirm_otp"],  # Skipping secondary navigation paths
        "hour_of_day": 23,                                       # Late-night transaction
        "device_hash": "human_device_a5c6c9",                   # Valid device, but unusual profile variables
        "network_type": "wifi",
        "transaction_amount": 1200.00                            # Spiked transaction amount
    }