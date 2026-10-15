"""
Phase 3 - P2P process mining and exception rules.

Works purely from the cleaned event log (data/processed/bpi2019_events.parquet).
For every rule, the activity names actually present in the log are looked up
by keyword first; a rule is only computed if all the activities/columns it
needs are confirmed to exist. Anything that can't be matched is recorded in
outputs/rules_skipped.txt instead of being silently assumed.

Output: data/processed/case_features.parquet, one row per PO item (case),
with cycle time, process variant, the six exception flags (E1-E6), and the
case-level attributes needed for the Excel/PPTX outputs.
"""

import json
import pandas as pd
import numpy as np

from config import (
    EVENT_LOG_PARQUET,
    CASE_FEATURES_PARQUET,
    OUTPUTS_DIR,
    COL_CASE_ID,
    COL_ACTIVITY,
    COL_TIMESTAMP,
)

RULES_SKIPPED_PATH = OUTPUTS_DIR / "rules_skipped.txt"
ACTIVITY_LIST_PATH = OUTPUTS_DIR / "activity_list.txt"


def find_activity(unique_activities, keywords):
    """Return the single activity name containing all keywords (case-insensitive),
    or None if zero or more than one match is found."""
    matches = [
        a for a in unique_activities
        if all(k.lower() in a.lower() for k in keywords)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def find_column(columns, keywords):
    matches = [
        c for c in columns
        if all(k.lower() in c.lower() for k in keywords)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def resolve_schema(df):
    """Look up the real activity and column names this rule set depends on.
    Returns a dict of resolved names (value is None if not found) and writes
    a log of anything that could not be resolved."""
    activities = df[COL_ACTIVITY].unique().tolist()
    columns = df.columns.tolist()

    schema = {
        "act_create_po_item": find_activity(activities, ["create", "purchase order item"]),
        "act_goods_receipt": find_activity(activities, ["record", "goods receipt"]),
        "act_invoice_receipt": find_activity(activities, ["record", "invoice receipt"]),
        "act_clear_invoice": find_activity(activities, ["clear", "invoice"]),
        "act_change_price": find_activity(activities, ["change", "price"]),
        "act_change_quantity": find_activity(activities, ["change", "quantity"]),
        "act_set_payment_block": find_activity(activities, ["set", "payment block"]),
        "act_remove_payment_block": find_activity(activities, ["remove", "payment block"]),
        "col_item_category": find_column(columns, ["item category"]) or find_column(columns, ["item type"]),
        "col_net_worth": find_column(columns, ["cumulative net worth"]),
        "col_vendor": find_column(columns, ["vendor"]),
        "col_company": find_column(columns, ["company"]),
        "col_doc_type": find_column(columns, ["document type"]),
    }

    skipped = {k: v for k, v in schema.items() if v is None}
    with open(RULES_SKIPPED_PATH, "w", encoding="utf-8") as f:
        f.write("Fields/activities that could not be uniquely resolved in the data:\n")
        for k in skipped:
            f.write(f"  - {k}\n")
        if not skipped:
            f.write("  (none - every field needed by the rules was found)\n")

    with open(ACTIVITY_LIST_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(activities)))

    print("Resolved schema:")
    for k, v in schema.items():
        print(f"  {k}: {v}")

    return schema


def build_case_level_attributes(df, schema):
    """One row per case with the case-level (SAP) attributes we need downstream."""
    case_cols = [COL_CASE_ID]
    for key in ["col_item_category", "col_vendor", "col_company", "col_doc_type"]:
        col = schema.get(key)
        if col and col not in case_cols:
            case_cols.append(col)

    case_attrs = df[case_cols].drop_duplicates(subset=[COL_CASE_ID]).set_index(COL_CASE_ID)
    return case_attrs


def compute_cycle_time(df, schema):
    """Cycle time per case: first 'Create Purchase Order Item' to first 'Clear Invoice'."""
    start_act = schema["act_create_po_item"]
    end_act = schema["act_clear_invoice"]
    if start_act is None or end_act is None:
        return pd.Series(dtype="float64", name="cycle_time_days")

    starts = (
        df[df[COL_ACTIVITY] == start_act]
        .groupby(COL_CASE_ID)[COL_TIMESTAMP].min()
    )
    ends = (
        df[df[COL_ACTIVITY] == end_act]
        .groupby(COL_CASE_ID)[COL_TIMESTAMP].min()
    )
    cycle = (ends - starts).dt.total_seconds() / 86400.0
    cycle.name = "cycle_time_days"
    return cycle


def compute_variants(df):
    """The activity sequence per case, used for top-variant analysis."""
    variants = (
        df.sort_values([COL_CASE_ID, COL_TIMESTAMP])
        .groupby(COL_CASE_ID)[COL_ACTIVITY]
        .apply(lambda s: " -> ".join(s))
    )
    variants.name = "variant"
    return variants


def flag_e1_invoice_before_gr(df, schema, case_attrs):
    """E1: invoice recorded before goods receipt, but only for cases in the
    '3-way match, invoice after GR' category (where GR must come first)."""
    cat_col = schema.get("col_item_category")
    gr_act = schema.get("act_goods_receipt")
    iv_act = schema.get("act_invoice_receipt")
    if cat_col is None or gr_act is None or iv_act is None:
        return pd.Series(dtype="bool", name="E1_invoice_before_gr")

    target_cases = case_attrs[
        case_attrs[cat_col].astype(str).str.contains("invoice after gr", case=False, na=False)
    ].index

    gr_time = df[df[COL_ACTIVITY] == gr_act].groupby(COL_CASE_ID)[COL_TIMESTAMP].min()
    iv_time = df[df[COL_ACTIVITY] == iv_act].groupby(COL_CASE_ID)[COL_TIMESTAMP].min()

    both = pd.DataFrame({"gr": gr_time, "iv": iv_time}).dropna()
    both = both.loc[both.index.intersection(target_cases)]
    flag = both["iv"] < both["gr"]
    flag.name = "E1_invoice_before_gr"
    return flag


def flag_e2_price_change(df, schema):
    act = schema.get("act_change_price")
    if act is None:
        return pd.Series(dtype="bool", name="E2_price_change")
    cases_with = df.loc[df[COL_ACTIVITY] == act, COL_CASE_ID].unique()
    flag = pd.Series(True, index=pd.Index(cases_with, name=COL_CASE_ID), name="E2_price_change")
    return flag


def flag_e3_quantity_change(df, schema):
    act = schema.get("act_change_quantity")
    if act is None:
        return pd.Series(dtype="bool", name="E3_quantity_change")
    cases_with = df.loc[df[COL_ACTIVITY] == act, COL_CASE_ID].unique()
    flag = pd.Series(True, index=pd.Index(cases_with, name=COL_CASE_ID), name="E3_quantity_change")
    return flag


def flag_e4_payment_block(df, schema):
    acts = [a for a in (schema.get("act_set_payment_block"), schema.get("act_remove_payment_block")) if a]
    if not acts:
        return pd.Series(dtype="bool", name="E4_payment_block")
    cases_with = df.loc[df[COL_ACTIVITY].isin(acts), COL_CASE_ID].unique()
    flag = pd.Series(True, index=pd.Index(cases_with, name=COL_CASE_ID), name="E4_payment_block")
    return flag


def flag_e5_repeated_invoice_receipt(df, schema):
    act = schema.get("act_invoice_receipt")
    if act is None:
        return pd.Series(dtype="bool", name="E5_repeated_invoice_receipt")
    counts = df[df[COL_ACTIVITY] == act].groupby(COL_CASE_ID).size()
    flag = counts[counts > 1] > 0
    flag.name = "E5_repeated_invoice_receipt"
    return flag


def flag_e6_long_cycle_time(cycle_time, case_attrs, schema):
    """Long cycle time: above the 90th percentile within the case's own
    item category (falls back to a global 90th percentile if the category
    column isn't available)."""
    if cycle_time.empty:
        return pd.Series(dtype="bool", name="E6_long_cycle_time")

    cat_col = schema.get("col_item_category")
    df_ct = cycle_time.to_frame()
    if cat_col is not None:
        df_ct = df_ct.join(case_attrs[[cat_col]], how="left")
        thresholds = df_ct.groupby(cat_col)["cycle_time_days"].transform(
            lambda s: s.quantile(0.90)
        )
    else:
        thresholds = cycle_time.quantile(0.90)

    flag = df_ct["cycle_time_days"] > thresholds
    flag.name = "E6_long_cycle_time"
    return flag


def main():
    df = pd.read_parquet(EVENT_LOG_PARQUET)
    print(f"Loaded {len(df):,} events across {df[COL_CASE_ID].nunique():,} cases.")

    schema = resolve_schema(df)
    case_attrs = build_case_level_attributes(df, schema)

    cycle_time = compute_cycle_time(df, schema)
    variants = compute_variants(df)
    activity_count = df.groupby(COL_CASE_ID).size()
    activity_count.name = "activity_count"

    e1 = flag_e1_invoice_before_gr(df, schema, case_attrs)
    e2 = flag_e2_price_change(df, schema)
    e3 = flag_e3_quantity_change(df, schema)
    e4 = flag_e4_payment_block(df, schema)
    e5 = flag_e5_repeated_invoice_receipt(df, schema)
    e6 = flag_e6_long_cycle_time(cycle_time, case_attrs, schema)

    case_features = case_attrs.copy()
    case_features = case_features.join(cycle_time, how="left")
    case_features = case_features.join(variants, how="left")
    case_features = case_features.join(activity_count, how="left")

    for flag in [e1, e2, e3, e4, e5, e6]:
        if flag.empty:
            case_features[flag.name] = False
        else:
            case_features[flag.name] = case_features.index.isin(flag[flag].index)

    flag_cols = [c for c in case_features.columns if c.startswith("E") and "_" in c]
    case_features["exception_count"] = case_features[flag_cols].sum(axis=1)
    case_features["has_exception"] = case_features["exception_count"] > 0

    net_worth_col = schema.get("col_net_worth")
    if net_worth_col is not None:
        # Net worth is recorded per event (it can change); use the last known
        # value per case as the case's net worth.
        last_values = (
            df.sort_values([COL_CASE_ID, COL_TIMESTAMP])
            .groupby(COL_CASE_ID)[net_worth_col].last()
        )
        case_features["net_worth_eur"] = last_values
    else:
        case_features["net_worth_eur"] = np.nan

    case_features = case_features.reset_index()

    CASE_FEATURES_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    case_features.to_parquet(CASE_FEATURES_PARQUET, index=False)

    print(f"Saved case-level features to {CASE_FEATURES_PARQUET} ({len(case_features):,} cases).")
    print("Exception rate:", round(100 * case_features["has_exception"].mean(), 2), "%")
    for col in flag_cols:
        print(f"  {col}: {int(case_features[col].sum()):,} cases")


if __name__ == "__main__":
    main()
