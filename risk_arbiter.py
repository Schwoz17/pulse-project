"""
PULSE -- Risk Arbiter (LLM Reasoning Layer)

Borderline risk scores (0.4-0.7 -- not obviously safe, not obviously
fraud) don't get a hard block/allow from the Isolation Forest. They get
passed here, where an LLM reasons over the score alongside context the
score itself can't see: does this look like the user's usual pattern,
even though something about it is a little off.

Model choice: openai/gpt-oss-120b via Groq, not the smaller gpt-oss-20b
used for nudges. A wrong nudge is mildly annoying. A wrong arbitration
is either a fraud loss or a frustrated legitimate customer -- worth
spending more reasoning on a judgment call than on a notification
sentence.

Known seam, stated plainly: the behavioral session data and the
financial transaction data come from two separate synthetic
simulations that don't share a timeline. "day_of_week" for a session
is borrowed from the user's finance baseline (their usual balance-check
day) as a stand-in for "a day this user is normally active" -- not a
real timestamp match. "transaction_amount" is synthesized here for
demo purposes; in production it would be the actual amount of the
transaction being authorized at that moment, not backfilled after
the fact. Fixing this properly means giving both simulations one
shared clock -- a real next step, not done here.

Uses Groq (free-tier, OpenAI-compatible) instead of the Anthropic API --
same reasoning as nudge_agent.py.
"""

import os
import json
import random
import re

import numpy as np
import pandas as pd

try:
    from openai import OpenAI
    _CLIENT = (
        OpenAI(api_key=os.environ.get("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1")
        if os.environ.get("GROQ_API_KEY") else None
    )
except ImportError:
    _CLIENT = None

MODEL = "openai/gpt-oss-120b"
LOW, HIGH = 0.4, 0.7  # the borderline band this module exists to handle
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

random.seed(11)
np.random.seed(11)


def synthesize_transaction_amount(profile, matches_pattern):
    """
    Demo stand-in only -- see module docstring. Sometimes generates an
    amount close to the user's known recurring payment (the "looks
    legitimate" case), sometimes an unrelated amount (the "could go
    either way" case).
    """
    recurring = profile.get("estimated_recurring_amount", 50000)
    if matches_pattern:
        return round(recurring * np.random.uniform(0.95, 1.05), 2)
    return round(np.random.uniform(2000, recurring * 2), 2)


def build_context(session_row, feature_row, profile):
    matches_pattern = random.random() < 0.5
    return {
        "session_id": session_row["session_id"],
        "user_id": session_row["user_id"],
        "risk_score": round(float(session_row["risk_score"]), 3),
        "device_change_flag": int(feature_row["device_change_flag"]),
        "network_change_flag": int(feature_row["network_change_flag"]),
        "hour_deviation_hours": round(float(feature_row["hour_deviation"]), 1),
        "sequence_entropy": round(float(feature_row["sequence_entropy"]), 2),
        "user_archetype": profile["archetype"],
        "user_usual_active_day": DAY_NAMES[profile["preferred_check_day"]],
        "user_usual_active_hour": profile["preferred_check_hour"],
        "user_typical_recurring_payment": profile["estimated_recurring_amount"],
        "transaction_amount": synthesize_transaction_amount(profile, matches_pattern),
    }


def _fallback_decision(context):
    # No reasoning available -- fall back to the conservative default a
    # pure threshold system would already do: challenge, don't block,
    # don't wave through.
    return {"decision": "soft_challenge", "reasoning": "LLM unavailable -- default step-up challenge applied."}


def arbitrate(context):
    if _CLIENT is None:
        return {**_fallback_decision(context), "source": "fallback_default"}

    prompt = (
        "You are a fraud-risk arbiter for a Nigerian banking app. A session has "
        "landed in the borderline risk band -- not clearly safe, not clearly "
        "fraudulent. Decide: approve, soft_challenge (extra verification step), "
        "or block. Weigh the risk score against whether the session's context "
        "matches this user's known behavior.\n\n"
        f"{json.dumps(context, indent=2)}\n\n"
        "Respond with ONLY a JSON object, no other text: "
        '{"decision": "approve|soft_challenge|block", "reasoning": "one sentence"}'
    )
    try:
        response = _CLIENT.chat.completions.create(
            model=MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content.strip()
        # gpt-oss-120b is a reasoning model -- it can emit thinking or
        # commentary alongside the final answer despite being told to
        # return only JSON. Pull the first {...} block out instead of
        # assuming the whole response is clean JSON; this survives
        # extra text before/after in a way naive prefix-stripping can't.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"no JSON object found in response: {text[:200]!r}")
        parsed = json.loads(match.group(0))
        if parsed.get("decision") not in {"approve", "soft_challenge", "block"}:
            raise ValueError(f"unexpected decision value: {parsed.get('decision')}")
        return {**parsed, "source": "llm"}
    except Exception as e:
        return {**_fallback_decision(context), "source": f"fallback_default (error: {type(e).__name__})"}


def main():
    risk_df = pd.read_csv("risk_scores.csv")
    feat_df = pd.read_csv("features.csv").set_index("session_id")
    with open("personalization_profiles.json") as f:
        profiles = {p["user_id"]: p for p in json.load(f)}

    borderline = risk_df[(risk_df["risk_score"] >= LOW) & (risk_df["risk_score"] <= HIGH)]
    print(f"{len(borderline)} sessions land in the borderline band ({LOW}-{HIGH}) out of {len(risk_df)} total.")

    results = []
    for _, row in borderline.iterrows():
        if row["session_id"] not in feat_df.index or row["user_id"] not in profiles:
            continue
        context = build_context(row, feat_df.loc[row["session_id"]], profiles[row["user_id"]])
        outcome = arbitrate(context)
        results.append({**context, "true_label": int(row["label"]), **outcome})
        print(f"\n[{context['session_id']}] risk={context['risk_score']} -- ({outcome['source']})")
        print(f"  decision: {outcome['decision']}")
        print(f"  reasoning: {outcome['reasoning']}")

    with open("arbitration_results.json", "w") as f:
        json.dump(results, f, indent=2)

    if results:
        n_correct_ish = sum(
            1 for r in results
            if (r["decision"] == "block") == bool(r["true_label"])
        )
        print(f"\nWrote arbitration_results.json -- {len(results)} arbitrated sessions.")
    else:
        print("\nNo borderline sessions found to arbitrate.")


if __name__ == "__main__":
    main()