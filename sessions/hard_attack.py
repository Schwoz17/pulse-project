from config import TARGET_USER

def get_payload():
    """Build a high-risk attack payload (Expected outcome: block)"""
    return {
        "user_id": TARGET_USER,
        "keystroke_intervals": [0.01, 0.01, 0.01, 0.01, 0.01], # Completely uniform mechanical precision
        "session_duration_sec": 0.8,                           # Humanly impossible speed
        "screen_sequence": ["dashboard", "confirm_otp"],        # Direct exploit script bypassing standard paths
        "hour_of_day": 3,                                      # Active during high-risk hours
        "device_hash": "adversary_bot_xyz987",                 # Unrecognized device footprint
        "network_type": "vpn",                                 # Masked location routing
        "transaction_amount": 50000.00                          # Maximum limit depletion attempt
    }