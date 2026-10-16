"""
Phase 6 - charts.

Builds 6 matplotlib charts from the pipeline's own outputs (never from
invented numbers): exception rate by item category, cycle-time distribution,
top process variants, vendor hotspots, AI extraction accuracy by field, and
AI triage priority mix. Any chart whose source data isn't available (e.g. no
API key was used) is skipped with a printed message rather than faked.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from config import (
    CASE_FEATURES_PARQUET,
    DATA_PROCESSED_DIR,
    OUTPUTS_CHARTS_DIR,
)

EXTRACTION_RESULTS_PATH = DATA_PROCESSED_DIR / "ai_extraction_results.parquet"
TRIAGE_RESULTS_PATH = DATA_PROCESSED_DIR / "ai_triage_results.parquet"

FLAG_COLUMNS = [
    "E1_invoice_before_gr",
    "E2_price_change",
    "E3_quantity_change",
    "E4_payment_block",
    "E5_repeated_invoice_receipt",
    "E6_long_cycle_time",
]

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 11,
})


def chart_exception_rate_by_category(case_features, category_col, out_path):
    if category_col not in case_features.columns:
        print(f"  skipped (no '{category_col}' column)")
        return
    grouped = case_features.groupby(category_col)["has_exception"].mean().sort_values(ascending=False) * 100
    fig, ax = plt.subplots(figsize=(9, 5))
    grouped.plot(kind="bar", ax=ax, color="#2E5C8A")
    ax.set_title("Exception Rate by Item Category")
    ax.set_xlabel("Item Category")
    ax.set_ylabel("Exception Rate (%)")
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  saved {out_path.name}")


def chart_cycle_time_distribution(case_features, out_path):
    cycle = case_features["cycle_time_days"].dropna()
    cycle = cycle[(cycle >= 0) & (cycle < cycle.quantile(0.99))]
    if cycle.empty:
        print("  skipped (no cycle time data)")
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(cycle, bins=40, color="#2E5C8A")
    ax.set_title("Cycle Time Distribution (Create PO Item to Clear Invoice)")
    ax.set_xlabel("Cycle Time (days)")
    ax.set_ylabel("Number of Cases")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  saved {out_path.name}")


def chart_top_variants(case_features, out_path, top_n=10):
    if "variant" not in case_features.columns:
        print("  skipped (no variant column)")
        return
    counts = case_features["variant"].value_counts().head(top_n)
    labels = [f"Variant {i+1}" for i in range(len(counts))]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(labels[::-1], counts.values[::-1], color="#2E5C8A")
    ax.set_title(f"Top {top_n} Process Variants by Case Count")
    ax.set_xlabel("Number of Cases")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  saved {out_path.name}")


def chart_vendor_hotspots(case_features, vendor_col, out_path, top_n=10):
    if vendor_col not in case_features.columns:
        print(f"  skipped (no '{vendor_col}' column)")
        return
    grouped = (
        case_features.groupby(vendor_col)
        .agg(exception_count=("has_exception", "sum"), case_count=("has_exception", "size"))
    )
    grouped = grouped[grouped["case_count"] >= 20]
    grouped["exception_rate"] = 100 * grouped["exception_count"] / grouped["case_count"]
    grouped = grouped.sort_values("exception_rate", ascending=False).head(top_n)
    if grouped.empty:
        print("  skipped (no vendors with enough volume)")
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(grouped.index.astype(str)[::-1], grouped["exception_rate"].values[::-1], color="#C65911")
    ax.set_title(f"Top {top_n} Vendor Hotspots (Exception Rate, min. 20 cases)")
    ax.set_xlabel("Exception Rate (%)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  saved {out_path.name}")


def chart_extraction_accuracy(out_path):
    if not EXTRACTION_RESULTS_PATH.exists():
        print("  skipped (no AI extraction results - run with an API key first)")
        return
    df = pd.read_parquet(EXTRACTION_RESULTS_PATH)
    fields = ["vendor", "address", "document_date", "total_amount"]
    exact = [df[f"{f}_exact_match"].mean() * 100 for f in fields]
    norm = [df[f"{f}_normalised_match"].mean() * 100 for f in fields]

    fig, ax = plt.subplots(figsize=(9, 5))
    x = range(len(fields))
    width = 0.35
    ax.bar([i - width / 2 for i in x], exact, width, label="Exact match", color="#2E5C8A")
    ax.bar([i + width / 2 for i in x], norm, width, label="Normalised match", color="#8FAADC")
    ax.set_xticks(list(x))
    ax.set_xticklabels(fields)
    ax.set_title("AI Extraction Accuracy by Field")
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 100)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  saved {out_path.name}")


def chart_triage_priority_mix(out_path):
    if not TRIAGE_RESULTS_PATH.exists():
        print("  skipped (no AI triage results - run with an API key first)")
        return
    df = pd.read_parquet(TRIAGE_RESULTS_PATH)
    counts = df["priority"].value_counts().reindex(["High", "Medium", "Low"]).fillna(0)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(counts.index, counts.values, color=["#C00000", "#ED7D31", "#548235"])
    ax.set_title("AI Triage - Priority Mix (Top Exception Cases)")
    ax.set_ylabel("Number of Cases")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  saved {out_path.name}")


def main():
    OUTPUTS_CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    case_features = pd.read_parquet(CASE_FEATURES_PARQUET)

    category_col = next((c for c in case_features.columns if "item category" in c.lower()), None)
    vendor_col = next((c for c in case_features.columns if "vendor" in c.lower()), None)

    print("Building charts...")
    chart_exception_rate_by_category(case_features, category_col, OUTPUTS_CHARTS_DIR / "01_exception_rate_by_category.png")
    chart_cycle_time_distribution(case_features, OUTPUTS_CHARTS_DIR / "02_cycle_time_distribution.png")
    chart_top_variants(case_features, OUTPUTS_CHARTS_DIR / "03_top_process_variants.png")
    chart_vendor_hotspots(case_features, vendor_col, OUTPUTS_CHARTS_DIR / "04_vendor_hotspots.png")
    chart_extraction_accuracy(OUTPUTS_CHARTS_DIR / "05_extraction_accuracy_by_field.png")
    chart_triage_priority_mix(OUTPUTS_CHARTS_DIR / "06_triage_priority_mix.png")


if __name__ == "__main__":
    main()
