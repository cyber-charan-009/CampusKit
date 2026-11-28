#!/usr/bin/env python3
"""Merge a dental-college TXT/CSV into NEET data without modifying MBBS records.

Usage: python scripts/append_neet_bds_colleges.py --source "path/to/Neet missing bds.txt"

Uses the checked-in official directory snapshot for state/ownership metadata.
Its intake year is historical, not a 2027 seat matrix. User-supplied stopped or
unclear BDS intake entries remain in the roster but receive no admission rank.
All generated ranks are explicitly hypothetical planning scenarios.
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
from html.parser import HTMLParser
from pathlib import Path

from append_neet_private_colleges import (
    AIR, CATEGORIES, LABEL, ROOT, YEAR, clean_engineering_fields, fee_details,
    historical, identity, location, make_projections,
)
from rebuild_neet_clean import (
    STATE_ALIASES, bond_applies, clean_college_name, normalize, parse_detail,
    stipend_number,
)

REGISTRY_FILE = Path(__file__).with_name("neet_bds_registry.json")
REGISTRY_URL = "https://dciindia.gov.in/CollegeSearch.aspx?ColName=&CourseId=1&SplId=0&StateId="

# Reviewed name variants only. Never use unconstrained fuzzy matches to merge
# colleges: similarly named dental colleges in different cities are distinct.
REGISTRY_ALIASES = {
    "Nimra Institute of Dental Sciences, Vijayawada": "Nimra Institute of Dental Sciences",
    "Vaidik Dental College and Research Centre, Daman": "Vaidik Dental College and Research Centre,",
    "Sri Govind Tricentenary Dental College, Hospital & Research Institute, Gurgaon": "Sri Govind Tricentenary Dental College, Hospital & Research Institute",
    "Institute of Dental Sciences, Sehora, Jammu": "Institute of Dental Sciences, Sehora",
    "H.K.E. Society's, S. Nijalingappa Institute of Dental Sciences & Research, Kalaburagi": "H.K.E. Society's, S. Nijalingappa Institute of Dental Sciences & Research",
    "Al-Azhar Dental College, Thodupuzha, Kerala": "Al-Azhar Dental College, Kerala",
    "PMS College of Dental Science & Research, Thiruvananthapuram": "PMS College of Dental Science & Research, Thiruvananthpuram",
    "Royal Dental College, Palakkad, Kerala": "Royal Dental College, kerala",
    "Sree Anjaneya Institute of Dental Sciences (Medical Trust), Calicut": "Sree Anjaneya Medical Trust, Calicut",
    "Travancore Dental College, Kollam": "Travancore Dental College",
    "Maharana Pratap College of Dentistry, Gwalior": "Maharana Pratap College of Dentistry & Research Centre, Gwalior",
    "Mansarovar Dental College, Bhopal": "Mansarover Dental College, Bhopal",
    "Maharashtra Institute of Dental Sciences & Research (Dental College), Latur": "Maharashtra Institute of Dental Sciences & Research (Dental College)",
    "Pandit Dindayal Upadhyay Dental College, Solapur": "Pandit Deendayal Upadhyay Dental College, Solapur",
    "Gian Sagar Dental College & Hospital, Patiala": "Gian Sagar Dental College & Hospital",
    "Dr. S. S. Tantia Dental College Hospital and Research Centre, Sri Ganganagar": "Dr. S. S. Tantia Dental College Hospital and Research Centre",
    "Pacific Dental College & Research Centre, Udaipur": "Pacific Dental College & Research Centre",
    "Dhanalakshmi Srinivasan Dental College, Perambalur": "Dhanalakshmi Srinivasan Dental College",
    "Nandha Dental College and Hospital, Erode": "Nandha Dental College and Hospital",
    "Mamata Dental College, Khammam": "Mamata Dental College, Khamam",
    "Mamata Institute of Dental Sciences, Bachupally": "Mamata Institute of Dental Sciences",
    "Tirumala Institute of Dental Sciences & Research Centre, Nizamabad": "Tirumala Institute of Dental Sciences & Research Centre",
    "Dental College Azamgarh, Azamgarh": "Dental College Azamgarh",
    "I.T.S. Dental College, Hospital & Research Centre, Greater Noida": "I.T.S. Dental College, Hospital & Research Centre, Gr. Noida",
    "Gurunanak Institute of Dental Science & Research, Kolkata": "Gurunanak Institute of Dental Science & Research, Kolkatta",
    "Lady Hardinge Medical College & Smt. Sucheta Kriplani Hospital, Delhi": "Lady Hardinge Medical College & Smt. Sucheta Kriplani Hospital New Delhi",
    "Armed Forces Medical College, Pune, Maharashtra": "Armed Forces Medical College, Pune-1",
    "U.P. Rural Institute of Medical Sciences & Research (UPUMS), Saifai, Uttar Pradesh": "U.P. Rural Institute of Medical Sciences & Research, Saifai",
}
ALIAS_KEYS = {identity(name, "BDS"): identity(target, "BDS") for name, target in REGISTRY_ALIASES.items()}

# Historical directory plus explicit input state suffice for state assignment.
# Extra aliases provide a useful city even when the MBBS parser lacks the town.
CITY_HINTS = {
    "Andhra Pradesh": "Gannavaram Mandalam|Rajahmundry|Vishakhapatnam|Amalapuram|Duggirala|Bhimavaram",
    "Gujarat": "Amargadh|Visnagar",
    "Haryana": "Yamuna Nagar|Sirsa|Gurgaon|Panchkula",
    "Himachal Pradesh": "Nalagarh|Sunder Nagar|Poanta Sahib|Solan",
    "Jharkhand": "Hazaribag|Garhwa",
    "Karnataka": "Bijapur|Davangere|Virajpat|Humnabad|KGF|Sullia|Shimoga",
    "Kerala": "Thodupuzha|Kothamangalam|Tiruvalla",
    "Madhya Pradesh": "Burhanpur",
    "Maharashtra": "Ahmednagar|Amrutnagar|New Pargaon",
    "Puducherry": "Mahe",
    "Punjab": "Mandi Gobindgarh|Ferozepur|Sunam|Gulabgarh|Derabassi",
    "Rajasthan": "Kotputli",
    "Tamil Nadu": "Melmaruvathur|Kancheepuram|Komarapalayam|Tiruchengode|Kundrathur|Pandur|Sulur|Kavalkinaru Jn|Kulasekharam|Elayampalayam",
    "Telangana": "Bachupally",
    "Uttar Pradesh": "Safedabad|Modi Nagar|Modinagar|Masuri|Greater Noida",
    "West Bengal": "Banbishnupur",
}


class DirectoryParser(HTMLParser):
    """Keep the institution row and nested course rows separate."""
    def __init__(self):
        super().__init__()
        self.rows = []
        self.stack = []
        self.cells = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.stack.append([])
        elif tag in {"td", "th"} and self.stack:
            self.cells.append((self.stack[-1], []))

    def handle_data(self, text):
        for _, parts in self.cells:
            parts.append(text)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cells:
            row, parts = self.cells.pop()
            row.append(" ".join(" ".join(parts).split()))
        elif tag == "tr" and self.stack:
            row = self.stack.pop()
            if len(row) == 8 and row[0].isdigit():
                self.rows.append(row)


def snapshot_from_html(path: Path) -> dict:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    parser = DirectoryParser()
    parser.feed(text)
    session = re.search(r"Permitted Seats for Academic Year\s+(\d{4}-\d{2})", text)
    if not session or len(parser.rows) < 250:
        raise ValueError("Official directory layout/year was not recognized; existing snapshot not replaced")
    records = []
    for row in parser.rows:
        state = STATE_ALIASES.get(normalize(row[2]))
        if row[2] in {"Daman & Diu", "Daman and Diu"}:
            state = "Dadra and Nagar Haveli and Daman and Diu"
        if row[2] == "Uttrakhand":
            state = "Uttarakhand"
        if not state:
            raise ValueError(f"Unknown directory state {row[2]!r}")
        seats = re.search(r"\bBDS\s+N/A\s+(\d+)\b", row[5])
        records.append({"college": row[1], "state": state, "ownership": row[4],
                        "bdsSeats": int(seats[1]) if seats else None})
    return {"source": REGISTRY_URL, "retrieved": date.today().isoformat(),
            "intakeSession": session[1], "htmlSha256": hashlib.sha256(raw).hexdigest(),
            "status": "Historical state/ownership/intake metadata; not a 2027 seat matrix or a cutoff source",
            "records": records}


def registry_match(name: str, registry: dict) -> dict | None:
    key = identity(name, "BDS")
    return registry.get(ALIAS_KEYS.get(key, key))


def bds_location(name: str, entry: dict | None) -> tuple[str, str | None]:
    state, city = location(name)
    text = normalize(name)
    hints = [(len(normalize(town)), hint_state, town) for hint_state, towns in CITY_HINTS.items()
             for town in towns.split("|") if re.search(r"\b" + re.escape(normalize(town)) + r"\b", text)]
    if entry:
        state = entry["state"]
        hints = [hint for hint in hints if hint[1] == state]
    if hints:
        _, state, city = max(hints)
    if not state:
        raise ValueError(f"Could not resolve state for {name!r}")
    return state, city


def read_bds_source(path: Path, registry: dict) -> list[dict]:
    records = []
    for line, row in enumerate(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))), 1):
        if not row or not any(part.strip() for part in row):
            continue
        if len(row) >= 2 and normalize(row[0]) == "college" and normalize(row[1]) == "course":
            continue
        if len(row) < 5 or row[1].strip().upper() != "BDS":
            raise ValueError(f"Line {line}: expected a BDS row with five columns")
        if len(row) == 5:
            details = dict(zip(("internshipStipend", "annualFeeDisplay", "serviceBond"), row[2:]))
        elif row[-1].strip().upper() in {"N/A", "NA"}:
            # A known terminal N/A bond must not be confused with the fee N/A.
            fragments = row[2:-1]
            boundary = next((i for i, part in enumerate(fragments) if "/month" in part.lower()), None)
            if boundary is None:
                raise ValueError(f"Line {line}: stipend/fee boundary not found")
            details = {"internshipStipend": ",".join(fragments[:boundary + 1]),
                       "annualFeeDisplay": ",".join(fragments[boundary + 1:]), "serviceBond": row[-1]}
        else:
            details = parse_detail(row, line)
        entry = registry_match(row[0], registry)
        state, city = bds_location(row[0], entry)
        text = " ".join(details.values()).lower()
        status = ("admissions-stopped-in-supplied-list" if "admissions stopped" in text else
                  "bds-intake-unconfirmed" if "no ug bds" in text or "intake unstated" in text else
                  "historical-zero-bds-intake" if entry and entry["bdsSeats"] == 0 else "planning-roster")
        if entry and entry["bdsSeats"] is None:
            status = "bds-intake-unconfirmed"
        rec = {"college": clean_college_name(row[0]), "sourceName": row[0], "course": "BDS",
               "state": state, "city": city, **details,
               "collegeType": "Govt BDS" if entry and "govt" in entry["ownership"].lower() else "Deemed / Private",
               "admissionStatus": status, "admissionStatusSource": path.name,
               "admissionStatusNote": "Historical directory and user-supplied status; confirm 2027 permission and seat availability with the regulator and counselling authority."}
        if entry:
            rec.update(registryName=entry["college"], registrySource=REGISTRY_URL,
                       historicalBdsSeats=entry["bdsSeats"], ownership=entry["ownership"])
        records.append(rec)
    return records


def record_key(record: dict, registry: dict) -> tuple[str, str]:
    if record["course"] != "BDS":
        return identity(record["college"], record["course"])
    entry = registry_match(record.get("registryName") or record.get("sourceName") or record["college"], registry)
    if entry and record.get("state") and entry["state"] != record["state"]:
        raise ValueError(f"Conflicting states for {record['college']!r}")
    return identity(entry["college"] if entry else record["college"], "BDS")


def project_bds(record: dict) -> list[dict]:
    rows = make_projections(record)
    if record["admissionStatus"] != "planning-roster":
        record["eligibilityNote"] = "Excluded from admission results: supplied list reports stopped admissions or BDS intake is not confirmed. Verify the latest regulator permission."
        for row in rows:
            row.update(available=False, closingRank=None, model="unavailable",
                       availabilityNote=record["eligibilityNote"])
        return rows
    if "army college of dental" in normalize(record["college"]):
        record["eligibilityNote"] = "Army-ward eligibility and institute counselling conditions must be verified. This planning record does not imply unrestricted management admission."
    if "for women" in normalize(record["college"]):
        record["eligibilityNote"] += " This institution is listed for women; verify eligibility in its prospectus."
    # Separate, documented BDS scenarios; never reuse MBBS fee-tier anchors.
    multipliers = dict(zip(CATEGORIES, (1, 1.08, 1.20, 1.85, 2.10)))
    for row in rows:
        if row["model"] != "fee-tier-scenario":
            continue
        if row["quota"] == "AIQ":
            route_fee = row["annualFeeNumeric"]
            model_fee = route_fee if route_fee is not None else 400_000
            base = 350_000 + min(1, max(0, (model_fee - 100_000) / 700_000)) * 650_000
            factor = 1 if row["categoryBasis"].startswith("Open competition") else multipliers[row["category"]]
        else:
            base = {"Karnataka": 300_000, "Andhra Pradesh": 350_000, "Telangana": 350_000,
                    "Tamil Nadu": 280_000, "Maharashtra": 260_000}.get(record["state"], 320_000)
            factor = multipliers[row["category"]]
        row.update(closingRank=max(1, round(base * factor)), model="bds-fee-tier-scenario")
    return rows


def merge_bds(before: dict, incoming: list[dict], source: Path, snapshot: dict) -> tuple[dict, dict]:
    output = copy.deepcopy(before)
    registry = {identity(r["college"], "BDS"): r for r in snapshot["records"]}
    records = {}
    for rec in output["records"]:
        key = record_key(rec, registry)
        if key in records:
            raise ValueError(f"Existing canonical college/course duplicate: {rec['college']}")
        records[key] = rec
    added = matched = 0
    touched = set()
    for item in incoming:
        key = record_key(item, registry)
        if key in records:
            rec = records[key]
            if rec["state"] != item["state"]:
                raise ValueError(f"Conflicting states for duplicate {item['college']}")
            matched += 1
            rec.update({k: v for k, v in item.items() if k != "college"})
        else:
            rec = copy.deepcopy(item)
            records[key] = rec
            added += 1
        rec["historicalCutoffs"] = historical(rec)
        rec["aliases"] = sorted(set(rec.get("aliases", []) + [item["sourceName"]]))
        rec.update(fee_details(rec["annualFeeDisplay"]))
        rec["stipendNumeric"] = stipend_number(rec["internshipStipend"])
        rec["hasBond"] = None if rec["serviceBond"].strip().upper() in {"N/A", "NA"} else bond_applies(rec["serviceBond"])
        rec["detailsSource"] = source.name
        rec["detailsStatus"] = "User supplied; fees, stipend and bonds have not been independently verified"
        if "registryName" in rec:
            rec["historicalBdsSeatSession"] = snapshot["intakeSession"]
        rec["cutoffs"] = project_bds(rec)
        touched.add(key)
    output["records"] = sorted(records.values(), key=lambda r: (r["college"].casefold(), r["course"]))
    meta = output.setdefault("meta", {})
    report = {"sourceRows": len(incoming), "addedRecords": added, "matchedSourceRows": matched,
              "collegeCourseRecords": len(records),
              "mbbsRecords": sum(r["course"] == "MBBS" for r in records.values()),
              "bdsRecords": sum(r["course"] == "BDS" for r in records.values()),
              "importedEntriesExcludedFromPredictions": sum(records[k]["admissionStatus"] != "planning-roster" for k in touched),
              "officialDirectoryMatches": sum("registryName" in records[k] for k in touched)}
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    prior = meta.get("bdsCollegeImport", {})
    if prior.get("sha256") != digest:
        meta["bdsCollegeImport"] = {"file": source.name, "sha256": digest, **report}
    meta.update(updated=date.today().isoformat(), collegeCount=len(records),
                cutoffRowCount=sum(len(r.get("cutoffs", [])) for r in records.values()),
                recordsWithCutoffs=sum(any(c.get("available", True) for c in r.get("cutoffs", [])) for r in records.values()),
                historicalCutoffRowCount=sum(len(r.get("historicalCutoffs", [])) for r in records.values()))
    meta["bdsRegistry"] = {key: snapshot[key] for key in ("source", "retrieved", "intakeSession", "htmlSha256", "status")}
    meta.setdefault("projectionMethodology", {})["bds-fee-tier-scenario"] = (
        "Hypothetical, unvalidated BDS scenarios without college-specific historical AIR. "
        "Open fees 1L to 8L map linearly to 350000 to 1000000 AIR (unknown fee assumes 4L only for the rank scenario, not the budget filter). "
        "SQ UR anchors: Karnataka300000, AP/Telangana350000, TamilNadu280000, Maharashtra260000, other320000. "
        "Reserved-route category multipliers reuse the documented illustrative factors; no caste advantage is assumed for open management. "
        "These values are assumptions, not official cutoffs or a model fitted to the directory. "
        "The directory supplies historical state, ownership and intake metadata only; it does not establish 2027 admissions. "
        "Source-reported stopped admissions or unclear BDS intake have available=false and no projected rank."
    )
    return output, report


def validate_bds(before: dict, output: dict, incoming: list[dict], snapshot: dict) -> None:
    registry = {identity(r["college"], "BDS"): r for r in snapshot["records"]}
    assert [r for r in output["records"] if r["course"] == "MBBS"] == [r for r in before["records"] if r["course"] == "MBBS"], "MBBS records changed"
    assert output.get("scoreToRank") == before.get("scoreToRank"), "Score/AIR lookup changed"
    assert output.get("meta", {}).get("privateCollegeImport") == before.get("meta", {}).get("privateCollegeImport"), "MBBS import provenance changed"
    keys = [record_key(r, registry) for r in output["records"]]
    assert len(keys) == len(set(keys)), "Duplicate college/course"
    by_key = dict(zip(keys, output["records"]))
    for item in incoming:
        rec = by_key[record_key(item, registry)]
        for field in ("internshipStipend", "annualFeeDisplay", "serviceBond"):
            assert rec[field] == item[field], (item["college"], field)
        rows = rec["cutoffs"]
        assert len(rows) == len({(r["quota"], r["category"]) for r in rows}) == 10
        assert all(r["year"] == YEAR and r["yearLabel"] == LABEL and r["status"] == "projected" and r["rankBasis"] == AIR for r in rows)
        if rec["admissionStatus"] != "planning-roster":
            assert all(r["available"] is False and r["closingRank"] is None for r in rows)
        else:
            assert all(not r["available"] or isinstance(r["closingRank"], int) and r["closingRank"] > 0 for r in rows)
    assert clean_engineering_fields(output) == output, "Engineering package fields in NEET data"
    before_history = sum(len(r.get("historicalCutoffs", [])) for r in before["records"])
    assert sum(len(r.get("historicalCutoffs", [])) for r in output["records"]) >= before_history


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.home() / "Downloads" / "Neet missing bds.txt")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "neet-cutoffs.json")
    parser.add_argument("--registry", type=Path, default=REGISTRY_FILE)
    parser.add_argument("--registry-html", type=Path, help="Refresh the metadata snapshot from a downloaded official directory HTML page")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    snapshot = snapshot_from_html(args.registry_html) if args.registry_html else json.loads(args.registry.read_text(encoding="utf-8"))
    registry = {identity(r["college"], "BDS"): r for r in snapshot["records"]}
    incoming = read_bds_source(args.source, registry)
    before = json.loads(args.dataset.read_text(encoding="utf-8"))
    output, report = merge_bds(before, incoming, args.source, snapshot)
    validate_bds(before, output, incoming, snapshot)
    rerun, _ = merge_bds(output, incoming, args.source, snapshot)
    assert rerun == output, "BDS merge is not idempotent"
    if not args.dry_run:
        if args.registry_html:
            args.registry.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary = args.dataset.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.dataset)
    print(json.dumps({"dryRun": args.dry_run, **report,
                      "sourceStates": dict(Counter(r["state"] for r in incoming)),
                      "entryStatus": dict(Counter(r["admissionStatus"] for r in incoming))}, indent=2))


if __name__ == "__main__":
    main()
