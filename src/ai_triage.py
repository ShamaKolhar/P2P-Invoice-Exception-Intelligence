"""
Phase 5 - GenAI exception triage.

Takes the top-N exception cases by net worth (from p2p_exceptions.py) and
sends each case's real event history to Claude, asking for a short summary,
a likely root cause (from a fixed list), a recommended next action, and a
priority. The model is explicitly told to say "insufficient information"
rather than guess, and a blank "human_review" column is added so the design
stays human-in-the-loop: AI assists the AP team, it does not auto-approve
anything.
"""

import argparse
import json

import pandas as pd
from jsonschema import validate, ValidationError

from config import (
    EVENT_LOG_PARQUET,
    CASE_FEATURES_PARQUET,
    DATA_PROCESSED_DIR,
    PROMPTS_DIR,
    COL_CASE_ID,
    COL_ACTIVITY,
    COL_TIMESTAMP,
    DEFAULT_AI_TRIAGE_TOP_N,
)
from ai_client import get_client, get_model, cache_get, cache_set, call_with_retry, extract_text

TRIAGE_RESULTS_PATH = DATA_PROCESSED_DIR / "ai_triage_results.parquet"

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "exception_summary": {"type": "string"},
        "likely_root_cause": {"type": "string"},
        "recommended_action": {"type": "string"},
        "priority": {"type": "string", "enum": ["High", "Medium", "Low"]},
    },
    "required": ["exception_summary", "likely_root_cause", "recommended_action", "priority"],
}

FLAG_COLUMNS = [
    "E1_invoice_before_gr",
    "E2_price_change",
    "E3_quantity_change",
    "E4_payment_block",
    "E5_repeated_invoice_receipt",
    "E6_long_cycle_time",
]


def select_top_cases(case_features, top_n):
    exceptions = case_features[case_features["has_exception"]].copy()
    exceptions = exceptions.sort_values("net_worth_eur", ascending=False, na_position="last")
    return exceptions.head(top_n)


def build_case_data_text(case_row, events_df):
    triggered_flags = [c for c in FLAG_COLUMNS if c in case_row and bool(case_row[c])]
    case_events = events_df[events_df[COL_CASE_ID] == case_row[COL_CASE_ID]].sort_values(COL_TIMESTAMP)

    lines = []
    lines.append(f"Case ID: {case_row[COL_CASE_ID]}")
    lines.append(f"Net worth (EUR): {case_row.get('net_worth_eur')}")
    lines.append(f"Cycle time (days): {case_row.get('cycle_time_days')}")
    lines.append(f"Exception rules triggered: {', '.join(triggered_flags) if triggered_flags else '(none)'}")
    lines.append("Event history (activity @ timestamp):")
    for _, ev in case_events.iterrows():
        lines.append(f"  - {ev[COL_ACTIVITY]} @ {ev[COL_TIMESTAMP]}")
    return "\n".join(lines)


def build_prompt(case_data_text):
    template = (PROMPTS_DIR / "triage_exception.txt").read_text(encoding="utf-8")
    return template.replace("{case_data}", case_data_text)


def call_claude_for_case(client, model, prompt_text):
    def _call():
        return client.messages.create(
            model=model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt_text}],
        )

    return call_with_retry(_call)


def parse_json_response(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=DEFAULT_AI_TRIAGE_TOP_N)
    args = parser.parse_args()

    if not CASE_FEATURES_PARQUET.exists():
        print(f"{CASE_FEATURES_PARQUET} not found. Run p2p_exceptions.py first.")
        return

    case_features = pd.read_parquet(CASE_FEATURES_PARQUET)
    events_df = pd.read_parquet(EVENT_LOG_PARQUET)

    top_cases = select_top_cases(case_features, args.top_n)
    if top_cases.empty:
        print("No exception cases found to triage.")
        return

    client = get_client()
    model = get_model()

    rows = []
    for _, case_row in top_cases.iterrows():
        case_id = case_row[COL_CASE_ID]
        case_data_text = build_case_data_text(case_row, events_df)
        prompt_text = build_prompt(case_data_text)

        cache_key = f"triage:{model}:{case_id}:{hash(case_data_text)}"
        cached = cache_get(cache_key)

        error = None
        parsed = None

        if cached is not None:
            parsed = cached.get("parsed")
            error = cached.get("error")
            print(f"{case_id}: using cached response")
        else:
            try:
                response = call_claude_for_case(client, model, prompt_text)
                raw_text = extract_text(response)
                parsed = parse_json_response(raw_text)
                validate(instance=parsed, schema=JSON_SCHEMA)
                print(f"{case_id}: triaged ok -> priority={parsed['priority']}")
            except (json.JSONDecodeError, ValidationError) as exc:
                error = f"malformed_json: {exc}"
                print(f"{case_id}: {error}")
            except Exception as exc:  # noqa: BLE001
                error = f"api_error: {exc}"
                print(f"{case_id}: {error}")

            if error is None or error.startswith("malformed_json"):
                # Cache real outcomes, but not transient/api errors, so a
                # temporary failure doesn't get stuck in the cache forever.
                cache_set(cache_key, {"parsed": parsed, "error": error})

        row = {
            "case_id": case_id,
            "net_worth_eur": case_row.get("net_worth_eur"),
            "cycle_time_days": case_row.get("cycle_time_days"),
            "exception_summary": parsed.get("exception_summary") if parsed else None,
            "likely_root_cause": parsed.get("likely_root_cause") if parsed else None,
            "recommended_action": parsed.get("recommended_action") if parsed else None,
            "priority": parsed.get("priority") if parsed else None,
            "error": error,
            "human_review": "",  # left blank for a human AP reviewer
        }
        rows.append(row)

    results_df = pd.DataFrame(rows)
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    results_df.to_parquet(TRIAGE_RESULTS_PATH, index=False)
    print(f"\nSaved triage results for {len(results_df)} cases to {TRIAGE_RESULTS_PATH}")


if __name__ == "__main__":
    main()
