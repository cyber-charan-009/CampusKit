#!/usr/bin/env python3
"""Merge supplied engineering placement lists into the JEE and KCET datasets."""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME_ALIASES = (
    (r"\biiitdm\b", "indian institute information technology design manufacturing"),
    (r"\biiitm\b", "indian institute information technology management"),
    (r"\biiest\b", "indian institute engineering science technology"),
    (r"\bmnnit\b", "motilal nehru national institute technology"),
    (r"\bmnit\b", "malaviya national institute technology"),
    (r"\bmanit\b", "maulana azad national institute technology"),
    (r"\bsvnit\b", "sardar vallabhbhai national institute technology"),
    (r"\bvnit\b", "visvesvaraya national institute technology"),
    (r"\bnielit\b", "national institute electronics information technology"),
    (r"\bniftem\b", "national institute food technology entrepreneurship management"),
    (r"\bnerist\b", "north eastern regional institute science technology"),
    (r"\biitram\b", "institute infrastructure technology research management"),
    (r"\bpdpm\b", "pandit dwarka prasad mishra"),
    (r"\biiit\b", "institute information technology"),
    (r"\bcentral university of jharkhand\b", "cu jharkhand"),
    (r"\bdonbosco\b", "don bosco"),
    (r"\bgurunanak\b", "guru nanak"),
    (r"\bmsscet\b", "m s sheshagiri college engineering technology"),
    (r"\biit\b", "indian institute technology"),
    (r"\bnit\b", "national institute technology"),
    (r"\babv\b", "atal bihari vajpayee"),
    (r"\bcsvtu\b", "chhattisgarh swami vivekananda technical university"),
    (r"\biet\b", "institute engineering technology"),
    (r"\bengg\b", "engineering"),
    (r"\btech\b", "technology"),
)
PLACE_ALIASES = (
    (r"\bbangalore\b", "bengaluru"),
    (r"\bbelgaum\b", "belagavi"),
    (r"\bmangalore\b", "mangaluru"),
    (r"\bmysore\b", "mysuru"),
    (r"\bchickamagalur\b", "chikkamagaluru"),
    (r"\bchikmagalur\b", "chikkamagaluru"),
    (r"\bmoodabidre\b", "moodabidri"),
    (r"\bmoodbidri\b", "moodabidri"),
    (r"\btumkur\b", "tumakuru"),
    (r"\bsoldevanahalli\b", "soladevanahalli"),
    (r"\btathguni\b", "tataguni"),
    (r"\bkalaburgi\b", "kalaburagi"),
    (r"\bkalburgi\b", "kalaburagi"),
    (r"\bkumbalagodu\b", "kumbalgodu"),
    (r"\bchickkaballapur\b", "chikkaballapur"),
    (r"\bchickballapur\b", "chikkaballapur"),
    (r"\bg u j r a t\b", "gujarat"),
    (r"\bgujrat\b", "gujarat"),
    (r"\bk okrajar\b", "kokrajhar"),
    (r"\bkokrajar\b", "kokrajhar"),
    (r"\bchittoor\b", "chittoor"),
    (r"\bvivekanada\b", "vivekananda"),
    (r"\bvivekananada\b", "vivekananda"),
    (r"\bintitute\b", "institute"),
    (r"\braod\b", "road"),
    (r"\bvidyavardhaka\b", "vidya vardhaka"),
    (r"\bunivesity\b", "university"),
    (r"\badhichunchanagiri\b", "adichunchanagiri"),
)
GENERIC_NAME_WORDS = {
    "a",
    "an",
    "and",
    "area",
    "at",
    "autonomous",
    "by",
    "campus",
    "college",
    "dist",
    "district",
    "engineering",
    "for",
    "from",
    "govt",
    "government",
    "in",
    "institute",
    "institution",
    "main",
    "near",
    "of",
    "opp",
    "post",
    "road",
    "the",
    "technology",
    "university",
    "village",
    "with",
}
LPA_PATTERN = re.compile(r"₹\s*([\d,]+(?:\.\d+)?)\s*LPA", re.IGNORECASE)
HEADING_PATTERN = re.compile(r"^\s*\d+\.\s*(.*?)\s*\|\s*Highest:\s*(.+?)\s*$", re.IGNORECASE)
BRANCH_PATTERN = re.compile(r"^\s*•?\s*(.*?)\s*:\s*(.+?)\s*$")
LEGACY_FIELDS = {
    "averagePackageLPA",
    "minimumPackageLPA",
    "highestPackageLPA",
    "placementNote",
    "placementSource",
}


