import json
from datetime import datetime

def log_session_run(scenario_name, payload, status_code, response_json):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "scenario": scenario_name,
        "injected_payload": payload,
        "network_status": status_code,
        "engine_response": response_json
    }
    try:
        with open("simulation_audit.log", "a") as log_file:
            log_file.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"[!] Log preservation error encountered: {e}")