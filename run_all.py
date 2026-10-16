"""
Phase 7 - orchestration.

Runs the whole pipeline in order: data prep -> process mining / exception
rules -> (optional) GenAI extraction + triage -> process maps -> charts ->
Excel -> PowerPoint deck.

Usage:
    python run_all.py                  # full run (needs ANTHROPIC_API_KEY)
    python run_all.py --skip-ai        # skip the two GenAI steps
    python run_all.py --sample 20      # use a smaller AI extraction sample
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

load_dotenv(ROOT_DIR / ".env")


def run_step(script_name, extra_args=None):
    cmd = [sys.executable, str(SRC_DIR / script_name)] + (extra_args or [])
    print(f"\n{'=' * 70}\nRunning {script_name} {' '.join(extra_args or [])}\n{'=' * 70}")
    result = subprocess.run(cmd, cwd=str(SRC_DIR))
    if result.returncode != 0:
        print(f"\n{script_name} failed with exit code {result.returncode}. Stopping.")
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-ai", action="store_true", help="skip the GenAI extraction and triage steps")
    parser.add_argument("--sample", type=int, default=None, help="AI extraction sample size (default: 40)")
    args = parser.parse_args()

    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))

    run_step("prepare_data.py")
    run_step("p2p_exceptions.py")

    if args.skip_ai:
        print("\n--skip-ai set: skipping ai_extract.py and ai_triage.py")
    elif not has_api_key:
        print("\nANTHROPIC_API_KEY not set: skipping ai_extract.py and ai_triage.py "
              "(the Excel/deck will note that AI steps were not run).")
    else:
        extract_args = ["--sample", str(args.sample)] if args.sample else []
        run_step("ai_extract.py", extract_args)
        run_step("ai_triage.py")

    run_step("build_process_maps.py")
    run_step("build_charts.py")
    run_step("build_excel.py")
    run_step("build_deck.py")

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
