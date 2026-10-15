"""
Thin wrapper around the Anthropic (Claude) API shared by ai_extract.py and
ai_triage.py: API key / model loading, a simple disk cache so reruns don't
re-spend tokens, and a small retry helper.

The API key is only ever read from the environment (via .env). It is never
printed, logged, or written to any output file.
"""

import hashlib
import json
import time
import os

from dotenv import load_dotenv
import anthropic

from config import AI_CACHE_DIR, DEFAULT_CLAUDE_MODEL

load_dotenv()


def get_model():
    return os.environ.get("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)


def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in, "
            "or run with --skip-ai."
        )
    return anthropic.Anthropic(api_key=api_key)


def _cache_path(cache_key):
    AI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
    return AI_CACHE_DIR / f"{digest}.json"


def cache_get(cache_key):
    path = _cache_path(cache_key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def cache_set(cache_key, value):
    path = _cache_path(cache_key)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def extract_text(response):
    """Return the text content from a Messages API response. Some models
    can return a thinking block before the text block, so this looks for
    the text block by type rather than assuming content[0] is text."""
    for block in response.content:
        if block.type == "text":
            return block.text
    raise ValueError("No text block found in API response")


def call_with_retry(fn, max_attempts=3, delay_seconds=2):
    """Call fn() and retry on exception, with a short fixed backoff."""
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - we want to retry any API error
            last_error = exc
            print(f"  API call failed (attempt {attempt}/{max_attempts}): {exc}")
            if attempt < max_attempts:
                time.sleep(delay_seconds)
    raise last_error
