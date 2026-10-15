"""
Phase 4 - GenAI document extraction.

Sends each sampled SROIE receipt image to Claude (vision) with a strict JSON
schema prompt, validates the JSON, and compares it field by field against the
real ICDAR-SROIE ground truth labels (company, address, date, total).

Note on terminology: SROIE is a dataset of real scanned retail receipts, not
purchase invoices. We call them "receipts / invoice-like documents"
throughout this project rather than "invoices", since that's what they are.

Results (including every failure case) are saved to
data/processed/ai_extraction_results.parquet for the Excel/chart outputs.
"""

import argparse
import base64
import json
import re
from datetime import datetime

import pandas as pd
from jsonschema import validate, ValidationError

from config import (
    SROIE_SAMPLE_DIR,
    DATA_PROCESSED_DIR,
    PROMPTS_DIR,
    DEFAULT_AI_EXTRACT_SAMPLE,
)
from ai_client import get_client, get_model, cache_get, cache_set, call_with_retry, extract_text

EXTRACTION_RESULTS_PATH = DATA_PROCESSED_DIR / "ai_extraction_results.parquet"

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor": {"type": ["string", "null"]},
        "address": {"type": ["string", "null"]},
        "document_date": {"type": ["string", "null"]},
        "total_amount": {"type": ["string", "null"]},
        "currency": {"type": ["string", "null"]},
    },
    "required": ["vendor", "address", "document_date", "total_amount", "currency"],
}

# Ground-truth JSON files use these keys; map them onto our extraction schema.
GT_FIELD_MAP = {
    "vendor": "company",
    "address": "address",
    "document_date": "date",
    "total_amount": "total",
}


def normalise_text(value):
    if value is None:
        return ""
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalise_amount(value):
    if value is None:
        return None
    match = re.search(r"[-+]?[0-9]*\.?[0-9]+", str(value).replace(",", ""))
    if not match:
        return None
    try:
        return round(float(match.group()), 2)
    except ValueError:
        return None


def normalise_date(value):
    if value is None:
        return None
    value = str(value).strip()
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def load_ground_truth(doc_id):
    path = SROIE_SAMPLE_DIR / "key" / f"{doc_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def list_sample_doc_ids(sample_size):
    img_dir = SROIE_SAMPLE_DIR / "img"
    if not img_dir.exists():
        return []
    doc_ids = sorted(p.stem for p in img_dir.glob("*.jpg"))
    return doc_ids[:sample_size]


def build_prompt():
    return (PROMPTS_DIR / "extract_document_fields.txt").read_text(encoding="utf-8")


def call_claude_for_document(client, model, prompt_text, image_path):
    image_bytes = image_path.read_bytes()
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    def _call():
        return client.messages.create(
            model=model,
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt_text},
                    ],
                }
            ],
        )

    return call_with_retry(_call)


def parse_json_response(raw_text):
    text = raw_text.strip()
    # Claude is asked to return only JSON, but strip code fences defensively.
    text = re.sub(r"^```(json)?", "", text).rstrip("`").strip()
    return json.loads(text)


def score_document(doc_id, extracted, ground_truth):
    row = {"doc_id": doc_id}
    for field, gt_key in GT_FIELD_MAP.items():
        extracted_value = extracted.get(field) if extracted else None
        gt_value = ground_truth.get(gt_key)
        row[f"{field}_extracted"] = extracted_value
        row[f"{field}_ground_truth"] = gt_value

        exact = extracted_value == gt_value

        # Normalised match is never stricter than exact match: if the raw
        # strings are already identical, it's a match regardless of whether
        # the normaliser below can parse that particular format.
        if field == "total_amount":
            norm_match = exact or normalise_amount(extracted_value) == normalise_amount(gt_value)
        elif field == "document_date":
            norm_match = exact or (
                normalise_date(extracted_value) == normalise_date(gt_value)
                and normalise_date(gt_value) is not None
            )
        else:
            norm_match = exact or (
                normalise_text(extracted_value) == normalise_text(gt_value)
                and normalise_text(gt_value) != ""
            )

        row[f"{field}_exact_match"] = bool(exact)
        row[f"{field}_normalised_match"] = bool(norm_match)
    return row


def run_rule_checks(results_df):
    mandatory_fields = ["vendor_extracted", "document_date_extracted", "total_amount_extracted"]
    results_df["missing_mandatory_fields"] = results_df[mandatory_fields].isnull().any(axis=1)

    results_df["invalid_date"] = results_df["document_date_extracted"].apply(
        lambda v: v is not None and normalise_date(v) is None
    )

    dup_key = (
        results_df["vendor_extracted"].apply(normalise_text)
        + "|"
        + results_df["document_date_extracted"].apply(lambda v: normalise_date(v) or "")
        + "|"
        + results_df["total_amount_extracted"].apply(lambda v: str(normalise_amount(v)))
    )
    results_df["duplicate_document"] = dup_key.duplicated(keep=False) & (dup_key != "||None")
    return results_df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=DEFAULT_AI_EXTRACT_SAMPLE)
    args = parser.parse_args()

    doc_ids = list_sample_doc_ids(args.sample)
    if not doc_ids:
        print(f"No SROIE sample images found in {SROIE_SAMPLE_DIR / 'img'}. Skipping extraction.")
        return

    client = get_client()
    model = get_model()
    prompt_text = build_prompt()

    rows = []
    for doc_id in doc_ids:
        cache_key = f"extract:{model}:{doc_id}:{prompt_text}"
        cached = cache_get(cache_key)

        error = None
        extracted = None
        raw_text = None

        if cached is not None:
            raw_text = cached.get("raw_text")
            extracted = cached.get("parsed")
            error = cached.get("error")
            print(f"{doc_id}: using cached response")
        else:
            image_path = SROIE_SAMPLE_DIR / "img" / f"{doc_id}.jpg"
            try:
                response = call_claude_for_document(client, model, prompt_text, image_path)
                raw_text = extract_text(response)
                parsed = parse_json_response(raw_text)
                validate(instance=parsed, schema=JSON_SCHEMA)
                extracted = parsed
                print(f"{doc_id}: extracted ok")
            except (json.JSONDecodeError, ValidationError) as exc:
                error = f"malformed_json: {exc}"
                print(f"{doc_id}: {error}")
            except Exception as exc:  # noqa: BLE001
                error = f"api_error: {exc}"
                print(f"{doc_id}: {error}")

            if error is None or error.startswith("malformed_json"):
                # Cache real outcomes (success or a genuine malformed-JSON
                # finding), but not transient/api errors, so a temporary
                # failure doesn't get stuck in the cache forever.
                cache_set(cache_key, {"raw_text": raw_text, "parsed": extracted, "error": error})

        ground_truth = load_ground_truth(doc_id)
        row = score_document(doc_id, extracted, ground_truth)
        row["error"] = error
        rows.append(row)

    results_df = pd.DataFrame(rows)
    results_df = run_rule_checks(results_df)

    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    results_df.to_parquet(EXTRACTION_RESULTS_PATH, index=False)

    print(f"\nSaved extraction results for {len(results_df)} documents to {EXTRACTION_RESULTS_PATH}")
    for field in GT_FIELD_MAP:
        exact_rate = results_df[f"{field}_exact_match"].mean() * 100
        norm_rate = results_df[f"{field}_normalised_match"].mean() * 100
        print(f"  {field}: exact={exact_rate:.1f}%  normalised={norm_rate:.1f}%")


if __name__ == "__main__":
    main()