def normalized_words(value: str) -> set[str]:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    def clean_parenthetical(match: re.Match[str]) -> str:
        contents = match.group(1)
        if contents.isupper() and re.search(r"[A-Z]{2,}", contents):
            return " "
        return f" {contents} "

    text = re.sub(r"\(([^)]*)\)", clean_parenthetical, text).lower()
    text = re.sub(r"(?<=\w)'s\b", "s", text)
    text = text.replace("&", " and ")
    for pattern, replacement in NAME_ALIASES + PLACE_ALIASES:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"\bformerly\b|\bknown as\b|\bformer\b|\bautonomous\b", " ", text)
    tokens = re.findall(r"[a-z]+", text)
    combined: list[str] = []
    index = 0
    while index < len(tokens):
        if len(tokens[index]) == 1:
            end = index
            while end < len(tokens) and len(tokens[end]) == 1:
                end += 1
            if end - index > 1:
                combined.append("".join(tokens[index:end]))
                index = end
                continue
        combined.append(tokens[index])
        index += 1
    return set(combined)


def normalized_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"(?<=\w)'s\b", "s", text).replace("&", " and ")
    for pattern, replacement in NAME_ALIASES + PLACE_ALIASES:
        text = re.sub(pattern, replacement, text)
    tokens = re.findall(r"[a-z]+", text)
    combined: list[str] = []
    index = 0
    while index < len(tokens):
        if len(tokens[index]) == 1:
            end = index
            while end < len(tokens) and len(tokens[end]) == 1:
                end += 1
            if end - index > 1:
                combined.append("".join(tokens[index:end]))
                index = end
                continue
        combined.append(tokens[index])
        index += 1
    return " ".join(combined)


def parse_lpa(value: str) -> float | None:
    match = LPA_PATTERN.search(value)
    return float(match.group(1).replace(",", "")) if match else None


def branch_families(value: str) -> set[str]:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\bdat\s+a\s+science\b", "data science", text)
    compact = re.sub(r"[^a-z0-9]+", " ", text).strip()
    result: set[str] = set()

    if re.search(r"\bcse\b|\bcs\b|computer science|computer engineering", text):
        result.add("CSE")
    if re.search(r"\bise\b|information science", text):
        result.add("ISE")
    if re.search(r"\bit\b|information technology", text):
        result.add("IT")
    if (
        re.search(r"\bai\s*/\s*ds\b|\baiml\b|\bai\b|\bartificial intelligence\b", text)
        or "data science" in text
        or "machine learning" in text
        or re.search(r"\bml\b", text)
    ):
        result.add("AI/DS")
    if re.search(r"\bece\b|electronics?\s*(?:and|&)\s*(?:communication|telecommunication)", text):
        result.add("ECE")
    if re.search(r"\beee\b|\bee\b|electrical", text):
        result.add("EE")

    aliases = {
        "Maths & Computing": ("mathematics and computing", "math and computing", "mnc"),
        "Engineering Physics": ("engineering physics",),
        "Planning": ("b plan", "planning"),
        "Mechanical": ("mechanical",),
        "Civil": ("civil",),
        "Aeronautical": ("aeronautical",),
        "Aerospace": ("aerospace", "aero space"),
        "Agricultural": ("agricultural", "agriculture"),
        "Biotechnology": ("biotechnology", "biotech", "bio technology"),
        "Biomedical": ("biomedical", "bio medical"),
        "Chemical": ("chemical",),
        "Mechatronics": ("mechatronics",),
        "Automobile": ("automobile", "automotive"),
        "Robotics": ("robotics", "robotic"),
        "VLSI": ("vlsi", "very large scale integration"),
        "Instrumentation": ("instrumentation",),
        "Industrial": ("industrial",),
        "Architecture": ("architecture",),
        "Mining": ("mining",),
        "Petroleum": ("petroleum",),
        "Marine": ("marine",),
        "Textile": ("textile",),
        "Food": ("food engineering",),
        "Ceramics": ("ceramic",),
    }
    for family, terms in aliases.items():
        if any(term in compact for term in terms):
            result.add(family)
    if "electronics" in compact and not any(term in compact for term in ("vlsi", "instrumentation")):
        result.add("ECE")
    return result


