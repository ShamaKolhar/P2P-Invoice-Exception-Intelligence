"""
Phase 6 - PowerPoint deck.

Builds outputs/deck/P2P_Exception_Intelligence.pptx. Every number on every
slide is read from the pipeline's own outputs (case_features.parquet,
ai_extraction_results.parquet, ai_triage_results.parquet). The only text
allowed to be an estimate is the implementation roadmap slide, and it is
explicitly labelled "illustrative assumption".
"""

import pandas as pd
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

from config import (
    CASE_FEATURES_PARQUET,
    DATA_PROCESSED_DIR,
    OUTPUTS_CHARTS_DIR,
    OUTPUTS_DECK_DIR,
    DOCS_DIR,
)

EXTRACTION_RESULTS_PATH = DATA_PROCESSED_DIR / "ai_extraction_results.parquet"
TRIAGE_RESULTS_PATH = DATA_PROCESSED_DIR / "ai_triage_results.parquet"

NAVY = RGBColor(0x2E, 0x5C, 0x8A)
DARK = RGBColor(0x26, 0x26, 0x26)
ORANGE = RGBColor(0xC6, 0x59, 0x11)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def add_title_slide(prs, title, subtitle):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(0.8), Inches(2.6), Inches(11.7), Inches(1.5))
    tf = box.text_frame
    tf.text = title
    tf.paragraphs[0].font.size = Pt(40)
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.color.rgb = NAVY

    sub_box = slide.shapes.add_textbox(Inches(0.8), Inches(4.0), Inches(11.7), Inches(1.0))
    sub_tf = sub_box.text_frame
    sub_tf.text = subtitle
    sub_tf.paragraphs[0].font.size = Pt(18)
    sub_tf.paragraphs[0].font.color.rgb = DARK
    return slide


def add_content_slide(prs, title, bullets, bullet_font_size=16):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.2), Inches(0.9))
    tf = title_box.text_frame
    tf.text = title
    tf.word_wrap = True
    tf.paragraphs[0].font.size = Pt(26)
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.color.rgb = NAVY

    body_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(11.7), Inches(5.6))
    body_tf = body_box.text_frame
    body_tf.word_wrap = True
    for i, bullet in enumerate(bullets):
        p = body_tf.paragraphs[0] if i == 0 else body_tf.add_paragraph()
        p.text = f"• {bullet}"
        p.font.size = Pt(bullet_font_size)
        p.font.color.rgb = DARK
        p.space_after = Pt(10)
    return slide


def add_image_slide(prs, title, image_path, caption=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.2), Inches(0.8))
    tf = title_box.text_frame
    tf.text = title
    tf.paragraphs[0].font.size = Pt(26)
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.color.rgb = NAVY

    if image_path and image_path.exists():
        slide.shapes.add_picture(str(image_path), Inches(0.6), Inches(1.3), width=Inches(12.1))
    else:
        box = slide.shapes.add_textbox(Inches(0.8), Inches(3.2), Inches(11), Inches(1))
        box.text_frame.text = f"(chart not available: {image_path.name if image_path else 'n/a'})"

    if caption:
        cap_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.9), Inches(11.7), Inches(0.5))
        cap_tf = cap_box.text_frame
        cap_tf.text = caption
        cap_tf.paragraphs[0].font.size = Pt(13)
        cap_tf.paragraphs[0].font.italic = True
        cap_tf.paragraphs[0].font.color.rgb = DARK
    return slide


def compute_kpis(case_features):
    cycle = case_features["cycle_time_days"].dropna()
    kpis = {
        "total_cases": len(case_features),
        "exception_rate": round(100 * case_features["has_exception"].mean(), 1),
        "total_net_worth": case_features["net_worth_eur"].sum(skipna=True),
        "exception_net_worth": case_features.loc[case_features["has_exception"], "net_worth_eur"].sum(skipna=True),
        "median_cycle_time": round(cycle.median(), 1) if len(cycle) else None,
        "p90_cycle_time": round(cycle.quantile(0.90), 1) if len(cycle) else None,
    }
    return kpis


