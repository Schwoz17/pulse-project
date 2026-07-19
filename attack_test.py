import requests
import time

BACKEND_URL = "https://pulse-project.onrender.com"

# Step 1: pretend to be a normal user, 5 times, to build up history
print("Building normal history...")
for i in range(5):
    requests.post(f"{BACKEND_URL}/session/event", json={
        "user_id": "user_005",
        "keystroke_intervals": [150, 148, 155, 152, 149, 151, 153, 150],
        "session_duration_sec": 120,
        "screen_sequence": ["login", "dashboard", "balance", "logout"],
        "hour_of_day": 19.5,
        "device_hash": "known_device",
        "network_type": "wifi_home"
    })
    print(f"  sent normal session {i+1}/5")
    time.sleep(1)

# Step 2: the actual "attack" — a suspicious session
print("\nNow sending a suspicious session...")
response = requests.post(f"{BACKEND_URL}/session/event", json={
    "user_id": "user_005",
    "keystroke_intervals": [280, 275, 290, 265, 300, 270, 295, 285],
    "session_duration_sec": 45,
    "screen_sequence": ["login", "transfer", "confirm"],
    "hour_of_day": 3.0,
    "device_hash": "unknown_device_xyz",
    "network_type": "mobile_data",
    "transaction_amount": 250000
})

result = response.json()
print("\n--- RESULT ---")
print("Risk score:", result["risk_score"])
print("Decision:", result["decision"])
print("Reasoning:", result["reasoning"])
