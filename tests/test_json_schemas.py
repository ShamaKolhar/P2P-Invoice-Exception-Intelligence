"""JSON-schema validation tests for the two GenAI output contracts."""

import pytest
from jsonschema import validate, ValidationError

from ai_extract import JSON_SCHEMA as EXTRACTION_SCHEMA
from ai_triage import JSON_SCHEMA as TRIAGE_SCHEMA


def test_valid_extraction_payload_passes():
    payload = {
        "vendor": "STARBUCKS STORE #10208",
        "address": "11302 EUCLID AVENUE, CLEVELAND, OH",
        "document_date": "14/03/2015",
        "total_amount": "4.95",
        "currency": "USD",
    }
    validate(instance=payload, schema=EXTRACTION_SCHEMA)


def test_extraction_payload_allows_null_fields():
    payload = {
        "vendor": None,
        "address": None,
        "document_date": None,
        "total_amount": None,
        "currency": None,
    }
    validate(instance=payload, schema=EXTRACTION_SCHEMA)


def test_extraction_payload_missing_key_fails():
    payload = {
        "vendor": "ACME",
        "address": "123 Main St",
        "document_date": "01/01/2019",
        "total_amount": "10.00",
        # "currency" key missing
    }
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=EXTRACTION_SCHEMA)


def test_valid_triage_payload_passes():
    payload = {
        "exception_summary": "Invoice was recorded before the goods receipt for this line item.",
        "likely_root_cause": "Process non-compliance (manual override)",
        "recommended_action": "Confirm goods were actually received before releasing payment.",
        "priority": "High",
    }
    validate(instance=payload, schema=TRIAGE_SCHEMA)


def test_triage_payload_bad_priority_fails():
    payload = {
        "exception_summary": "Example.",
        "likely_root_cause": "Insufficient information",
        "recommended_action": "Review manually.",
        "priority": "Urgent",  # not one of High / Medium / Low
    }
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=TRIAGE_SCHEMA)
