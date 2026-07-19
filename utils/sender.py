import requests
from config import EVENT_ENDPOINT as endpoint

def send_to_backend(payload):
    """Send a session run request to the target endpoint"""
    try:
        response = requests.post(endpoint, json=payload)
        return response.status_code, response.json()
    except requests.RequestException as e:
        print(f"[!] Error sending session run: {e}")
        return None