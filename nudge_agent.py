"""
PULSE -- Nudge & Insight Generator (LLM Agent)

Turns a structured personalization profile into a short, specific
notification instead of a generic one. This is the one PULSE module
built as an LLM agent rather than classical ML: the personalization
profile is structured data, but the thing a customer actually reads
needs to read like a sentence, not a JSON blob.

Falls back to a template message if the API is unavailable -- no key
set, network down, request times out. A banking nudge system going
silent because an API call failed is a worse outcome than sending
something slightly less personalized.

Uses Groq (free-tier, OpenAI-compatible) instead of the Anthropic API.
Groq's endpoint speaks the same request/response shape as OpenAI, so
the standard `openai` package works here with just a different
base_url and API key -- no separate SDK needed.
"""

import os
import json

try:
    from openai import OpenAI
    _CLIENT = (
        OpenAI(api_key=os.environ.get("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1")
        if os.environ.get("GROQ_API_KEY") else None
    )
except ImportError:
    _CLIENT = None

MODEL = "openai/gpt-oss-20b"  # fast and cheap -- nudges are short, frequent,
                               # low-stakes; no reason to route through a bigger model


def _fallback_nudge(profile):
    if profile["shortfall_amount"] > 0:
        return (
            f"Heads up -- based on your recent spending, your balance may run about "
            f"\u20a6{profile['shortfall_amount']:,.0f} short in {profile['days_until_due']} day(s), "
            f"around when your usual big payment is due. Worth moving something aside before then."
        )
    return (
        f"You're on track -- your balance looks steady against your usual payment "
        f"due in {profile['days_until_due']} day(s)."
    )


def generate_nudge(profile):
    if _CLIENT is None:
        return {"text": _fallback_nudge(profile), "source": "fallback_template"}

    prompt = (
        "Write one short banking-app notification, one or two sentences, no greeting "
        "and no sign-off. Use the numbers below directly and naturally. Naira amounts "
        "use the symbol \u20a6.\n\n"
        f"{json.dumps(profile, indent=2)}\n\n"
        "Write the notification now, nothing else."
    )
    try:
        response = _CLIENT.chat.completions.create(
            model=MODEL,
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content.strip()
        return {"text": text, "source": "llm"}
    except Exception as e:
        return {"text": _fallback_nudge(profile), "source": f"fallback_template (error: {type(e).__name__})"}


def main():
    with open("personalization_profiles.json") as f:
        profiles = json.load(f)

    results = []
    sample = sorted(profiles, key=lambda p: -p["shortfall_amount"])[:5]  # most at-risk first
    for profile in sample:
        result = generate_nudge(profile)
        results.append({**profile, "nudge": result["text"], "nudge_source": result["source"]})
        print(f"\n[{profile['user_id']}] {profile['archetype']} -- ({result['source']})")
        print(result["text"])

    with open("nudges.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nWrote nudges.json")


if __name__ == "__main__":
    main()