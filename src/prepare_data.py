"""
Phase 2 - Data preparation.

Reads the raw BPI Challenge 2019 XES event log with pm4py, standardises
column names, parses timestamps, and writes a clean Parquet file that every
later script works from. Also runs a small set of data-quality checks and
saves a summary so the DQ issues are documented rather than silently fixed.

This script only ever reads the XES file once. Everything downstream uses
the Parquet file it produces.
"""

import sys
import pandas as pd
import pm4py

from config import (
    BPI_XES_PATH,
    DATA_PROCESSED_DIR,
    EVENT_LOG_PARQUET,
    OUTPUTS_DIR,
    COL_CASE_ID,
    COL_ACTIVITY,
    COL_TIMESTAMP,
    COL_RESOURCE,
)

# The BPI 2019 log covers calendar year 2018 (with some bookkeeping events
# just before/after). Anything far outside this window is a data-quality
# issue in the source log, not a real business date.
VALID_TIMESTAMP_MIN = pd.Timestamp("2017-01-01", tz="UTC")
VALID_TIMESTAMP_MAX = pd.Timestamp("2020-01-01", tz="UTC")


def load_raw_xes(xes_path):
    """Load the XES log with pm4py and return it as a pandas DataFrame."""
    print(f"Reading XES log from {xes_path} (this can take a while for a 700MB+ file)...")
    log = pm4py.read_xes(str(xes_path))
    if isinstance(log, pd.DataFrame):
        df = log
    else:
        df = pm4py.convert_to_dataframe(log)
    print(f"Loaded {len(df):,} raw events.")
    return df


def standardise_columns(df):
    """Rename pm4py's XES-style column names to simple, readable ones."""
    rename_map = {
        "case:concept:name": COL_CASE_ID,
        "concept:name": COL_ACTIVITY,
        "time:timestamp": COL_TIMESTAMP,
        "org:resource": COL_RESOURCE,
    }
    df = df.rename(columns=rename_map)

    # Every remaining "case:X" column is a case-level attribute from SAP.
    # Strip the XES "case:" prefix so the Excel/report columns read cleanly,
    # e.g. "case:Item Category" -> "Item Category".
    further_renames = {}
    for col in df.columns:
        if col.startswith("case:"):
            further_renames[col] = col[len("case:"):]
    df = df.rename(columns=further_renames)

    return df


def parse_timestamps(df):
    df[COL_TIMESTAMP] = pd.to_datetime(df[COL_TIMESTAMP], utc=True, errors="coerce")
    return df


def run_data_quality_checks(df):
    """Compute DQ metrics without dropping or silently fixing anything."""
    checks = {}

    checks["total_events"] = len(df)
    checks["total_cases"] = df[COL_CASE_ID].nunique()

    null_counts = df.isnull().sum()
    null_summary = null_counts[null_counts > 0].sort_values(ascending=False)
    checks["columns_with_nulls"] = null_summary

    key_cols = [COL_CASE_ID, COL_ACTIVITY, COL_TIMESTAMP, COL_RESOURCE]
    key_cols = [c for c in key_cols if c in df.columns]
    duplicate_mask = df.duplicated(subset=key_cols, keep=False)
    checks["duplicate_event_rows"] = int(duplicate_mask.sum())

    out_of_range_mask = (df[COL_TIMESTAMP] < VALID_TIMESTAMP_MIN) | (
        df[COL_TIMESTAMP] > VALID_TIMESTAMP_MAX
    )
    out_of_range_mask = out_of_range_mask.fillna(True)  # unparsable timestamps count too
    checks["out_of_range_timestamp_events"] = int(out_of_range_mask.sum())
    checks["out_of_range_timestamp_pct"] = round(
        100 * out_of_range_mask.sum() / len(df), 4
    )

    # Keep the flag on the dataframe itself so later steps can see it,
    # rather than dropping the rows.
    df["is_timestamp_out_of_range"] = out_of_range_mask

    return checks, df


def write_dq_summary(checks, out_path):
    lines = []
    lines.append("P2P Invoice Exception Intelligence - Data Quality Summary")
    lines.append("=" * 60)
    lines.append(f"Total events: {checks['total_events']:,}")
    lines.append(f"Total cases (PO items): {checks['total_cases']:,}")
    lines.append(f"Duplicate event rows (same case/activity/timestamp/resource): {checks['duplicate_event_rows']:,}")
    lines.append(
        f"Events with out-of-range timestamp (outside {VALID_TIMESTAMP_MIN.date()} - "
        f"{VALID_TIMESTAMP_MAX.date()}): {checks['out_of_range_timestamp_events']:,} "
        f"({checks['out_of_range_timestamp_pct']}%) - flagged, not dropped"
    )
    lines.append("")
    lines.append("Columns with null values:")
    if len(checks["columns_with_nulls"]) == 0:
        lines.append("  (none)")
    else:
        for col, count in checks["columns_with_nulls"].items():
            pct = round(100 * count / checks["total_events"], 2)
            lines.append(f"  {col}: {count:,} ({pct}%)")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote DQ summary to {out_path}")


def main():
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    if not BPI_XES_PATH.exists():
        print(f"ERROR: raw event log not found at {BPI_XES_PATH}")
        print("Download BPI_Challenge_2019.xes and place it in data/raw/ first.")
        sys.exit(1)

    df = load_raw_xes(BPI_XES_PATH)
    df = standardise_columns(df)
    df = parse_timestamps(df)
    df = df.sort_values([COL_CASE_ID, COL_TIMESTAMP]).reset_index(drop=True)

    checks, df = run_data_quality_checks(df)
    write_dq_summary(checks, OUTPUTS_DIR / "data_quality_summary.txt")

    df.to_parquet(EVENT_LOG_PARQUET, index=False)
    print(f"Saved clean event log to {EVENT_LOG_PARQUET} ({len(df):,} rows, {len(df.columns)} columns).")
    print("Column list:", list(df.columns))


if __name__ == "__main__":
    main()