def parse_source(path: Path, exam: str) -> tuple[list[dict[str, Any]], int]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_count = 0
    for index, line in enumerate(lines):
        heading = HEADING_PATTERN.match(line)
        if not heading:
            continue
        college, highest_display = heading.groups()
        if "duplicate" in line.lower():
            duplicate_count += 1
            continue
        key = normalized_key(college)
        if not key or key in seen:
            duplicate_count += 1
            continue
        seen.add(key)

        highest_numeric = parse_lpa(highest_display)
        if highest_numeric is None:
            raise ValueError(f"{path.name}: missing numeric highest package for {college!r}")

        branches: list[dict[str, Any]] = []
        if index + 1 < len(lines):
            for segment in lines[index + 1].split("|"):
                branch_match = BRANCH_PATTERN.match(segment)
                if not branch_match:
                    continue
                branch, display_value = branch_match.groups()
                numeric = parse_lpa(display_value)
                if numeric is None:
                    continue
                branches.append(
                    {
                        "sourceBranch": branch.strip(),
                        "branchAvgLpa": f"Avg: {display_value.strip()}",
                        "branchAvgLpaNumeric": numeric,
                    }
                )
        if not branches:
            raise ValueError(f"{path.name}: no branch averages found for {college!r}")

        entries.append(
            {
                "college": college.strip(),
                "exam": exam,
                "highestLpaDisplay": f"Highest: {highest_display.strip()}",
                "highestLpaNumeric": highest_numeric,
                "branches": branches,
                "placementSource": path.name,
            }
        )
    return entries, duplicate_count


def match_college(
    source_name: str, candidates: list[str], candidate_words: dict[str, set[str]]
) -> tuple[str | None, list[tuple[float, str]]]:
    source_words = normalized_words(source_name)
    if not source_words:
        return None, []
    exact = [name for name in candidates if candidate_words[name] == source_words]
    if len(exact) == 1:
        return exact[0], [(1.0, exact[0])]

    token_frequency: dict[str, int] = defaultdict(int)
    for words in candidate_words.values():
        for word in words:
            token_frequency[word] += 1
    token_weight = {
        word: 1 + math.log((len(candidates) + 1) / (frequency + 1))
        for word, frequency in token_frequency.items()
    }

    ranked: list[tuple[float, str]] = []
    for name in candidates:
        target_words = candidate_words[name]
        overlap = len(source_words & target_words)
        coverage = overlap / len(source_words)
        union = overlap / len(source_words | target_words)
        source_core = source_words - GENERIC_NAME_WORDS
        target_core = target_words - GENERIC_NAME_WORDS
        shared_core = source_core & target_core
        core_weight = sum(token_weight.get(word, 1) for word in source_core)
        shared_weight = sum(token_weight.get(word, 1) for word in shared_core)
        core_coverage = shared_weight / core_weight if core_weight else coverage
        union_weight = sum(
            token_weight.get(word, 1) for word in source_core | target_core
        )
        core_union = shared_weight / union_weight if union_weight else union
        sequence = SequenceMatcher(
            None, " ".join(sorted(source_words)), " ".join(sorted(target_words))
        ).ratio()
        score = 0.70 * core_coverage + 0.18 * core_union + 0.08 * coverage + 0.04 * sequence
        ranked.append((score, name))
    ranked.sort(reverse=True)

    if not ranked:
        return None, []
    best_score, best_name = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0
    source_core = source_words - GENERIC_NAME_WORDS
    shared = source_core & (candidate_words[best_name] - GENERIC_NAME_WORDS)
    core_coverage = len(shared) / len(source_core) if source_core else 1
    same_core_variant = False
    if len(ranked) > 1:
        best_core = candidate_words[best_name] - GENERIC_NAME_WORDS
        second_core = candidate_words[ranked[1][1]] - GENERIC_NAME_WORDS
        same_core_variant = best_core == second_core
    if (
        best_score >= 0.48
        and core_coverage >= 0.50
        and (best_score - second_score >= 0.02 or (best_score >= 0.80 and same_core_variant))
    ):
        return best_name, ranked[:3]
    return None, ranked[:3]


def branch_average(entry: dict[str, Any], row: dict[str, Any]) -> dict[str, Any] | None:
    row_families = branch_families(str(row.get("branch", ""))) | branch_families(
        str(row.get("program", ""))
    )
    best: tuple[int, int, dict[str, Any]] | None = None
    for average in entry["branches"]:
        spec = average["sourceBranch"]
        spec_families = set()
        for component in spec.split("/"):
            spec_families.update(branch_families(component))
        shared = row_families & spec_families
        if shared:
            score = (len(shared), -len(spec_families), average)
            if best is None or score[:2] > best[:2]:
                best = score
    return best[2] if best else None


def remove_legacy_fields(value: Any) -> None:
    if isinstance(value, dict):
        for key in list(value):
            if key in LEGACY_FIELDS or key.lower().startswith("annualfee"):
                del value[key]
            else:
                remove_legacy_fields(value[key])
    elif isinstance(value, list):
        for item in value:
            remove_legacy_fields(item)


def attach_placement(row: dict[str, Any], entry: dict[str, Any]) -> None:
    row["highestLpaDisplay"] = entry["highestLpaDisplay"]
    row["highestLpaNumeric"] = entry["highestLpaNumeric"]
    average = branch_average(entry, row)
    row["branchAvgLpa"] = average["branchAvgLpa"] if average else None
    row["branchAvgLpaNumeric"] = average["branchAvgLpaNumeric"] if average else None
    row["placementSource"] = entry["placementSource"]


