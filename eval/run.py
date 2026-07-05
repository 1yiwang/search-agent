"""Run golden-case evaluation against the live research pipeline.

Usage (from repo root):
    backend/.venv/Scripts/python.exe -m eval.run
    backend/.venv/Scripts/python.exe -m eval.run --case python-312
    backend/.venv/Scripts/python.exe -m eval.run --list
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Allow imports from backend/
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from config import config  # noqa: E402
from agent import run_research  # noqa: E402
from models import ResearchRequest  # noqa: E402

from eval.validate import GoldenCase, validate_report  # noqa: E402

import yaml  # noqa: E402


def load_cases(path: Path | None = None) -> list[GoldenCase]:
    cases_path = path or (_REPO_ROOT / "eval" / "golden_cases.yaml")
    data = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    return [GoldenCase.from_dict(item) for item in data.get("cases", [])]


async def run_case(case: GoldenCase, attempt: int) -> tuple[bool, list[str], float]:
    started = time.perf_counter()
    request = ResearchRequest(topic=case.topic, max_sources=case.max_sources)
    report = await run_research(request)
    elapsed = time.perf_counter() - started
    errors = validate_report(report, case)
    if errors and attempt > 1:
        errors = [f"(retry {attempt})"] + errors
    return (len(errors) == 0, errors, elapsed)


async def run_all(
    cases: list[GoldenCase],
    max_retries: int = 1,
) -> int:
    if not config.llm_api_key:
        print("ERROR: LLM_API_KEY is not set. Configure backend/.env before running eval.")
        return 2

    passed = 0
    failed = 0

    print(f"Running {len(cases)} golden case(s) (max_retries={max_retries})...\n")

    for case in cases:
        ok = False
        last_errors: list[str] = []
        elapsed = 0.0

        for attempt in range(1, max_retries + 2):
            if attempt > 1:
                print(f"  retry {case.id} (attempt {attempt})...")
            ok, last_errors, elapsed = await run_case(case, attempt)
            if ok:
                break

        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case.id} ({elapsed:.1f}s) - {case.topic}")
        if ok:
            passed += 1
        else:
            failed += 1
            for err in last_errors:
                print(f"       - {err}")

    print(f"\n{passed}/{len(cases)} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search Agent golden-case eval")
    parser.add_argument("--case", help="Run a single case id")
    parser.add_argument("--list", action="store_true", help="List available cases")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Retry failed cases this many times (default: 1)",
    )
    parser.add_argument(
        "--cases-file",
        type=Path,
        default=None,
        help="Path to golden_cases.yaml",
    )
    args = parser.parse_args(argv)

    cases = load_cases(args.cases_file)

    if args.list:
        for case in cases:
            print(f"{case.id}: {case.topic}")
        return 0

    if args.case:
        cases = [c for c in cases if c.id == args.case]
        if not cases:
            print(f"Unknown case id: {args.case}")
            return 1

    return asyncio.run(run_all(cases, max_retries=args.max_retries))


if __name__ == "__main__":
    raise SystemExit(main())