def build_deck():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    case_features = pd.read_parquet(CASE_FEATURES_PARQUET)
    kpis = compute_kpis(case_features)

    ai_extraction_available = EXTRACTION_RESULTS_PATH.exists()
    ai_triage_available = TRIAGE_RESULTS_PATH.exists()

    # 1. Title
    add_title_slide(
        prs,
        "P2P Invoice Exception Intelligence",
        "AI-assisted exception detection and triage for Procure-to-Pay — a portfolio project",
    )

    # 2. Executive summary
    exec_bullets = [
        f"Analysed {kpis['total_cases']:,} real purchase-order line items from the BPI Challenge 2019 SAP event log.",
        f"{kpis['exception_rate']}% of cases trigger at least one of six rule-based exceptions, representing "
        f"EUR {kpis['exception_net_worth']:,.0f} of net order value.",
        f"Median cycle time from PO creation to invoice clearing is {kpis['median_cycle_time']} days "
        f"(90th percentile: {kpis['p90_cycle_time']} days).",
    ]
    if ai_extraction_available:
        extraction_df = pd.read_parquet(EXTRACTION_RESULTS_PATH)
        norm_cols = [c for c in extraction_df.columns if c.endswith("_normalised_match")]
        avg_acc = round(extraction_df[norm_cols].mean().mean() * 100, 1)
        exec_bullets.append(
            f"A Claude vision prototype extracted key fields from {len(extraction_df)} real scanned receipts "
            f"at {avg_acc}% average normalised accuracy — promising, but not yet reliable enough to remove human review."
        )
    else:
        exec_bullets.append("GenAI extraction and triage steps were not run for this build (no API key supplied).")
    exec_bullets.append(
        "Recommendation: pilot an AI-assisted triage layer that drafts exception summaries and root causes for "
        "human AP reviewers — not an auto-approval system."
    )
    add_content_slide(prs, "Executive Summary", exec_bullets)

    # 3. Context
    add_content_slide(prs, "Procure-to-Pay and Why Exceptions Matter", [
        "Procure-to-Pay (P2P) covers the flow from raising a purchase order through goods/service receipt, "
        "invoice receipt, and payment clearing.",
        "Three-way matching compares the Purchase Order, the Goods Receipt, and the Invoice before payment is "
        "released — it is a core financial control against overpayment and fraud.",
        "Exceptions (price/quantity changes, payment blocks, sequence breaks, repeated invoices) slow down the "
        "process, increase manual rework for AP teams, and create audit and compliance exposure.",
        "This project mines a real SAP event log to find where exceptions actually occur, then prototypes a "
        "generative-AI layer to help AP analysts triage them faster.",
    ])

    # 4. As-Is process map
    add_image_slide(
        prs, "As-Is: Manual Three-Way Match",
        DOCS_DIR / "process_map_as_is.png",
        "Goods receipt, invoice receipt, and matching are reconciled manually by the AP analyst today.",
    )

    # 5. What the data shows
    add_image_slide(
        prs, f"What the Data Shows: {kpis['exception_rate']}% Exception Rate Across {kpis['total_cases']:,} Cases",
        OUTPUTS_CHARTS_DIR / "02_cycle_time_distribution.png",
        "Cycle time is right-skewed: most items clear quickly, but a long tail drives the 90th-percentile exception rule (E6).",
    )

    # 6. Exception hotspots
    add_image_slide(
        prs, "Exception Hotspots Concentrate in a Small Set of Categories and Vendors",
        OUTPUTS_CHARTS_DIR / "01_exception_rate_by_category.png",
        "See the Vendor Hotspots sheet in the Excel workbook for the full vendor-level breakdown.",
    )

    # 7. GenAI extraction results
    if ai_extraction_available:
        extraction_df = pd.read_parquet(EXTRACTION_RESULTS_PATH)
        field_acc = {
            f: round(extraction_df[f"{f}_normalised_match"].mean() * 100, 1)
            for f in ["vendor", "address", "document_date", "total_amount"]
        }
        weakest_field = min(field_acc, key=field_acc.get)
        add_image_slide(
            prs, f"GenAI Document Extraction: Strong on Totals, Weaker on {weakest_field.replace('_', ' ').title()}",
            OUTPUTS_CHARTS_DIR / "05_extraction_accuracy_by_field.png",
            f"Tested on {len(extraction_df)} real scanned receipts (ICDAR-SROIE) with ground-truth labels; "
            f"{weakest_field.replace('_', ' ')} accuracy was the weakest field at {field_acc[weakest_field]}%.",
        )
    else:
        add_content_slide(prs, "GenAI Document Extraction", [
            "AI extraction was not run for this build (no ANTHROPIC_API_KEY was supplied).",
            "Design: Claude vision receives each scanned receipt image and a strict JSON schema prompt "
            "(vendor, address, date, total, currency).",
            "Evaluation plan: compare exact-match and normalised-match accuracy per field against ICDAR-SROIE "
            "ground truth labels.",
        ])

    # 8. To-Be process map
    add_image_slide(
        prs, "To-Be: AI-Assisted Triage with Human-in-the-Loop Controls",
        DOCS_DIR / "process_map_to_be.png",
        "Claude drafts the exception summary and root cause; a human AP reviewer approves, rejects, or escalates every case.",
    )

    # 9. Controls & risks
    add_content_slide(prs, "Controls and Risks", [
        "Hallucination: the triage prompt instructs the model to answer 'insufficient information' rather than "
        "guess, and is restricted to facts present in the case's own event history.",
        "Data privacy: document images and event data are processed only through the Anthropic API under the "
        "project's own key; no data is used to train models; API keys are never logged or committed.",
        "Audit trail: every AI output (extraction JSON, triage JSON) is cached and stored alongside the case ID "
        "so a reviewer can trace exactly what the model saw and said.",
        "Segregation of duties: the AI never clears an invoice or removes a payment block — it only drafts a "
        "recommendation that a human reviewer must action.",
    ])

    # 10. Implementation roadmap
    add_content_slide(prs, "Implementation Roadmap: Pilot to Scale", [
        "Pilot (0-3 months): run AI-assisted triage alongside existing manual review for one vendor category; "
        "track reviewer agreement with AI root-cause suggestions.",
        "[Illustrative assumption] If reviewers accept AI-drafted summaries for ~60% of cases without edits, "
        "analyst time per exception could fall meaningfully — this is an assumption to validate in the pilot, "
        "not a measured result.",
        "Scale (3-9 months): extend to all 3-way-match categories, add a feedback loop so rejected AI suggestions "
        "are logged and reviewed for prompt improvements.",
        "Throughout: keep a human-in-the-loop approval step and an audit log at every stage.",
    ])

    # 11. Appendix
    add_content_slide(prs, "Appendix: Data Sources and Method", [
        "BPI Challenge 2019 event log - 4TU.ResearchData, DOI 10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1 "
        "(real, anonymised SAP purchase-order data).",
        "ICDAR-SROIE 2019 scanned receipts - real receipt images with ground-truth key-information labels, "
        "used here as invoice-like documents (not purchase invoices) for the extraction test.",
        "Method: pandas for process mining and exception-rule computation; Claude (claude-haiku-5-5 by default) "
        "for document extraction and exception triage; openpyxl / python-pptx for reporting.",
        "Limitations: exception rules are a starting set, not an exhaustive AP control framework; GenAI accuracy "
        "was measured on a small sample; see the Explanation Guide for full limitations.",
    ], bullet_font_size=15)

    OUTPUTS_DECK_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUTS_DECK_DIR / "P2P_Exception_Intelligence.pptx"
    prs.save(out_path)
    print(f"Saved {out_path} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    build_deck()