def placement_report(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "highestLpaDisplay": entry["highestLpaDisplay"],
        "highestLpaNumeric": entry["highestLpaNumeric"],
        "placementSource": entry["placementSource"],
        "branchPlacements": entry["branches"],
    }


def merge_group(
    data: dict[str, Any],
    dataset_key: str,
    entries: list[dict[str, Any]],
    prefix: str,
    check_only: bool,
) -> tuple[int, list[dict[str, Any]]]:
    rows = data[dataset_key]
    candidates = sorted({str(row["college"]) for row in rows if row.get("college")})
    candidate_words = {name: normalized_words(name) for name in candidates}
    matched_count = 0
    placement_only: list[dict[str, Any]] = []
    placement_map: dict[str, Any] = {}

    for entry in entries:
        matched, alternatives = match_college(entry["college"], candidates, candidate_words)
        if matched is None:
            placement_only.append(
                {
                    **entry,
                    "matchCandidates": [
                        {"score": round(score, 4), "college": name}
                        for score, name in alternatives
                    ],
                }
            )
            continue
        matched_count += 1
        matches = [matched]
        best_score = alternatives[0][0] if alternatives else 1
        best_core = candidate_words[matched] - GENERIC_NAME_WORDS
        for score, candidate in alternatives[1:]:
            candidate_core = candidate_words[candidate] - GENERIC_NAME_WORDS
            if best_score - score <= 0.025 and candidate_core == best_core:
                matches.append(candidate)
        for college in matches:
            placement_map[f"{prefix}|{college}"] = placement_report(entry)
        if not check_only:
            for row in rows:
                if row.get("college") in matches:
                    attach_placement(row, entry)

    if not check_only:
        return matched_count, placement_only
    return matched_count, placement_only


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path.home() / "Downloads",
        help="directory containing the three supplied college lists",
    )
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="report parsing and match coverage without changing JSON files",
    )
    args = parser.parse_args()

    sources = [
        ("Jee Colleges list.txt", "JEE", "josaa-cutoffs.json", "records", "JEE"),
        ("KCET Colleges list.txt", "KCET", "kcet-cutoffs.json", "kea", "KCET"),
        ("COMEDK Colleges list.txt", "COMEDK", "kcet-cutoffs.json", "comedk", "COMEDK"),
    ]
    parsed: dict[str, list[dict[str, Any]]] = {}
    data_files: dict[str, dict[str, Any]] = {}
    duplicates: dict[str, int] = {}
    for filename, exam, json_name, _, _ in sources:
        entries, duplicate_count = parse_source(args.source_dir / filename, exam)
        parsed[exam] = entries
        duplicates[exam] = duplicate_count
        data_files[json_name] = read_json(args.data_dir / json_name)
    if not args.check_only:
        for data in data_files.values():
            remove_legacy_fields(data)

    reports: dict[str, dict[str, Any]] = defaultdict(dict)
    placement_maps: dict[str, dict[str, Any]] = defaultdict(dict)
    placement_only_by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, exam, json_name, dataset_key, prefix in sources:
        data = data_files[json_name]
        count, placement_only = merge_group(
            data, dataset_key, parsed[exam], prefix, args.check_only
        )
        reports[exam] = {
            "parsed": len(parsed[exam]),
            "matched": count,
            "placementOnly": len(placement_only),
            "duplicatesSkipped": duplicates[exam],
        }
        placement_only_by_file[json_name].extend(placement_only)

        candidates = sorted({str(row["college"]) for row in data[dataset_key] if row.get("college")})
        candidate_words = {name: normalized_words(name) for name in candidates}
        for entry in parsed[exam]:
            matched, _ = match_college(entry["college"], candidates, candidate_words)
            if matched:
                placement_maps[json_name][f"{prefix}|{matched}"] = placement_report(entry)

    print(json.dumps(reports, ensure_ascii=False, indent=2))
    for json_name, entries in placement_only_by_file.items():
        if entries:
            print(f"\n{json_name}: unmatched placement-only entries")
            for entry in entries:
                candidates = ", ".join(
                    f"{item['college']} ({item['score']:.2f})"
                    for item in entry["matchCandidates"]
                )
                print(f"- {entry['exam']}: {entry['college']} -> {candidates or 'no candidates'}")

    if args.check_only:
        return 0

    for json_name, data in data_files.items():
        data["collegePlacements"] = placement_maps[json_name]
        data["placementOnly"] = placement_only_by_file[json_name]
        write_json(args.data_dir / json_name, data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
