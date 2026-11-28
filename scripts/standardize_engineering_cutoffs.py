#!/usr/bin/env python3
"""Keep the latest cutoff row for each normalized engineering course and seat."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
    "data/josaa-cutoffs.json": ("records",),
    "data/kcet-cutoffs.json": ("kea", "comedk"),
}


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").upper()
    text = re.sub(r"\bENGG\b", "ENGINEERING", text)
    text = re.sub(r"\bAND\b|&", "AND", text)
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def year_number(row: dict[str, Any]) -> int:
    try:
        return int(row.get("year") or 0)
    except (TypeError, ValueError):
        return 0


def round_number(row: dict[str, Any]) -> int:
    match = re.search(r"\d+", str(row.get("round") or ""))
    return int(match.group()) if match else 0


def identity(row: dict[str, Any]) -> tuple[str, ...]:
    college = row.get("collegeCode") or row.get("college")
    program = row.get("program") or row.get("course") or row.get("branch")
    return (
        normalize(college),
        normalize(program),
        normalize(row.get("branch")),
        normalize(row.get("exam")),
        normalize(row.get("quota")),
        normalize(row.get("category")),
        normalize(row.get("gender")),
    )


def deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(identity(row), []).append(row)

    kept = []
    for key, candidates in grouped.items():
        latest_year = max(year_number(row) for row in candidates)
        same_year = [row for row in candidates if year_number(row) == latest_year]
        latest_round = max(round_number(row) for row in same_year)
        finalists = [row for row in same_year if round_number(row) == latest_round]
        closing_ranks = {str(row.get("closingRank")) for row in finalists}
        if len(closing_ranks) > 1:
            raise ValueError(
                f"Conflicting closing ranks for {key} at {latest_year}, "
                f"round {latest_round}: {sorted(closing_ranks)}"
            )
        kept.append(finalists[0])
    return kept


def assert_2026_ranks_preserved(
    original: list[dict[str, Any]], standardized: list[dict[str, Any]], label: str
) -> None:
    latest_2026: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in original:
        if year_number(row) != 2026:
            continue
        key = identity(row)
        current = latest_2026.get(key)
        if current is None or round_number(row) > round_number(current):
            latest_2026[key] = row

    selected = {identity(row): row for row in standardized}
    for key, original_row in latest_2026.items():
        actual = selected.get(key)
        if (
            actual is None
            or year_number(actual) != 2026
            or actual.get("closingRank") != original_row.get("closingRank")
        ):
            raise ValueError(
                f"{label} changed or dropped a 2026 closing rank for {key}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="report duplicate rows without writing dataset files",
    )
    args = parser.parse_args()

    changes: list[tuple[Path, dict[str, Any], dict[str, list[dict[str, Any]]]]] = []
    for relative_path, sections in DATASETS.items():
        path = ROOT / relative_path
        data = json.loads(path.read_text(encoding="utf-8"))
        updated_sections = {}
        for section in sections:
            original = data[section]
            standardized = deduplicate(original)
            assert_2026_ranks_preserved(original, standardized, section)
            updated_sections[section] = standardized
            print(
                f"{relative_path} [{section}]: {len(original)} rows -> "
                f"{len(standardized)} rows; {len(original) - len(standardized)} "
                "duplicate historical/alias rows removed"
            )
        changes.append((path, data, updated_sections))

    if args.check_only:
        return 0

    for path, data, sections in changes:
        for section, rows in sections.items():
            data[section] = rows
        years = sorted(
            {
                year_number(row)
                for section in sections.values()
                for row in section
                if year_number(row)
            }
        )
        data["meta"]["years"] = years
        data["meta"]["updated"] = "2026-11-28"
        data["meta"]["roundPolicy"] = (
            "One row per normalized college/program/branch/exam/quota/category/"
            "gender; retain the latest year and round, preferring 2026 where "
            "available and the latest older record only when no 2026 row exists."
        )
        path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
