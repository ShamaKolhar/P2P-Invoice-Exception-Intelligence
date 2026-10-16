"""
Unit tests for the six exception rules in src/p2p_exceptions.py.

Every case ID below is a real case from the BPI Challenge 2019 event log
(not synthetic), hand-picked by inspecting its actual event history. The
expected result for each test is documented from that real event history,
so it can be independently verified by looking the case up in
data/processed/bpi2019_events.parquet.

These tests require data/processed/case_features.parquet to exist, i.e.
prepare_data.py and p2p_exceptions.py must have been run first.
"""

import pandas as pd
import pytest

from config import CASE_FEATURES_PARQUET, EVENT_LOG_PARQUET

pytestmark = pytest.mark.skipif(
    not CASE_FEATURES_PARQUET.exists() or not EVENT_LOG_PARQUET.exists(),
    reason="run prepare_data.py and p2p_exceptions.py on the real BPI 2019 log first",
)


@pytest.fixture(scope="module")
def case_features():
    return pd.read_parquet(CASE_FEATURES_PARQUET).set_index("case_id")


def test_e2_price_change_detected(case_features):
    # Case 2000000010_00001 has two real "Change Price" events
    # (2018-09-05 14:34 and 2018-10-22 04:05).
    assert case_features.loc["2000000010_00001", "E2_price_change"] == True  # noqa: E712


def test_e3_quantity_change_detected(case_features):
    # Case 2000000146_00001 has a real "Change Quantity" event (2018-02-27 16:29).
    assert case_features.loc["2000000146_00001", "E3_quantity_change"] == True  # noqa: E712


def test_e4_payment_block_detected(case_features):
    # Case 2000000007_00001 has a real "Remove Payment Block" event (2018-02-21 12:55),
    # meaning a payment block was set and lifted at some point for this case.
    assert case_features.loc["2000000007_00001", "E4_payment_block"] == True  # noqa: E712


def test_e5_repeated_invoice_receipt_detected(case_features):
    # Case 2000000005_00001 has two real "Record Invoice Receipt" events
    # (2018-04-03 04:26 and 2018-08-02 07:17), with a "Cancel Invoice Receipt"
    # in between - a real cancel-and-resubmit case.
    assert case_features.loc["2000000005_00001", "E5_repeated_invoice_receipt"] == True  # noqa: E712


def test_e6_long_cycle_time_detected(case_features):
    # Case 2000000002_00001 is in the "3-way match, invoice after GR" category,
    # where the real 90th-percentile cycle time is ~119 days. This case's real
    # cycle time is ~224 days (2018-01-04 PO creation to 2018-08-16 invoice clearing).
    row = case_features.loc["2000000002_00001"]
    assert row["cycle_time_days"] > 200
    assert row["E6_long_cycle_time"] == True  # noqa: E712


def test_e1_no_violations_found_for_compliant_case(case_features):
    # Case 2000000001_00001 is in the "3-way match, invoice after GR" category
    # and its real event history has Goods Receipt (2018-01-16 12:09) before
    # Invoice Receipt (2018-01-16 14:44), as required - so E1 must be False.
    assert case_features.loc["2000000001_00001", "E1_invoice_before_gr"] == False  # noqa: E712


def test_e1_rule_found_zero_violations_overall(case_features):
    # A real, documented finding for this dataset: among the ~11,100 cases in
    # the "3-way match, invoice after GR" category that have both a goods
    # receipt and an invoice receipt event, none have the invoice recorded
    # first - the GR-based invoice verification control appears well-enforced
    # in this log. This test locks in that finding rather than assuming it.
    assert case_features["E1_invoice_before_gr"].sum() == 0


def test_case_with_no_exceptions(case_features):
    # Case 2000000000_00001: single "Record Goods Receipt" then single
    # "Record Invoice Receipt" in the right order, no price/quantity change,
    # no payment block, cycle time well under its category's 90th percentile.
    row = case_features.loc["2000000000_00001"]
    assert row["has_exception"] == False  # noqa: E712
    assert row["exception_count"] == 0
