#!/usr/bin/env python3
"""Merge the supplied medical CSV and build explicitly hypothetical 2027 scenarios.

Run: python scripts/append_neet_private_colleges.py --source "path/to/Neet missing mbbs.txt"

No network access or third-party packages are needed. Numeric historical evidence
is retained separately; assumptions are never presented as published 2027 ranks.
The input has unquoted commas in INR amounts, so use the roster's proven parser.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from rebuild_neet_clean import (
    CITY_ALIASES, CITY_STATE, STATE_ALIASES, bond_applies, clean_college_name,
    extract_state_city, latest_location_match, normalize, parse_detail, stipend_number,
)

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ("UR", "EWS", "OBC", "SC", "ST")
YEAR = 2027
LABEL = "2027 Projected Cutoff"
VERSION = "neet-planning-v2-exact-baselines"
AIR = "NEET All India Rank"
SOURCES = {
    "counselling": "https://mcc.nic.in/about-department/",
    "ntaRules": "https://nta.gov.in/cms/uploads/neet_Information_Bulletin_2026_6aee60b758.pdf",
    "afmc": "https://afmc.nic.in/MBBSAdmission",
    "cmc": "https://ext.cmcvellore.edu.in/wp-content/uploads/sites/14/2026/02/college-prospectus-23-02-2026.pdf",
    "stjohns": "https://www.stjohns.in/medicalcollege/announcements/mbbs-admissions-20262027-document-verification-notice",
    "vidisha": "https://gmcvidisha.org/",
}


def identity(name: str, course: str) -> tuple[str, str]:
    """Conservative normalization: preserve campus and city distinctions."""
    name = clean_college_name(name).replace("&", " and ")
    for old, new in CITY_ALIASES.items():
        name = re.sub(r"\b" + re.escape(old) + r"\b", new, name, flags=re.I)
    name = normalize(name)
    name = re.sub(r"\bst john s\b|\bst johns\b", "saint johns", name)
    name = re.sub(r"\bgovt\b", "government", name)
    # Official Vidisha institution also appears under its abbreviated name.
    if "vidisha" in name and "government medical college" in name:
        name = "atal bihari vajpayee government medical college vidisha"
    return name, course.strip().upper()


def location(name: str) -> tuple[str | None, str | None]:
    state, city = extract_state_city(name)
    # A city-like token elsewhere in the institute name must not override the
    # explicitly supplied trailing state (e.g. similarly named cities in two states).
    explicit = next((STATE_ALIASES[normalize(part)] for part in reversed(name.split(","))
                     if normalize(part) in STATE_ALIASES), None)
    if explicit:
        state = explicit
        lookup = {key: [pair for pair in pairs if pair[1] == state]
                  for key, pairs in CITY_STATE.items()}
        match = latest_location_match(normalize(name), {k: v for k, v in lookup.items() if v})
        city = match[1][0][0] if match else None
    return state, city


def money(segment: str) -> int | None:
    match = re.search(r"₹\s*([\d,]+(?:\.\d+)?)\s*(crores?|cr\b|lakhs?|lacs?|l\b|k\b)?", segment, re.I)
    if not match:
        return None
    amount = float(match[1].replace(",", ""))
    unit = (match[2] or "").lower()
    factor = 10_000_000 if unit.startswith("cr") else 100_000 if unit.startswith("l") else 1000 if unit == "k" else 1
    return round(amount * factor)


def fee_details(display: str) -> dict:
    """Choose a labeled public/state/Cat-A price, never an NRI price, first."""
    segments = [part.strip() for part in display.split("|")]
    state = [part for part in segments if re.search(r"govt|government|state|cat[\s-]*a\b", part, re.I)
             and not re.search(r"state\s*/\s*mgmt", part, re.I)]
    ordinary = [part for part in segments if not re.search(r"\bnri\b|\$", part, re.I)]
    primary = next((part for part in state + ordinary if money(part) is not None), "")
    management = [part for part in ordinary if re.search(r"mgmt|management|\bpvt\b|private|cat[\s-]*b\b|deemed|open", part, re.I)]
    return {
        "annualFeeNumeric": money(primary),
        "annualFeeBasis": primary or "Unknown; consult the college fee schedule",
        "stateFeeNumeric": next((money(part) for part in state if money(part) is not None), None),
        "managementFeeNumeric": next((money(part) for part in management if money(part) is not None), None),
    }


def read_source(path: Path) -> list[dict]:
    records = []
    for line, row in enumerate(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))), 1):
        if not row or not any(part.strip() for part in row):
            continue
        if normalize(row[0]) == "college" and normalize(row[1]) == "course":
            continue
        course = row[1].strip().upper()
        if course not in {"MBBS", "BDS"}:
            raise ValueError(f"Line {line}: unsupported course {course!r}")
        details = (dict(zip(("internshipStipend", "annualFeeDisplay", "serviceBond"), row[2:]))
                   if len(row) == 5 else parse_detail(row, line))
        state, city = location(row[0])
        if not state:
            raise ValueError(f"Line {line}: could not infer state for {row[0]!r}")
        records.append({"college": clean_college_name(row[0]), "sourceName": row[0],
                        "course": course, "state": state, "city": city, **details})
    return records


def historical(record: dict) -> list[dict]:
    rows = record.get("historicalCutoffs", []) + [row for row in record.get("cutoffs", [])
            if row.get("status") != "projected" and int(row.get("year", 0)) < YEAR]
    return list({json.dumps(row, sort_keys=True): copy.deepcopy(row) for row in rows}.values())


def special_kind(record: dict) -> str:
    name = normalize(record["college"])
    if "armed forces medical college" in name:
        return "afmc"
    if "christian medical college" in name and "vellore" in name:
        return "cmc"
    if "saint johns" in identity(record["college"], record["course"])[0]:
        return "stjohns"
    if "kempegowda institute" in name or "m s ramaiah" in name:
        return "premier-private"
    if "army college of medical sciences" in name:
        return "army"
    return ""


def clean_engineering_fields(value):
    if isinstance(value, dict):
        return {key: clean_engineering_fields(item) for key, item in value.items()
                if not re.search(r"package|lpa|placement|ctc", key, re.I)}
    if isinstance(value, list):
        return [clean_engineering_fields(item) for item in value]
    return value


def reference_for(record: dict, quota: str, category: str) -> dict | None:
    rows = [row for row in record["historicalCutoffs"]
            if ("SQ" if row.get("quota") in {"SQ", "State"} else row.get("quota")) == quota
            and row.get("category") == category and row.get("rankBasis") == AIR
            and isinstance(row.get("closingRank"), (int, float)) and row["closingRank"] > 0]
    # Preserve the roster's preferred seat pool, then most recent round/year.
    def order(row):
        seat = normalize(str(row.get("seatQuota", "")))
        priority = 0 if any(s in seat for s in ("all india", "govt quota", "open seat")) else 1
        if any(s in seat for s in ("nri", "foreign", "employees state insurance")):
            priority = 3
        rnd = str(row.get("round", "")).lower()
        roundnum = 100 if "stray" in rnd else 90 if "mop" in rnd else int(next(iter(re.findall(r"\d+", rnd)), "0"))
        return -int(row.get("year", 0)), priority, -roundnum, -row["closingRank"]
    return min(rows, key=order) if rows else None


def make_projections(record: dict) -> list[dict]:
    kind = special_kind(record)
    private = record.get("collegeType") == "Deemed / Private"
    central = record.get("collegeType") == "AIIMS / Central Govt"
    fee = record.get("annualFeeNumeric")
    private_fee = record.get("managementFeeNumeric")
    # An unlabeled single fee / 'All Quotas' fee can apply to open seats. An
    # explicitly state-only price cannot stand in for an unknown management fee.
    if private_fee is None and record.get("stateFeeNumeric") is None:
        private_fee = fee
    model_fee = private_fee if private_fee is not None else 1_500_000
    state_fee = record.get("stateFeeNumeric")
    aiq_government_pool = any(
        row.get("quota") == "AIQ" and any(term in normalize(str(row.get("seatQuota", "")))
                                         for term in ("all india", "govt quota", "government quota"))
        for row in record["historicalCutoffs"]
    )
    has_state_reference = any(r.get("quota") in {"State", "SQ"} for r in record["historicalCutoffs"])
    sq_available = (not central and kind != "afmc" and
                    (not private or state_fee is not None or has_state_reference or kind in {"cmc", "stjohns"}))
    # These are published assumptions, NOT fitted regression coefficients or real
    # seat matrices. Open/management scenarios never fabricate caste advantages.
    state_multiplier = {"UR": 1, "EWS": 1.08, "OBC": 1.20, "SC": 1.85, "ST": 2.10}
    if private:
        open_base = round(150_000 + min(1, max(0, (model_fee - 500_000) / 2_000_000)) * 500_000)
        sq_base = 90_000 if record["state"] == "Karnataka" else 100_000
        if record["state"] in {"Tamil Nadu", "Maharashtra"}:
            sq_base = 75_000
        if record["state"] in {"Andhra Pradesh", "Telangana"}:
            sq_base = 110_000
    else:
        open_base = 80_000 if record["course"] == "BDS" else 22_000
        sq_base = 120_000 if record["course"] == "BDS" else 40_000
    # Named-institute anchors are user-requested planning scenarios only.
    if kind in {"afmc", "cmc", "stjohns", "premier-private"}:
        open_base, sq_base = {"afmc": (10_000, 0), "cmc": (5_000, 12_000),
                              "stjohns": (18_000, 25_000), "premier-private": (40_000, 40_000)}[kind]
    notes = {
        "afmc": "AFMC screening, medical fitness and service conditions apply; NEET AIR alone does not determine selection. No general SQ route.",
        "cmc": "CMC has state and restricted management/minority routes, not a universal 85/15 split. Sponsorship, minority and service conditions apply.",
        "stjohns": "All admissions through KEA under institute-specific categories. Caste alone does not establish category eligibility; service conditions apply.",
        "army": "Army wards and college-specific eligibility conditions apply; this is not unrestricted management admission.",
    }
    record["eligibilityNote"] = notes.get(kind, "Check the current seat matrix, domicile, reservation/subcategory and counselling rules. A planning scenario does not establish eligibility.")
    record["eligibilitySource"] = SOURCES.get(kind, SOURCES["counselling"])
    result = []
    for quota in ("AIQ", "SQ"):
        for category in CATEGORIES:
            available = quota != "SQ" or sq_available
            open_competition = private and quota == "AIQ" and not aiq_government_pool or kind in {"afmc", "cmc", "stjohns", "army"}
            ref = reference_for(record, quota, category)
            inherited = False
            if not ref:
                ref = reference_for(record, quota, "UR")
                inherited = ref is not None and category != "UR"
            if quota == "AIQ" and kind == "afmc":
                label = "AFMC selection route (MCC registration)"
            elif quota == "AIQ":
                label = "Open / management (check counselling authority)" if private and not aiq_government_pool else "AIQ / central counselling"
            else:
                label = "SQ — state counselling"
            row = {"year": YEAR, "projectionYear": YEAR, "yearLabel": LABEL, "status": "projected", "quota": quota,
                   "quotaLabel": label, "category": category, "rankBasis": AIR,
                   "available": available,
                   "categoryBasis": "Open competition; no caste advantage assumed" if open_competition else "Category planning proxy; verify state subcategory and seat availability"}
            if not available:
                row.update(closingRank=None, model="unavailable", availabilityNote="No supported general state-quota route in the supplied evidence.")
            elif ref:
                factor = state_multiplier[category] if inherited and not open_competition else 1
                row.update(closingRank=max(1, round(ref["closingRank"] * factor)),
                           model="historical-category-proxy" if inherited else "historical-air-scenario",
                           sourceYear=ref["year"], historicalClosingRank=ref["closingRank"],
                           projectionMethod="category-proxy" if inherited else "unchanged-historical-baseline",
                           historicalReference={key: ref.get(key) for key in ("year", "openingRank", "closingRank", "category", "round", "rankBasis", "seatQuota", "source")})
            else:
                base = open_base if quota == "AIQ" else sq_base
                factor = 1 if open_competition else state_multiplier[category]
                row.update(closingRank=max(1, round(base * factor)), model="named-institute-scenario" if kind in {"afmc", "cmc", "stjohns", "premier-private"} else "fee-tier-scenario" if private else "public-college-scenario")
            # Route-specific prices prevent a low state fee qualifying a costly
            # management option under the maximum-fee filter.
            row["annualFeeNumeric"] = ((state_fee if state_fee is not None else fee) if quota == "SQ"
                                       else private_fee if private and not aiq_government_pool else fee)
            row["annualFeeBasis"] = "State / government-quota fee" if quota == "SQ" else "Open / management fee" if private and not aiq_government_pool else record.get("annualFeeBasis", "Annual tuition")
            result.append(row)
    return result


def merge_dataset(data: dict, incoming: list[dict], source: Path) -> tuple[dict, dict]:
    data = copy.deepcopy(data)
    imported_courses = {item["course"] for item in incoming}
    existing_count = len(data["records"])
    merged: dict[tuple[str, str], dict] = {}
    for original in data["records"]:
        rec = clean_engineering_fields(original)
        rec["historicalCutoffs"] = historical(rec)
        key = identity(rec["college"], rec["course"])
        if key in merged:
            combined = merged[key]["historicalCutoffs"] + rec["historicalCutoffs"]
            merged[key]["historicalCutoffs"] = list({json.dumps(r, sort_keys=True): r for r in combined}.values())
        else:
            merged[key] = rec
    added = matched = 0
    for item in incoming:
        key = identity(item["college"], item["course"])
        if key in merged:
            rec = merged[key]
            matched += 1
            # Preserve canonical roster name; retain the exact incoming name.
            rec.setdefault("aliases", [])
            rec["aliases"] = sorted(set(rec["aliases"] + [item["sourceName"]]))
            rec.update({k: v for k, v in item.items() if k != "college"})
        else:
            rec = {**item, "historicalCutoffs": []}
            merged[key] = rec
            added += 1
        name = normalize(rec["college"])
        rec["aliases"] = sorted(set(rec.get("aliases", []) + [item["sourceName"]]))
        rec["collegeType"] = "Govt MBBS" if special_kind(rec) == "afmc" or "government medical college" in name else "Deemed / Private"
        rec["detailsSource"] = source.name
        rec["detailsStatus"] = "User supplied; fees, stipend and bonds have not been independently verified"
    for rec in merged.values():
        # A later MBBS import must preserve BDS projections and intake holds.
        if rec["course"] not in imported_courses:
            continue
        if "gmers" in normalize(rec["college"]):
            rec["collegeType"] = "Deemed / Private"
            rec["collegeTypeNote"] = "Self-financed roster grouping requested by the site owner; this label does not assert deemed-university status. Historical AIQ seat pools retain their own category rules."
        rec.update(fee_details(rec.get("annualFeeDisplay", "")))
        rec["stipendNumeric"] = stipend_number(rec.get("internshipStipend", ""))
        rec["hasBond"] = bond_applies(rec.get("serviceBond", ""))
        rec["cutoffs"] = make_projections(rec)
    data["records"] = sorted(merged.values(), key=lambda r: (r["college"].casefold(), r["course"]))
    stats = {"sourceRows": len(incoming), "addedColleges": added, "matchedSourceRows": matched,
             "collegeCount": len(merged), "activeCutoffRows": sum(len(r["cutoffs"]) for r in merged.values()),
             "availableProjectedRows": sum(c["available"] for r in merged.values() for c in r["cutoffs"]),
             "historicalCutoffRows": sum(len(r["historicalCutoffs"]) for r in merged.values())}
    # Retain first-run import counts on rerun, while reporting current run below.
    previous_import = data.get("meta", {}).get("privateCollegeImport", {})
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    import_info = previous_import if previous_import.get("sha256") == digest else {
        "file": source.name, "sha256": digest, "sourceRows": len(incoming),
        "rosterBeforeImport": existing_count, "newColleges": added, "matchedSourceRows": matched,
    }
    data.setdefault("meta", {}).update({
        "dataset": "NEET UG college roster with hypothetical 2027 planning cutoffs",
        "updated": date.today().isoformat(), "projectionVersion": VERSION, "activeCutoffYear": YEAR,
        "cutoffLabel": LABEL, "collegeCount": len(merged), "cutoffRowCount": stats["activeCutoffRows"],
        "recordsWithCutoffs": sum(any(c["available"] for c in r["cutoffs"]) for r in merged.values()),
        "historicalCutoffRowCount": stats["historicalCutoffRows"], "privateCollegeImport": import_info,
        "cutoffStatus": "2027 Projected: hypothetical planning scenarios, NOT official cutoffs or a validated prediction. Historical ranks are preserved separately with their original year and rank basis.",
        "rosterStatus": "User supplied roster; financial and bond displays are preserved verbatim and unverified.",
        "projectionMethodology": {
            **data.get("meta", {}).get("projectionMethodology", {}),
            "historical-air-scenario": "Carry forward the exact latest matching historical college/course/quota/category AIR unchanged, preferring 2026 where available. No scaling or 4% tightening. The source year, rank, round and seat pool remain in historicalReference; 2027 is the projection/display year only.",
            "historical-category-proxy": "When a category has no AIR evidence, use the UR reference with illustrative category multipliers; category eligibility and actual reservation are unverified.",
            "fee-tier-scenario": "No college-specific historical AIR evidence. Open fee of 5L to 25L maps linearly to 150000 to 650000 AIR. SQ UR anchors: Karnataka90000, AP/Telangana110000, TN/Maharashtra75000, other100000. These are user-requested planning assumptions, not sourced cutoffs.",
            "named-institute-scenario": "Unvalidated AIR anchors: AFMC10000 (screening required), CMC5000 open/12000state, St Johns18000open/25000state, Kempegowda/MS Ramaiah40000. Never label these values official or calibrated.",
            "public-college-scenario": "No matching historical AIR: illustrative MBBS AIQ22000/SQ40000, BDS AIQ80000/SQ120000. Not a college-specific estimate.",
            "categories": "Illustrative factors UR1/EWS1.08/OBC1.20/SC1.85/ST2.10 only for reserved-route scenarios without exact evidence. Open/management and institute-specific scenarios use no caste advantage. National caste labels do not establish state-subcategory eligibility.",
            "quotas": "AIQ is a storage code for AIQ/central OR open/management/AFMC routes; quotaLabel distinguishes them. SQ is state counselling, not a universal85% share. Unsupported SQ has null rank and available=false, and is hidden in results.",
            "fees": "College annualFeeNumeric selects the primary Govt/State/Cat-A fee. Each cutoff row has the applicable state or management fee for budget filtering. Exact source display remains unchanged; a missing management fee is unknown, not the cheaper state fee.",
            "stateMerit": "Historical state merit ranks are never converted to AIR or used as AIR anchors.",
            "confidence": "No fitted probability model, 2027 seat matrix, validated college-specific fee-tier model or 2027 outcomes are available. Chance labels compare rank against the selected scenario only.",
        },
        "eligibilitySources": SOURCES,
    })
    return data, stats


def validate(data: dict, incoming: list[dict]) -> None:
    records = data["records"]
    keys = [identity(r["college"], r["course"]) for r in records]
    assert len(keys) == len(set(keys)), "Duplicate college/course"
    by_key = dict(zip(keys, records))
    for item in incoming:
        rec = by_key[identity(item["college"], item["course"])]
        for field in ("internshipStipend", "annualFeeDisplay", "serviceBond"):
            assert rec[field] == item[field], (item["college"], field)
    for record in records:
        rows = record["cutoffs"]
        assert len(rows) == 10
        assert len({(c["quota"], c["category"]) for c in rows}) == 10
        assert all(c["year"] == YEAR and c["status"] == "projected" and c["yearLabel"] == LABEL for c in rows)
        assert all(c["rankBasis"] == AIR and (not c["available"] or isinstance(c["closingRank"], int) and c["closingRank"] > 0) for c in rows)
    assert clean_engineering_fields(data) == data, "Engineering package field in NEET data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.home() / "Downloads" / "Neet missing mbbs.txt")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "neet-cutoffs.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    before = json.loads(args.dataset.read_text(encoding="utf-8"))
    incoming = read_source(args.source)
    output, report = merge_dataset(before, incoming, args.source)
    validate(output, incoming)
    assert output.get("scoreToRank") == before.get("scoreToRank"), "Score-to-AIR table changed"
    # Repeatability is checked in memory before touching the dataset.
    rerun, _ = merge_dataset(output, incoming, args.source)
    assert rerun == output, "Merge is not idempotent"
    if not args.dry_run:
        temporary = args.dataset.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.dataset)
    print(json.dumps({"dryRun": args.dry_run, **report, "models": dict(Counter(c["model"] for r in output["records"] for c in r["cutoffs"]))}, indent=2))


if __name__ == "__main__":
    main()
