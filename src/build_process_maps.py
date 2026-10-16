"""
Phase 6 - As-Is / To-Be process maps.

Draws two simple swimlane-free process diagrams (boxes + arrows) with
matplotlib and saves them as docs/process_map_as_is.png and
docs/process_map_to_be.png. These are also embedded into the PowerPoint deck
by build_deck.py.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from config import DOCS_DIR

BOX_COLOR = "#2E5C8A"
AI_COLOR = "#C65911"
TEXT_COLOR = "white"


def draw_box(ax, x, y, w, h, text, color=BOX_COLOR, fontsize=10):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.2,
        edgecolor="black",
        facecolor=color,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
             fontsize=fontsize, color=TEXT_COLOR, wrap=True, weight="bold")


def draw_arrow(ax, start, end, color="black", style="-"):
    arrow = FancyArrowPatch(
        start, end,
        arrowstyle="-|>", mutation_scale=15,
        linewidth=1.4, color=color, linestyle=style,
    )
    ax.add_patch(arrow)


def build_as_is():
    fig, ax = plt.subplots(figsize=(15, 4.5))
    ax.set_xlim(0, 14.8)
    ax.set_ylim(0, 4.5)
    ax.axis("off")

    box_w, box_h = 2.0, 1.2
    y = 2.2
    steps = [
        "Create\nPurchase Order\nItem",
        "Goods\nReceipt\nrecorded",
        "Vendor\ninvoice\narrives",
        "Record\nInvoice\nReceipt",
        "Manual 3-way\nmatch check\n(AP analyst)",
        "Clear Invoice\n/ Payment",
    ]
    xs = [0.3 + i * 2.3 for i in range(len(steps))]
    for x, label in zip(xs, steps):
        draw_box(ax, x, y, box_w, box_h, label)
    for i in range(len(xs) - 1):
        draw_arrow(ax, (xs[i] + box_w, y + box_h / 2), (xs[i + 1], y + box_h / 2))

    # Exception branch
    draw_box(ax, xs[4], 0.3, box_w, box_h, "Exceptions found\n-> manual rework,\npayment block", color="#8FAADC", fontsize=9)
    draw_arrow(ax, (xs[4] + box_w / 2, y), (xs[4] + box_w / 2, 0.3 + box_h))

    ax.set_title("As-Is: Manual Three-Way Match in the P2P Process", fontsize=14, weight="bold")
    fig.tight_layout()
    fig.savefig(DOCS_DIR / "process_map_as_is.png", dpi=150)
    plt.close(fig)


def build_to_be():
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 6)
    ax.axis("off")

    box_w, box_h = 2.1, 1.1
    y_top = 4.2
    steps = [
        "Create\nPurchase Order\nItem",
        "Goods\nReceipt\nrecorded",
        "Vendor\ninvoice\narrives",
        "Record\nInvoice\nReceipt",
    ]
    xs = [0.3 + i * 2.3 for i in range(len(steps))]
    for x, label in zip(xs, steps):
        draw_box(ax, x, y_top, box_w, box_h, label)
    for i in range(len(xs) - 1):
        draw_arrow(ax, (xs[i] + box_w, y_top + box_h / 2), (xs[i + 1], y_top + box_h / 2))

    ai_y = 2.3
    ai_x = xs[2]
    draw_box(ax, ai_x, ai_y, box_w, box_h, "Claude: extract\ndocument fields\n(JSON schema)", color=AI_COLOR)
    draw_arrow(ax, (xs[2] + box_w / 2, y_top), (ai_x + box_w / 2, ai_y + box_h))

    match_x = xs[3]
    draw_box(ax, match_x, ai_y, box_w, box_h, "Automated\n3-way match &\nexception rules", color=AI_COLOR)
    draw_arrow(ax, (ai_x + box_w, ai_y + box_h / 2), (match_x, ai_y + box_h / 2))
    draw_arrow(ax, (xs[3] + box_w / 2, y_top), (match_x + box_w / 2, ai_y + box_h))

    triage_x = match_x + 2.3
    draw_box(ax, triage_x, ai_y, box_w, box_h, "Claude: exception\nsummary, root cause,\npriority (JSON)", color=AI_COLOR)
    draw_arrow(ax, (match_x + box_w, ai_y + box_h / 2), (triage_x, ai_y + box_h / 2))

    review_x = triage_x
    review_y = 0.4
    draw_box(ax, review_x, review_y, box_w, box_h, "Human AP reviewer\n(human-in-the-loop)\napprove / reject / escalate", color="#548235")
    draw_arrow(ax, (triage_x + box_w / 2, ai_y), (review_x + box_w / 2, review_y + box_h))

    final_x = review_x - 2.3
    draw_box(ax, final_x, review_y, box_w, box_h, "Clear Invoice\n/ Payment\n(human-approved)")
    draw_arrow(ax, (review_x, review_y + box_h / 2), (final_x + box_w, review_y + box_h / 2))

    audit_x = final_x - 2.3
    draw_box(ax, audit_x, review_y, box_w, box_h, "Audit trail:\nAI output + human\ndecision logged", color="#7F7F7F")
    draw_arrow(ax, (final_x, review_y + box_h / 2), (audit_x + box_w, review_y + box_h / 2))

    ax.set_title("To-Be: AI-Assisted P2P Exception Triage with Human-in-the-Loop Controls", fontsize=13, weight="bold")
    fig.tight_layout()
    fig.savefig(DOCS_DIR / "process_map_to_be.png", dpi=150)
    plt.close(fig)


def main():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    build_as_is()
    build_to_be()
    print(f"Saved process maps to {DOCS_DIR}")


if __name__ == "__main__":
    main()
