from requests import Timeout

BASE_URL = "https://pulse-project.onrender.com"
TARGET_USER = "user_10293"
EVENT_ENDPOINT = f"{BASE_URL}/session/event"
Timeout = 5  # seconds