import sys
from utils.sender import send_to_backend
from utils.printer import display_title, display_result
from utils.logger import log_session_run

# Dynamic import configuration paths mapping back to payload assets
from sessions.normal import get_payload as get_normal
from sessions.borderline import get_payload as get_borderline
from sessions.hard_attack import get_payload as get_hard_attack

def run_simulation(name, payload_builder):
    payload = payload_builder()
    status_code, response = send_to_backend(payload)
    
    # Display results nicely via the terminal
    display_result(name, status_code, response)
    
    # Saving demo logs locally for documentation validation
    log_session_run(name, payload, status_code, response)
    
    if status_code is None:
        print("[!] Execution pipeline halted due to missing upstream server connectivity dependencies.")
        sys.exit(1)

def main():
    display_title()
    
    run_simulation("1. Human User Baseline Verification Profile", get_normal)
    run_simulation("2. Anomalous Borderline Evaluation Scenario", get_borderline)
    run_simulation("3. Automated High-Risk Bot Exploit Insertion", get_hard_attack)

if __name__ == "__main__":
    main()