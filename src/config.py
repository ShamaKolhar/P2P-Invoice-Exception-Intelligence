"""Shared paths and constants used across the pipeline scripts."""

from pathlib import Path

# Project layout
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
AI_CACHE_DIR = DATA_PROCESSED_DIR / "ai_cache"
OUTPUTS_DIR = ROOT_DIR / "outputs"
OUTPUTS_EXCEL_DIR = OUTPUTS_DIR / "excel"
OUTPUTS_CHARTS_DIR = OUTPUTS_DIR / "charts"
OUTPUTS_DECK_DIR = OUTPUTS_DIR / "deck"
DOCS_DIR = ROOT_DIR / "docs"
PROMPTS_DIR = ROOT_DIR / "prompts"

# Source files
BPI_XES_PATH = DATA_RAW_DIR / "BPI_Challenge_2019.xes"
EVENT_LOG_PARQUET = DATA_PROCESSED_DIR / "bpi2019_events.parquet"
CASE_FEATURES_PARQUET = DATA_PROCESSED_DIR / "case_features.parquet"
SROIE_SAMPLE_DIR = DATA_RAW_DIR / "sroie_sample"

# Standardised column names used after prepare_data.py has run
COL_CASE_ID = "case_id"
COL_ACTIVITY = "activity"
COL_TIMESTAMP = "timestamp"
COL_RESOURCE = "resource"

# Random seed used for every sampling step, so results are reproducible
RANDOM_SEED = 42

# Default sample size for the GenAI document-extraction step (Phase 4)
DEFAULT_AI_EXTRACT_SAMPLE = 40

# Default number of top exception cases sent to the LLM for triage (Phase 5)
DEFAULT_AI_TRIAGE_TOP_N = 25

DEFAULT_CLAUDE_MODEL = "claude-haiku-5-5"
