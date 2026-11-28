#!/usr/bin/env python3
"""Import user-supplied NEET stipend, fee, and bond details into the dataset.

Usage: python scripts/import_neet_college_details.py "path/to/Neet Colleges list.txt"
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "neet-cutoffs.json"
HEADER = ["College", "Course", "Internship Stipend", "Annual Fee", "Service Bond"]
BOND_START = re.compile(
    r"^(?:no\b|(?:\d+\s*[-–]\s*)?\d+\s*(?:years?|yrs?|months?|mos?|days?)\b|"
    r"optional\b|compulsory\b|service\b|rural\b|bond\b|mandatory\b|state\s+service\b)",
    re.IGNORECASE,
)
LEADING_QUOTA = re.compile(
    r"^(?:(?:country|minority|women|female|general|open|sc|st|obc|ews|quota|"
    r"puducherry|ut|domicile|aiq)\s+)+"
)
TOKEN_ALIASES = {
    "govt": "government",
    "gmc": "government medical college",
    "gdc": "government dental college",
    "gmch": "government medical college hospital",
    "inst": "institute",
    "instt": "institute",
    "med": "medical",
    "medcial": "medical",
    "coll": "college",
    "dent": "dental",
    "hospt": "hospital",
    "hosp": "hospital",
    "sce": "science",
    "scie": "science",
    "sciences": "science",
    "mangalore": "mangaluru",
    "manglore": "mangaluru",
    "bangalore": "bengaluru",
    "pondicherry": "puducherry",
    "tumkur": "tumakuru",
    "bellary": "ballari",
    "calicut": "kozhikode",
    "vizag": "visakhapatnam",
    "dehradoon": "dehradun",
}
STATE_NAMES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jammu and kashmir",
    "jharkhand", "karnataka", "kerala", "madhya pradesh", "maharashtra",
    "manipur", "meghalaya", "mizoram", "nagaland", "odisha", "punjab",
    "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura",
    "uttar pradesh", "uttarakhand", "west bengal", "delhi", "puducherry",
    "ladakh", "hp", "ap", "mp", "up", "j k",
}
GENERIC_TOKENS = {
    "of", "and", "the", "a", "an", "dr", "late", "shri", "sri",
}
FALLBACK_GENERIC_TOKENS = GENERIC_TOKENS | {
    "government", "medical", "dental", "college", "hospital", "institute",
    "science", "research", "center", "university", "autonomous", "state",
    "memorial", "institution", "school", "health", "deemed", "faculty",
}


def tokens(value: str) -> list[str]:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    result: list[str] = []
    for token in re.findall(r"[a-z0-9]+", value.lower()):
        result.extend(TOKEN_ALIASES.get(token, token).split())
    return result


def normalized(value: str) -> str:
    return " ".join(tokens(value))


def source_name_without_state(value: str) -> str:
    parts = value.split(",")
    while len(parts) > 1 and normalized(parts[-1].strip()) in STATE_NAMES:
        parts.pop()
    return ",".join(parts).strip()


def target_title(value: str) -> str:
    value = re.sub(r"\([^)]*\)", " ", value)
    return LEADING_QUOTA.sub("", normalized(value))


def parse_detail_row(row: list[str], line_number: int) -> dict[str, str]:
    if len(row) < 5:
        raise ValueError(f"line {line_number}: expected at least five CSV fields")

    fragments = row[2:]
    stipend_end = next(
        (index for index, value in enumerate(fragments) if "/month" in value.lower()),
        None,
    )
    if stipend_end is None:
        raise ValueError(f"line {line_number}: stipend does not end in /month")

    bond_start = next(
        (index for index, value in enumerate(fragments) if BOND_START.match(value.strip())),
        None,
    )
    if bond_start is None or bond_start <= stipend_end:
        raise ValueError(f"line {line_number}: could not locate service-bond field")

    stipend = ",".join(fragments[: stipend_end + 1]).strip()
    annual_fee = ",".join(fragments[stipend_end + 1 : bond_start]).strip()
    service_bond = ",".join(fragments[bond_start:]).strip()
    if not stipend or not annual_fee or not service_bond:
        raise ValueError(f"line {line_number}: one or more detail fields are empty")

    return {
        "internshipStipendText": stipend,
        "annualFeeText": annual_fee,
        "serviceBondText": service_bond,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="user-provided five-column text/CSV file")
    parser.add_argument("--dataset", type=Path, default=DATASET, help="NEET JSON dataset path")
    args = parser.parse_args()

    with args.source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows or rows[0] != HEADER:
        raise ValueError(f"expected source header: {','.join(HEADER)}")

    dataset: dict[str, Any] = json.loads(args.dataset.read_text(encoding="utf-8"))
    targets: dict[str, set[str]] = defaultdict(set)
    for record in dataset.get("records", []):
        college = record.get("college")
        course = str(record.get("course") or "").upper()
        if college and course:
            targets[course].add(college)
    target_titles = {
        (course, college): target_title(college)
        for course, colleges in targets.items()
        for college in colleges
    }

    source_entries: list[dict[str, Any]] = []
    alias_owners: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    fallback_ambiguities = 0
    for index, row in enumerate(rows[1:], start=2):
        college, course = row[0].strip(), row[1].strip().upper()
        if course not in {"MBBS", "BDS"}:
            raise ValueError(f"line {index}: unsupported course {course!r}")
        details = parse_detail_row(row, index)
        source_clean = source_name_without_state(college)
        source_match_name = re.sub(r"\([^)]*\)", " ", source_clean)
        query = normalized(source_match_name).strip()
        source_tokens = set(tokens(source_match_name)) - GENERIC_TOKENS
        location_tokens = set(tokens(source_clean.split(",")[-1]))
        source_specific_tokens = source_tokens - FALLBACK_GENERIC_TOKENS - location_tokens

        candidates = [
            target
            for target in sorted(targets[course])
            if query and target_titles[(course, target)].startswith(query)
        ]
        if "soa" in tokens(college):
            candidates = [
                target for target in candidates
                if "kalinga" not in tokens(target) and "kiit" not in tokens(target)
            ]
        if "kiit" in tokens(college):
            candidates = [
                target for target in candidates
                if "kalinga" in tokens(target) or "kiit" in tokens(target)
            ]

        match_strength = 2 if candidates else 0
        if not candidates and len(source_tokens) >= 2 and source_specific_tokens:
            possible = [
                target for target in sorted(targets[course])
                if source_tokens.issubset(set(tokens(target)))
            ]
            if len(possible) == 1:
                candidates = possible
                match_strength = 1
            elif possible:
                fallback_ambiguities += 1

        entry: dict[str, Any] = {
            "sourceBatchIndex": len(source_entries) + 1,
            "sourceCollegeName": college,
            "aliases": [],
            "course": course,
            **details,
            "visibleCitationNames": [],
            "attribution": "User-provided Neet Colleges list.txt; unverified",
        }
        source_entries.append(entry)
        for target in candidates:
            alias_owners[(course, target)].append((len(source_entries) - 1, match_strength))

    for (course, alias), owners in alias_owners.items():
        strongest = max(strength for _, strength in owners)
        best_owners = {index for index, strength in owners if strength == strongest}
        if len(best_owners) == 1:
            source_entries[best_owners.pop()]["aliases"].append(alias)

    dataset["medicalCollegeDetails"] = {
        entry["sourceCollegeName"]: entry for entry in source_entries
    }
    matched_entries = sum(bool(entry["aliases"]) for entry in source_entries)
    matched_aliases = sum(len(entry["aliases"]) for entry in source_entries)
    course_counts: dict[str, int] = defaultdict(int)
    for entry in source_entries:
        course_counts[entry["course"]] += 1
    dataset["medicalCollegeDetailsImport"] = {
        "source": "User-provided Neet Colleges list.txt",
        "status": "unverified; the supplied file includes no source URLs and values were not independently confirmed",
        "entryCount": len(source_entries),
        "courseCounts": dict(sorted(course_counts.items())),
        "matchedSourceEntries": matched_entries,
        "unmatchedSourceEntries": len(source_entries) - matched_entries,
        "matchedCutoffCollegeAliases": matched_aliases,
        "ambiguousFallbackSourceEntries": fallback_ambiguities,
        "note": (
            "Only course-specific, confidently matched aliases are linked to cutoff records. "
            "Unmatched entries are retained without aliases, so their details remain pending "
            "on cutoff cards. The source file contains only the rows counted above."
        ),
    }
    args.dataset.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Imported {len(source_entries)} rows "
        f"({dict(sorted(course_counts.items()))}); "
        f"{matched_entries} entries matched to {matched_aliases} cutoff aliases; "
        f"{len(source_entries) - matched_entries} left unmatched."
    )


if __name__ == "__main__":
    main()
