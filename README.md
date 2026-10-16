# P2P Invoice Exception Intelligence

An AI-assisted Procure-to-Pay (P2P) exception detection and triage
prototype, built as a portfolio project on real, publicly available data.

## Problem

Procure-to-Pay teams reconcile purchase orders, goods receipts, and
invoices (three-way matching) before releasing payment. Exceptions - price
or quantity changes, payment blocks, out-of-sequence receipts, repeated
invoices, unusually long cycle times - slow this down and create audit and
compliance exposure. This project asks two questions of a real SAP event
log: where do exceptions actually occur, and can generative AI help an AP
analyst triage them faster without removing human control?

## Approach

1. **Process mining**: load the real BPI Challenge 2019 SAP purchase-order
   event log, compute cycle times and process variants per PO line item, and
   flag six exception types from the actual event sequences.
2. **GenAI document extraction**: send real scanned receipt images
   (ICDAR-SROIE, with ground-truth labels) to Claude's vision API and score
   field-level extraction accuracy honestly, including where it fails.
3. **GenAI exception triage**: send the top exception cases' real event
   history to Claude and ask for a short summary, a likely root cause (from a
   fixed list), a recommended action, and a priority - with an explicit
   instruction to say "insufficient information" rather than guess. The
   output is a draft for a human AP reviewer, not an auto-approval.
4. **Reporting**: an Excel exception log and a consulting-style PowerPoint
   deck, both regenerated from the pipeline's own numbers.

## Architecture

```
BPI_Challenge_2019.xes --> prepare_data.py --> bpi2019_events.parquet
                                                      |
                                                      v
                                           p2p_exceptions.py
                                                      |
                                                      v
                                          case_features.parquet
                                                      |
                        +-----------------------------+-----------------------------+
                        |                                                           |
                        v                                                           v
SROIE receipts --> ai_extract.py --> ai_extraction_results.parquet      ai_triage.py --> ai_triage_results.parquet
                        |                                                           |
                        +-----------------------------+-----------------------------+
                                                      |
                                       build_process_maps.py / build_charts.py
                                                      |
                                      build_excel.py            build_deck.py
                                           |                          |
                                           v                          v
                          P2P_Exception_Log.xlsx      P2P_Exception_Intelligence.pptx
```

## How to run

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

1. Download the raw data (see `data/README.md` for exact sources and URLs)
   and place it under `data/raw/`.
2. Copy `.env.example` to `.env` and add your own `ANTHROPIC_API_KEY` if you
   want to run the GenAI steps.
3. Run the full pipeline:

```bash
python run_all.py                 # full run, needs ANTHROPIC_API_KEY
python run_all.py --skip-ai       # process mining + reporting only, no API key needed
python run_all.py --sample 20     # use a smaller AI-extraction sample
```

Outputs land in `outputs/excel/`, `outputs/charts/`, and `outputs/deck/`.

## Data sources

- **BPI Challenge 2019** event log - 4TU.ResearchData,
  DOI 10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1. Real, anonymised SAP
  purchase-order data from a multinational coatings and paints company.
- **ICDAR-SROIE 2019** - real scanned receipt images with ground-truth
  key-information labels (company, address, date, total), used here as
  invoice-like documents, not purchase invoices.

Full provenance, licence, and citation details are in `data/README.md`.

## Key results

From the latest pipeline run on the real BPI Challenge 2019 log (full
numbers in `outputs/excel/P2P_Exception_Log.xlsx`, "Summary KPIs" sheet):

- 251,734 real purchase-order line items analysed, from 1,595,923 events.
- 34.1% of cases trigger at least one of six rule-based exceptions,
  representing EUR 520.7M of the EUR 1.035B total net order value analysed.
- Payment blocks are the single largest exception driver (55,934 cases),
  followed by long cycle time (18,368) and quantity changes (17,590).
- Zero cases were found where an invoice was recorded before goods receipt
  in the "3-way match, invoice after GR" category — the GR-based invoice
  verification control appears well-enforced in this log (see `tests/test_exceptions.py`).
- Median cycle time (PO creation to invoice clearing) is 77.0 days; the
  90th percentile is 126.2 days.
- GenAI document extraction (Claude vision, `claude-haiku-5-5`) on 40 real
  ICDAR-SROIE receipts: 100% normalised accuracy on total amount, 97.5% on
  address, 82.5% on vendor, but only 45.0% on document date — honestly the
  weakest field, driven mostly by date-format mismatches rather than wrong
  values.
- GenAI exception triage on the top 25 exception cases by net worth
  produced grounded, fact-based summaries and root causes (21 of 25
  attributed to "Duplicate or repeated invoice submission"); every output
  is stored with a blank `human_review` column — the AI drafts a
  recommendation, it never approves a payment.

## Limitations

- The six exception rules are a starting control set, not an exhaustive AP
  control framework.
- GenAI extraction accuracy was measured on a small sample (default 40
  documents) to keep API cost low; it is not a production accuracy estimate.
- SROIE receipts are used as a stand-in for invoice-like documents because a
  real, public, ground-truth-labelled invoice image dataset was not
  available; they are retail receipts, not purchase invoices.
- This is a prototype for a portfolio application, not a deployed system,
  and has not been used by any real company.

## Next steps

- Expand the exception rule set with AP stakeholders and validate thresholds
  (e.g. the E6 cycle-time percentile) against business tolerance.
- Pilot the AI triage step against live reviewer feedback to measure actual
  acceptance/edit rates, rather than the illustrative assumption in the deck.
