def display_title():
    """
    Displays the application banner for the terminal interface.
    """
    print("\n" + "=" * 60)
    print("           PULSE ACCOUNT TAKEOVER SIMULATOR")
    print("=" * 60)


def display_result(scenario_name, status_code, response):
    """
    Displays the analysis returned by the PULSE API in a clean,
    presentation-friendly format.
    """

    print(f"\nSimulation Scenario : {scenario_name}")
    print("-" * 60)

    # HTTP Status
    if status_code is None:
        print("HTTP Status         : CONNECTION FAILED")
    else:
        print(f"HTTP Status        : {status_code}")

    print("-" * 60)

    # Handle connection errors
    if response is None:
        print("ERROR               : No response received from the server.")
        print("=" * 60)
        return

    # Handle API errors
    if isinstance(response, dict) and "error" in response:
        print(f"ERROR               : {response['error']}")
        print("=" * 65)
        return

    # Extract API values
    user_id = response.get("user_id", "Unknown User")
    decision = response.get("decision", "UNKNOWN")
    risk_score = response.get("risk_score", "N/A")
    reasoning = response.get("reasoning", "No reasoning provided.")
    source = response.get("source", "Unknown")
    cold_start = response.get("is_cold_start", False)

    # Determine Risk Level
    if isinstance(risk_score, (int, float)):
        if risk_score < 0.4:
            risk_level = "LOW"
        elif risk_score <= 0.7:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"
    else:
        risk_level = "UNKNOWN"

    # Decision Badge
    decision_badges = {
        "approve": "✓ APPROVED",
        "soft_challenge": "⚠ SOFT CHALLENGE",
        "block": "✖ BLOCKED"
    }

    verdict = decision_badges.get(decision.lower(), "UNKNOWN")

    # Display Report
    print(f"User ID             : {user_id}")
    print(f"Risk Score          : {risk_score}")
    print(f"Risk Level          : {risk_level}")
    print(f"Decision            : {verdict}")
    print(f"Reasoning           : {reasoning}")
    print(f"Decision Source     : {source.upper()}")
    print(f"Cold Start          : {'YES' if cold_start else 'NO'}")

    print("=" * 60)
    print("Simulation Complete. Awaiting Next Scenario...")
    print("=" * 60)