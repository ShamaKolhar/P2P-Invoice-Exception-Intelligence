# Data Provenance

Raw data is **not** committed to this repository (see `.gitignore`). This
file documents exactly where to get it and what was downloaded for this
project's own run.

## 1. BPI Challenge 2019 event log

- **What it is**: a real, anonymised SAP purchase-order event log from a
  multinational coatings and paints company, covering ~60 subsidiaries.
- **Source**: 4TU.ResearchData — https://data.4tu.nl/articles/_/12715853/1
- **DOI**: 10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1
- **Licence**: 4TU.ResearchData open-access terms (see the dataset page for
  the exact licence).
- **Citation**: van Dongen, B. (BPI Challenge 2019 event log), 4TU.ResearchData.
- **File used**: `BPI_Challenge_2019.xes` (direct file download via the
  dataset's own file API), MD5 `4eb909242351193a61e1c15b9c3cc814`, 728,558,522
  bytes.
- **Date downloaded**: 2026-10-14.
- **Counts after loading** (see `outputs/data_quality_summary.txt` for the
  full data-quality report): 1,595,923 events across 251,734 purchase-order
  line items (cases), 42 distinct activities.
- **Where to put it**: `data/raw/BPI_Challenge_2019.xes`.

## 2. ICDAR-SROIE 2019 scanned receipts

- **What it is**: real scanned retail receipts with ground-truth
  key-information labels (company, address, date, total). Referred to
  throughout this project as "receipts / invoice-like documents", not
  invoices, since they are retail receipts, not purchase invoices.
- **Source (corrected mirror used here)**: GitHub —
  https://github.com/zzzDavid/ICDAR-2019-SROIE (`data/img/` and `data/key/`)
- **Original dataset**: ICDAR 2019 Robust Reading Challenge on Scanned
  Receipts OCR and Information Extraction —
  https://rrc.cvc.uab.es/?ch=13&com=introduction
- **Licence**: MIT (per the GitHub mirror's LICENSE file); original
  competition data provided for research use by the ICDAR-SROIE organisers.
- **Sample used**: a reproducible random sample of 40 documents (seed 42) out
  of the 626 available in the mirror, downloaded via
  `scripts`/`download_sroie_sample.py`-style logic into
  `data/raw/sroie_sample/img/` (receipt images) and
  `data/raw/sroie_sample/key/` (ground-truth JSON labels). All 40 downloaded
  successfully; the exact sampled document IDs are recorded in
  `data/raw/sroie_sample/sample_manifest.txt`.
- **Date downloaded**: 2026-10-14.
- **Where to put it**: `data/raw/sroie_sample/img/*.jpg` and
  `data/raw/sroie_sample/key/*.json`.

## How to re-download

### BPI Challenge 2019
1. Visit https://data.4tu.nl/articles/_/12715853/1
2. Download `BPI_Challenge_2019.xes` and place it at `data/raw/BPI_Challenge_2019.xes`.

### SROIE sample
1. The images/labels live at
   `https://raw.githubusercontent.com/zzzDavid/ICDAR-2019-SROIE/master/data/img/<id>.jpg`
   and `.../data/key/<id>.json` for IDs `000`–`625`.
2. Download whichever sample you want (this project used a seeded random
   sample of 40) into `data/raw/sroie_sample/img/` and
   `data/raw/sroie_sample/key/` respectively.

## What is NOT included

No raw data files are committed to Git. `run_all.py` will fail fast with a
clear message if `data/raw/BPI_Challenge_2019.xes` is missing.
