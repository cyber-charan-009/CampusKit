#!/usr/bin/env python3
"""Build CampusKit's static predictor datasets from linked public sources.

Usage: python scripts/build_datasets.py

This is an offline build step only; GitHub Pages users consume the resulting
JSON and need no Python service. It deliberately never writes candidate names,
application numbers, roll numbers, or other candidate identifiers from MCC
allotment documents. The script records source URLs and ingestion diagnostics.
"""
from __future__ import annotations

import csv
import argparse
import io
import json
import re
import sys
from collections import defaultdict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pdfplumber
from pypdf import PdfReader
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
USER_AGENT = "CampusKit-DatasetBuilder/1.0 (static educational project)"
TIMEOUT = 90
JOSAA_CSV = "https://raw.githubusercontent.com/JIGGLEO/JOSAA-CUTOFF_DATASET/master/cutoffsfinal.csv"
JOSAA_OFFICIAL = "https://josaa.nic.in/or-cr/"
JOSAA_2026_PORTAL = "https://josaa.admissions.nic.in/Applicant/SeatAllotmentResult/currentorcr.aspx"
JOSAA_2026_PAGE = "https://josaa.nic.in/document/opening-and-closing-ranks-2026/"
JOSAA_2026_ROUND_CSV = "https://raw.githubusercontent.com/HarinManiK/cutoff_lens/main/data/jee_advanced_2026_round_{round}_IITs.csv"
KEA_2025_PORTAL = "https://cetonline.karnataka.gov.in/kea/ugcet2025"
KEA_2026_PORTAL = "https://cetonline.karnataka.gov.in/kea/ugcet2026"
COMEDK_2025_PORTAL = "https://www.comedk.org/counselling-document-2025"
COMEDK_2026_PORTAL = "https://www.comedk.org/counselling-document-2026"
AVANTI_KCET_DATA = "https://raw.githubusercontent.com/avantifellows/college-predictor/main/public/data/KCET/kcet_data.json"
MCC_2026_ROUND1_PAGE = "https://mcc.nic.in/document/final-allotment-result-for-round-1-of-ug-counselling-2026/"
MCC_2026_ROUND1_RESULT = "https://cdnbbsr.s3waas.gov.in/s3e0f7a4d0ef9b84b83b693bbf3feb8e6e/uploads/2026/08/20260824606525705.pdf"
AVANTI_NEET_DATA = "https://raw.githubusercontent.com/avantifellows/college-predictor/main/public/data/NEETUG/NEETUG.json"
NEET_NTA_RESULT = "https://cdnbbsr.s3waas.gov.in/s37bc1ec1d9c3426357e69acd5bf320061/uploads/2025/06/2025061472.pdf"
NEET_SCORE_ANALYSIS = "https://medicine.careers360.com/articles/neet-result-marks-vs-rank"
NEET_SCORE_ANALYSIS_SECONDARY = "https://resources-prod.aakash.ac.in/Aakash/s3fs-public/pdf_management_files/sm_sa/NEET%20Secrets%202026%20%281%29%20%281%29.pdf"
CG_STATE_ORCR_2025 = "https://cdnbbsr.s3waas.gov.in/s34b4edc2630fe75800ddc29a7b4070add/uploads/2025/11/202511062056440958.pdf"
NEXDOC_COLLEGE_METADATA = "https://raw.githubusercontent.com/deekshithvodela/nexdoc/main/public/data/colleges_details.json"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})
diagnostics: dict[str, Any] = {"generatedOn": date.today().isoformat(), "sources": {}, "warnings": []}


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.href: str | None = None
        self.text: list[str] = []
        self.items: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self.href = dict(attrs).get("href") or ""
            self.text = []

    def handle_data(self, data: str) -> None:
        if self.href is not None:
            self.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self.href is not None:
            self.items.append((" ".join(" ".join(self.text).split()), self.href))
            self.href = None
            self.text = []


def get(url: str, *, stream: bool = False) -> requests.Response:
    response = session.get(url, timeout=TIMEOUT, stream=stream)
    response.raise_for_status()
    return response


def html_links(url: str) -> list[tuple[str, str]]:
    parser = Links()
    parser.feed(get(url).text)
    return [(text, urljoin(url, href)) for text, href in parser.items]


def numeric(value: Any) -> float | None:
    if value is None:
        return None
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value).replace("\u00a0", " "))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def branch_name(value: str) -> str:
    s = value.lower()
    compact = re.sub(r"[^a-z]", "", s)
    if any(x in s for x in ("computer science", "computing", "computer eng")):
        return "CSE"
    if any(x in compact for x in ("informationtechnology", "informationscience", "informationengineering")):
        return "IT"
    if any(x in compact for x in ("artificialintelligence", "machinelearning", "datascience", "dataanalytics", "aiml")):
        return "AI/DS"
    if any(x in compact for x in ("electronicsandcommunication", "electronicscommunication", "electronicsandtelecommunication", "electronicstelecommunication", "communicationengineering")):
        return "ECE"
    if any(x in compact for x in ("electricalandelectronics", "electricalengineering")):
        return "EE"
    if "mechanical" in s:
        return "Mechanical"
    if "civil" in s:
        return "Civil"
    if "ise" in s:
        return "IT"
    if "aiml" in s or "ai & ml" in s or "ai and ml" in s:
        return "AI/DS"
    if "eee" in s:
        return "EE"
    if re.search(r"\b(ece|ec)\b", s):
        return "ECE"
    if re.search(r"\b(me|mec)\b", s):
        return "Mechanical"
    if re.search(r"\b(cv|ce)\b", s):
        return "Civil"
    return value.strip() or "Other"


def institute_type(name: str) -> str:
    s = name.lower()
    if "indian institute of technology" in s or re.search(r"\biit\b", s):
        return "IIT"
    if "national institute of technology" in s or re.search(r"\bnit\b", s):
        return "NIT"
    if "indian institute of information technology" in s or re.search(r"\biiit\b", s):
        return "IIIT"
    return "GFTI"


def normalize_kea_category(value: str) -> str:
    """Map KEA HK column suffixes to the equivalent category keys in the UI."""
    value = value.strip().upper()
    if value.endswith("H"):
        value = value[:-1]
        if value in {"1", "2A", "2B", "3A", "3B", "SC", "ST"}:
            return value + "G"
    return value


def write_json(name: str, obj: Any) -> None:
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")


def build_jee_cutoffs() -> dict[str, Any]:
    print("Downloading JoSAA historical CSV (76 MB source; parsing in-memory to handle gzip/content encoding reliably)…")
    response = get(JOSAA_CSV)
    official_status = get(JOSAA_OFFICIAL).status_code
    portal_status = get(JOSAA_2026_PORTAL).status_code
    reader = csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"), newline=""))
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    column_map: dict[str, str] = {}
    for raw in reader:
        if not column_map:
            column_map = {key.strip().lower(): key for key in raw}
        def col(label: str) -> str:
            return raw.get(column_map.get(label, ""), "") or ""
        year = int(numeric(col("year")) or 0)
        if year not in (2024, 2025):
            continue
        institute = col("institute").strip()
        program = col("academic program name").strip()
        category = col("seat type").strip().upper()
        gender = col("gender").strip()
        quota_raw = col("quota").strip().upper()
        opened_raw, closed_raw = col("opening rank").strip(), col("closing rank").strip()
        opened, closed = numeric(opened_raw), numeric(closed_raw)
        round_no = int(numeric(col("round")) or 0)
        if not institute or not program or closed is None or opened is None or not category:
            continue
        quota = quota_raw if quota_raw in {"AI", "HS", "OS"} else quota_raw
        key = (year, institute, program, quota, category, gender)
        old = by_key.get(key)
        if old is None or round_no >= old["round"]:
            by_key[key] = {
                "year": year, "round": round_no, "exam": "JEE Advanced" if institute_type(institute) == "IIT" else "JEE Main",
                "instituteType": institute_type(institute), "college": institute, "program": program,
                "branch": branch_name(program), "quota": quota, "category": category, "gender": gender,
                "openingRank": int(opened), "closingRank": int(closed),
                "openingRankLabel": opened_raw, "closingRankLabel": closed_raw,
                "isPreparatory": opened_raw.upper().endswith("P") or closed_raw.upper().endswith("P"),
                "annualFeeINR": None, "averagePackageLPA": None,
                "source": "JIGGLEO JoSAA Historical Cutoff Dataset; public JoSAA OR-CR source",
            }

    round_counts: dict[str, int] = {}
    round_errors: list[str] = []
    for round_no in range(1, 7):
        source_url = JOSAA_2026_ROUND_CSV.format(round=round_no)
        try:
            round_response = get(source_url)
        except requests.RequestException as exc:
            round_errors.append(f"R{round_no}: {exc}")
            continue
        csv_reader = csv.DictReader(io.StringIO(round_response.content.decode("utf-8-sig"), newline=""))
        parsed = 0
        for raw in csv_reader:
            institute = (raw.get("Institute") or "").strip()
            program = (raw.get("Academic Program Name") or "").strip()
            category = (raw.get("Seat Type") or "").strip().upper()
            gender = (raw.get("Gender") or "").strip()
            quota = (raw.get("Quota") or "").strip().upper()
            opening_raw = (raw.get("Opening Rank") or "").strip()
            closing_raw = (raw.get("Closing Rank") or "").strip()
            opening, closing = numeric(opening_raw), numeric(closing_raw)
            if not institute or not program or not category or opening is None or closing is None:
                continue
            key = (2026, institute, program, quota, category, gender)
            old = by_key.get(key)
            if old is None or round_no >= old["round"]:
                by_key[key] = {
                    "year": 2026, "round": round_no, "exam": "JEE Advanced",
                    "instituteType": institute_type(institute), "college": institute, "program": program,
                    "branch": branch_name(program), "quota": quota, "category": category, "gender": gender,
                    "openingRank": int(opening), "closingRank": int(closing),
                    "openingRankLabel": opening_raw, "closingRankLabel": closing_raw,
                    "isPreparatory": opening_raw.upper().endswith("P") or closing_raw.upper().endswith("P"),
                    "annualFeeINR": None, "averagePackageLPA": None, "source": source_url,
                }
            parsed += 1
        round_counts[str(round_no)] = parsed

    rows = list(by_key.values())
    if not any(x["year"] == 2025 for x in rows):
        raise RuntimeError("JoSAA CSV download succeeded but no valid 2025 cutoff rows parsed; preserving existing data.")
    latest_by_key: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for item in rows:
        key = (item["college"], item["program"], item["quota"], item["category"], item["gender"])
        current = latest_by_key.get(key)
        if current is None or item["year"] > current["year"]:
            latest_by_key[key] = item
    latest = list(latest_by_key.values())
    history_index = {
        (x["year"], x["college"], x["program"], x["quota"], x["category"], x["gender"]): x
        for x in rows
    }
    for item in latest:
        prev = history_index.get((item["year"] - 1, item["college"], item["program"], item["quota"], item["category"], item["gender"]))
        item["previousYear"] = item["year"] - 1 if prev else None
        item["previousYearClosingRank"] = prev["closingRank"] if prev else None
        item["cutoffTrend"] = ("rank-improved" if prev and item["closingRank"] < prev["closingRank"] else "rank-relaxed" if prev and item["closingRank"] > prev["closingRank"] else "unchanged" if prev else "new/no-2024-match")
    rows_by_year = {str(year): sum(row["year"] == year for row in rows) for year in (2024, 2025, 2026)}
    diagnostics["sources"]["josaa"] = {
        "csv": JOSAA_CSV, "official": JOSAA_OFFICIAL, "officialStatus": official_status,
        "official2026Page": JOSAA_2026_PAGE, "portal2026": JOSAA_2026_PORTAL, "portal2026Status": portal_status,
        "2026RoundCsvTemplate": JOSAA_2026_ROUND_CSV, "parsedRowsBy2026Round": round_counts,
        "roundSourceErrors": round_errors, "rowsByYear": rows_by_year, "servedRows": len(latest),
        "note": "The 2026 open-repository files cover IIT JEE Advanced rounds available in the repository; the official JoSAA portal is recorded for verification. Other institutes retain the latest available year-specific source row.",
    }
    return {
        "meta": {
            "dataset": "JoSAA OR-CR historical cutoffs", "updated": date.today().isoformat(),
            "years": sorted({row["year"] for row in latest}),
            "comparisonYears": [2024, 2025],
            "roundPolicy": "latest available round and year per institute/program/quota/category/gender; unavailable 2026 entries retain the latest older record",
            "rankBasis": "JoSAA published opening/closing rank; OPEN uses CRL, reserved seat types use their published category rank",
            "officialSource": JOSAA_OFFICIAL, "official2026Source": JOSAA_2026_PAGE,
            "contributorSource": JOSAA_CSV, "contributor2026Source": JOSAA_2026_ROUND_CSV,
            "dataNotice": "Cutoff year and round are retained per record. Fees and placements are null unless sourced from official institute reports; no values are invented.",
        },
        "records": sorted(latest, key=lambda x: (x["instituteType"], x["college"], x["program"], x["category"], x["quota"], x["gender"])),
    }


def parse_pdf(url: str, *, max_pages: int | None = None) -> list[tuple[int, str]]:
    response = get(url)
    reader = PdfReader(io.BytesIO(response.content))
    pages = reader.pages[:max_pages] if max_pages else reader.pages
    result = [(page_no, page.extract_text(extraction_mode="layout") or "") for page_no, page in enumerate(pages, 1)]
    if result and not any(text.strip() for _, text in result):
        # Fallback for text layers that pypdf cannot decode: pdfplumber table/text extraction.
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            fallback_pages = pdf.pages[:max_pages] if max_pages else pdf.pages
            result = []
            for page_no, page in enumerate(fallback_pages, 1):
                text = page.extract_text(layout=False) or ""
                if not text.strip():
                    tables = page.extract_tables() or []
                    text = "\n".join(" | ".join(str(cell or "") for cell in row) for table in tables for row in table)
                result.append((page_no, text))
    return result


def find_kea_pdfs(year: int = 2025) -> list[tuple[str, str]]:
    portal = KEA_2026_PORTAL if year == 2026 else KEA_2025_PORTAL
    links = html_links(portal)
    found = []
    date_pattern = re.compile(r"PROF_CODE_E_([RH])_(\d{2})(\d{2})(\d{4})", re.I)
    for label, href in links:
        match = date_pattern.search(href)
        if not match or ".pdf" not in href.lower() or "spl" in href.lower():
            continue
        if int(match.group(4)) != year:
            continue
        found.append((label, href, (int(match.group(4)), int(match.group(3)), int(match.group(2))), match.group(1).upper()))
    if found:
        latest_date = max(item[2] for item in found)
        selected = [item for item in found if item[2] == latest_date]
        selected.sort(key=lambda item: item[3])
        return [(label, href) for label, href, _, _ in selected]
    if year == 2026:
        return [
            ("KEA UGCET 2026 Round 3 Rest of Karnataka", "https://cetonline.karnataka.gov.in/keawebentry456/ugcet2026/PROF_CODE_E_R_04092026kannada.pdf"),
            ("KEA UGCET 2026 Round 3 Kalyana Karnataka", "https://cetonline.karnataka.gov.in/keawebentry456/ugcet2026/PROF_CODE_E_H_04092026kannada.pdf"),
        ]
    return [
        ("KEA UGCET 2025 Round 3 Rest of Karnataka", "https://cetonline.karnataka.gov.in/keawebentry456/ugcet2025/PROF_CODE_E_R_11092025kannada.pdf"),
        ("KEA UGCET 2025 Round 3 Kalyana Karnataka", "https://cetonline.karnataka.gov.in/keawebentry456/ugcet2025/PROF_CODE_E_H_11092025kannada.pdf"),
    ]


def parse_kea_page(text: str, page: int, quota: str, year: int = 2025) -> list[dict[str, Any]]:
    """Parse KEA's extracted PDF text using each page's printed course/category header."""
    categories: list[str] = []
    college_code = ""
    college_name = ""
    pending: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = []
    category_pattern = re.compile(r"^(?:GM|GMK|GMP|GMR|NRI|OPN|OTH|(?:1|2A|2B|3A|3B|SC|ST)[GKRH]|(?:1|2A|2B|3A|3B|SC|ST)[GKR]H|(?:GM|GMK|GMP|GMR|SC|ST)[H])$")
    def flush() -> None:
        nonlocal pending
        if not pending or not college_code or not categories:
            pending = None
            return
        course = re.sub(r"\s+", " ", " ".join(pending["parts"])).strip()
        for raw_cat, cell in zip(categories, pending["values"]):
            rank = numeric(cell)
            if rank is None:
                continue
            cat = normalize_kea_category(raw_cat)
            rows.append({"exam": "KCET", "year": year, "round": "Round 3", "collegeCode": college_code,
                         "college": college_name, "program": course, "branch": branch_name(course),
                         "category": cat, "sourceCategory": raw_cat, "quota": quota, "closingRank": rank, "openingRank": None,
                         "annualFeeINR": None, "averagePackageLPA": None, "source": "KEA UGCET 2025 official cutoff PDF"})
        pending = None

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        match = re.search(r"College:\s*([A-Z]\d{3})\s+(.+?)(?:\s+Course Name|$)", line, re.I)
        if match:
            flush()
            college_code, college_name = match.group(1).upper(), match.group(2).strip()
        if "Course Name" in line:
            flush()
            tail = line.split("Course Name", 1)[1]
            categories = [x for x in re.findall(r"\b[A-Z0-9]+\b", tail) if category_pattern.fullmatch(x)]
            continue
        cells = re.findall(r"--|\d[\d,]*(?:\.\d+)?", line)
        if categories and len(cells) == len(categories):
            flush()
            first = re.search(r"--|\d[\d,]*(?:\.\d+)?", line)
            prefix = line[:first.start()].strip() if first else ""
            pending = {"parts": [prefix] if prefix else [], "values": cells}
            continue
        if pending and not cells and not line.lower().startswith(("seat type:", "karnataka examinations", "non-interactive", "ugcet-", "generated on:", "page ")):
            if not re.match(r"^[\d.\- ]+$", line):
                pending["parts"].append(line)
    flush()
    return rows


def parse_kea_table_page(page: Any, quota: str, year: int, round_name: str, source_url: str) -> list[dict[str, Any]]:
    """Parse KEA's structured cutoff table while retaining the PDF's category columns."""
    text = page.extract_text() or ""
    college_match = re.search(r"College:\s*(E\d{3})\s+([^\r\n]+)", text, re.I)
    if not college_match:
        return []
    college_code = college_match.group(1).upper()
    college_name = college_match.group(2).strip()
    category_pattern = re.compile(r"^(?:GM|GMK|GMP|GMR|NRI|OPN|OTH|(?:1|2A|2B|3A|3B|SC|ST)[GKRH]|S[1-4][GKR]|(?:GM|GMK|GMP|GMR|SC|ST)[H])$", re.I)
    rows: list[dict[str, Any]] = []
    for table in page.extract_tables() or []:
        header_index = next(
            (i for i, row in enumerate(table) if row and "course name" in str(row[0] or "").lower()),
            None,
        )
        if header_index is None:
            continue
        header = table[header_index]
        categories = [(index, str(value or "").strip().upper()) for index, value in enumerate(header) if index and category_pattern.fullmatch(str(value or "").strip())]
        if not categories:
            continue
        for cells in table[header_index + 1:]:
            if not cells or not cells[0]:
                continue
            program = re.sub(r"\s+", " ", str(cells[0])).strip()
            if not program or program.lower() == "course name":
                continue
            for index, raw_category in categories:
                if index >= len(cells):
                    continue
                closing = numeric(cells[index])
                if closing is None or closing <= 0:
                    continue
                rows.append({
                    "exam": "KCET", "year": year, "round": round_name, "collegeCode": college_code,
                    "college": college_name, "program": program, "branch": branch_name(program),
                    "category": normalize_kea_category(raw_category), "sourceCategory": raw_category,
                    "quota": quota, "closingRank": closing, "openingRank": None,
                    "annualFeeINR": None, "averagePackageLPA": None, "source": source_url,
                })
    return rows


def find_comedk_pdf(year: int) -> str:
    portal = COMEDK_2026_PORTAL if year == 2026 else COMEDK_2025_PORTAL
    links = html_links(portal)
    wanted_round = "round 3"
    for label, href in links:
        value = re.sub(r"[^a-z0-9]+", " ", f"{label} {href}".lower())
        if "engineering" in value and "cut" in value and wanted_round in value and href.lower().endswith(".pdf"):
            return href
    if year == 2026:
        return "https://www.comedk.org/uploads/Engineering-Cut-off-Ranks-after-Round-3-Allotment%20Notified-on-18.08.2026.pdf"
    return "https://www.comedk.org/uploads/Engineering_Cut_Off_Ranks_after_Round_3_Allotment__Notified_on_22_08_2025.pdf"


def build_kcet() -> dict[str, Any]:
    all_kea_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    errors = []
    for year in (2025, 2026):
        for label, url in find_kea_pdfs(year):
            try:
                pdf_response = get(url)
                parsed = 0
                with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
                    for page in pdf.pages:
                        quota = "HK" if "_H_" in url else "Rest of Karnataka"
                        parsed_rows = parse_kea_table_page(page, quota, year, "Round 3", url)
                        all_kea_rows.extend(parsed_rows)
                        parsed += len(parsed_rows)
                        page.close()
                source_rows.append({"year": year, "url": url, "label": label, "parsedRows": parsed})
                if parsed == 0:
                    errors.append(f"KEA source {url}: no cutoff rows parsed")
            except Exception as exc:
                errors.append(f"KEA source {url}: {exc}")

    all_comedk_rows: list[dict[str, Any]] = []
    comedk_sources: list[dict[str, Any]] = []
    for year in (2025, 2026):
        comedk_pdf = find_comedk_pdf(year)
        round_name = "Round 3"
        comedk_rows: list[dict[str, Any]] = []
        try:
            pdf_response = get(comedk_pdf)
            with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
                for page_no, page in enumerate(pdf.pages, 1):
                    for table in page.extract_tables() or []:
                        if not table:
                            continue
                        header = [" ".join(str(c or "").split()) for c in table[0]]
                        if not any("college code" in x.lower() for x in header) or not any("seat category" in x.lower() for x in header):
                            continue
                        for cells in table[1:]:
                            if len(cells) < 4:
                                continue
                            code = str(cells[0] or "").strip().upper()
                            college = " ".join(str(cells[1] or "").split())
                            category = " ".join(str(cells[2] or "").split()).upper()
                            if not re.fullmatch(r"E\d{3}", code) or not college:
                                continue
                            for column, cell in enumerate(cells[3:], 3):
                                rank = numeric(cell)
                                if rank is None or column >= len(header):
                                    continue
                                program = header[column]
                                comedk_rows.append({
                                    "exam": "COMEDK", "year": year, "round": round_name,
                                    "collegeCode": code, "college": college, "program": program,
                                    "branch": branch_name(program), "category": category or "GM",
                                    "quota": f"COMEDK-{category or 'GM'}", "closingRank": rank,
                                    "openingRank": None, "annualFeeINR": None, "averagePackageLPA": None,
                                    "source": comedk_pdf, "sourcePage": page_no,
                                })
            comedk_sources.append({"year": year, "portal": COMEDK_2026_PORTAL if year == 2026 else COMEDK_2025_PORTAL, "pdf": comedk_pdf, "parsedRows": len(comedk_rows)})
        except Exception as exc:
            errors.append(f"COMEDK source {comedk_pdf}: {exc}")
        all_comedk_rows.extend(comedk_rows)

    open_source_kcet_rows = 0
    try:
        response = get(AVANTI_KCET_DATA)
        known_official_keys = {
            (row["year"], row["collegeCode"], re.sub(r"\s+", " ", row["program"]).casefold(), row["category"], row["quota"])
            for row in all_kea_rows
        }
        for raw in response.json():
            if str(raw.get("Year", "")) != "2025" or raw.get("Course Type") != "Engineering":
                continue
            institute = " ".join(str(raw.get("Institute") or "").split())
            code_match = re.match(r"^(E\d{3})\s+(.+)$", institute, re.I)
            program = " ".join(str(raw.get("Academic Program Name") or "").split())
            category_source = str(raw.get("Category_Key") or "").strip().upper()
            closing = numeric(raw.get("Closing Rank"))
            if not code_match or not program or not category_source or closing is None or closing <= 0:
                continue
            college_code, college = code_match.group(1).upper(), code_match.group(2).strip()
            quota = "HK" if raw.get("Pool") == "Kalyana-Karnataka" else "Rest of Karnataka"
            category = normalize_kea_category(category_source)
            source_key = (2025, college_code, re.sub(r"\s+", " ", program).casefold(), category, quota)
            if source_key in known_official_keys:
                continue
            all_kea_rows.append({
                "exam": "KCET", "year": 2025, "collegeCode": college_code, "college": college,
                "program": program, "branch": branch_name(program), "category": category,
                "sourceCategory": category_source, "quota": quota, "closingRank": closing,
                "openingRank": None, "annualFeeINR": None, "averagePackageLPA": None,
                "source": AVANTI_KCET_DATA,
            })
            open_source_kcet_rows += 1
            known_official_keys.add(source_key)
    except Exception as exc:
        errors.append(f"Avanti Fellows KCET 2025 source {AVANTI_KCET_DATA}: {exc}")

    def latest_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        best: dict[tuple[Any, ...], dict[str, Any]] = {}
        for item in items:
            key = (item["exam"], item["collegeCode"], item["program"], item["category"], item["quota"])
            old = best.get(key)
            if old is None or (item["year"], item["closingRank"]) > (old["year"], old["closingRank"]):
                best[key] = item
        return list(best.values())

    rows = latest_records(all_kea_rows)
    comedk_rows = latest_records(all_comedk_rows)
    if len(rows) < 100:
        diagnostics["warnings"].append(f"KEA parser produced {len(rows)} records (<100); output records are not padded with invented values.")
    if len(comedk_rows) < 100:
        diagnostics["warnings"].append(f"COMEDK parser produced {len(comedk_rows)} records (<100); output records are not padded with invented values.")
    diagnostics["sources"]["kcet"] = {
        "officialPortals": [KEA_2025_PORTAL, KEA_2026_PORTAL], "pdfs": source_rows,
        "openSource2025": AVANTI_KCET_DATA, "openSourceRows": open_source_kcet_rows,
        "parsedRecords": len(rows), "errors": errors,
    }
    diagnostics["sources"]["comedk"] = {"pdfs": comedk_sources, "parsedRecords": len(comedk_rows), "errors": errors}
    for record in comedk_rows:
        record.pop("sourcePage", None)
    years = sorted({row["year"] for row in rows + comedk_rows})
    return {
        "meta": {
            "dataset": "KEA KCET and COMEDK engineering cutoff references", "updated": date.today().isoformat(),
            "years": years, "officialKEA": KEA_2026_PORTAL, "officialCOMEDK": COMEDK_2026_PORTAL,
            "roundPolicy": "latest available year per college, program, quota, and category; KEA uses Round 3 of 2026 where published and 2025 fallback otherwise; COMEDK uses Round 3 in both 2025 and 2026",
            "notes": "Round-specific published last ranks. Fees are null unless explicitly extracted from an official fee table. Verify quota and column headers with the source PDF.",
        },
        "kea": rows, "comedk": comedk_rows,
    }


def normalize_neet_category(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip().upper()
    return {"OPEN": "UR", "GENERAL": "UR", "GEN": "UR", "GN": "UR", "EW": "EWS", "BC": "OBC", "OBC-NCL": "OBC"}.get(value, value)


def read_medical_college_metadata() -> tuple[dict[str, dict[str, Any]], str | None]:
    try:
        response = get(NEXDOC_COLLEGE_METADATA)
        raw = response.json()
        rows = raw.values() if isinstance(raw, dict) else raw
        index = {}
        ambiguous: set[str] = set()

        def add_name(name: Any, metadata: dict[str, Any]) -> None:
            key = re.sub(r"[^a-z0-9]", "", str(name).lower())
            if not key or key in ambiguous:
                return
            previous = index.get(key)
            if previous is not None and previous != metadata:
                index.pop(key)
                ambiguous.add(key)
            else:
                index[key] = metadata

        for item in rows:
            metadata = {"state": item.get("state"), "city": item.get("city"), "collegeType": item.get("college_type"), "collegeCode": item.get("college_code")}
            for name in [item.get("college_name", ""), *(item.get("aliases", []) or []), *(item.get("canonical_names", []) or [])]:
                add_name(name, metadata)
        return index, NEXDOC_COLLEGE_METADATA
    except Exception as exc:
        diagnostics["warnings"].append(f"NMC college metadata fallback not loaded: {exc}")
        return {}, None


def build_neet() -> dict[str, Any]:
    warnings: list[str] = []
    college_meta, metadata_source = read_medical_college_metadata()
    nta_result_bytes = len(get(NEET_NTA_RESULT).content)
    neet_analysis_status = get(NEET_SCORE_ANALYSIS).status_code
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    mcc_2026_rows = 0
    try:
        response = get(MCC_2026_ROUND1_RESULT)
        reader = PdfReader(io.BytesIO(response.content))
        row_pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(.*?)\s+(MBBS|BDS)\s+(Open|EWS|OBC|SC|ST)\s+(General|EWS|OBC|SC|ST|OBC-NCL)\s+(Allotted|Alloted)\s*$",
            re.I,
        )
        quota_prefixes = (
            "Employees State Insurance Scheme(ESI)", "Self-Financed Merit Seat",
            "Open Seat Quota", "Deemed/Paid Seats Quota", "Deemed University Quota",
            "Non-Resident Indian Quota", "Management Quota", "All India",
        )

        def split_quota_college(prefix: str) -> tuple[str, str]:
            prefix = re.sub(r"\s+", " ", prefix).strip()
            for label in quota_prefixes:
                if prefix.lower().startswith(label.lower() + " "):
                    return label, prefix[len(label):].strip()
            first, _, rest = prefix.partition(" ")
            return first, rest.strip()

        def add_mcc_row(line: str, page_no: int) -> None:
            nonlocal mcc_2026_rows
            match = row_pattern.match(line)
            if not match:
                return
            _, rank_raw, prefix, course, seat_category, candidate_category, status_text = match.groups()
            rank = int(rank_raw)
            seat_quota, college = split_quota_college(prefix)
            course = course.upper()
            if not college or rank <= 0:
                return
            category = normalize_neet_category(candidate_category)
            if category not in {"UR", "EWS", "OBC", "SC", "ST"}:
                category = normalize_neet_category(seat_category) if "open seat" in seat_quota.lower() else ""
            if category not in {"UR", "EWS", "OBC", "SC", "ST"}:
                return
            quota = "Deemed/Private" if any(k in seat_quota.lower() for k in ("deemed", "management", "nri", "paid", "self-financed")) else "AIQ/Central"
            key_name = re.sub(r"[^a-z0-9]", "", college.lower())
            meta = college_meta.get(key_name, {})
            ctype = "BDS" if course == "BDS" else ("Deemed/Private" if quota == "Deemed/Private" or meta.get("collegeType") == "Private" else "Govt MBBS")
            record_key = (2026, college, course, category, quota, seat_quota, "Round 1", "AIQ")
            item = grouped.setdefault(record_key, {
                "year": 2026, "college": college, "collegeCode": meta.get("collegeCode"),
                "state": meta.get("state"), "city": meta.get("city"), "course": course,
                "type": ctype, "quota": quota, "seatQuota": seat_quota, "category": category,
                "candidateCategory": normalize_neet_category(candidate_category) or None,
                "seatCategory": normalize_neet_category(seat_category) or None,
                "counsellingQuota": "AIQ", "round": "Round 1", "rankBasis": "NEET All India Rank",
                "openingRank": rank, "closingRank": rank, "allotmentStatus": status_text,
                "annualFeeINR": None, "source": MCC_2026_ROUND1_RESULT,
                "sourcePage": page_no, "allotmentCount": 0,
            })
            item["openingRank"] = min(item["openingRank"], rank)
            item["closingRank"] = max(item["closingRank"], rank)
            item["allotmentCount"] += 1
            mcc_2026_rows += 1

        for page_no, pdf_page in enumerate(reader.pages, 1):
            page_text = pdf_page.extract_text() or ""
            buffered = ""
            for line in page_text.splitlines():
                if re.match(r"^\s*\d+\s+\d+\s+", line):
                    if buffered:
                        add_mcc_row(buffered, page_no)
                    buffered = line.strip()
                elif buffered and line.strip():
                    buffered += " " + line.strip()
            if buffered:
                add_mcc_row(buffered, page_no)
    except Exception as exc:
        warnings.append(f"MCC 2026 Round 1 result extraction failed: {exc}")

    # State-quotas use their own merit lists; keep their state-rank basis distinct from AIR.
    state_url = CG_STATE_ORCR_2025
    try:
        response = get(state_url)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            for page_no, page in enumerate(pdf.pages, 1):
                page_tables = page.extract_tables() or []
                for table in page_tables:
                    if not table or not any("institute name" in str(c or "").lower() for c in table[0]):
                        continue
                    for cells in table[1:]:
                        if len(cells) < 10:
                            continue
                        college, course = " ".join(str(cells[0] or "").split()), " ".join(str(cells[1] or "").split()).upper()
                        quota_raw, category = " ".join(str(cells[2] or "").split()), normalize_neet_category(str(cells[3] or ""))
                        opening, closing = numeric(cells[8]), numeric(cells[9])
                        if not college or course not in {"MBBS", "BDS"} or opening is None or closing is None:
                            continue
                        key = (college, course, category, quota_raw, "Mop-up", "State")
                        grouped[key] = {"year": 2025, "college": college, "collegeCode": None, "state": "Chhattisgarh", "city": None,
                            "course": course, "type": "BDS" if course == "BDS" else ("Deemed/Private" if any(k in quota_raw.lower() for k in ("management", "nri")) else "Govt MBBS"),
                            "quota": "State Quota", "seatQuota": quota_raw, "category": category, "counsellingQuota": "State",
                            "round": "Mop-up", "rankBasis": "Chhattisgarh State Merit Rank", "openingRank": int(opening),
                            "closingRank": int(closing), "annualFeeINR": None, "source": state_url, "sourcePage": page_no, "allotmentCount": None}
                page.close()
    except Exception as exc:
        warnings.append(f"State OR-CR PDF fallback failed: {exc}")

    open_source_rows = 0
    try:
        response = get(AVANTI_NEET_DATA)
        open_rows = response.json()
        known_keys = {
            (re.sub(r"[^a-z0-9]", "", item["college"].lower()), item["course"], item["category"], item["quota"])
            for item in grouped.values() if item["year"] == 2025 and item["counsellingQuota"] == "AIQ"
        }
        for raw in open_rows:
            if not str(raw.get("Source", "")).startswith("aiq_2025") or raw.get("rank_space") != "NEET AIR":
                continue
            seat_quota = " ".join(str(raw.get("Seat Type") or "").split())
            quota = "Deemed/Private" if any(k in seat_quota.lower() for k in ("deemed", "management", "nri", "paid", "self-financed")) else "AIQ/Central"
            if seat_quota != "All India" and quota != "Deemed/Private":
                continue
            course = str(raw.get("Academic Program Name") or "").strip().upper()
            category_label = str(raw.get("Category") or "").strip()
            category = normalize_neet_category(category_label)
            rank = numeric(raw.get("Closing Rank"))
            college = " ".join(str(raw.get("Institute") or "").split())
            if course not in {"MBBS", "BDS"} or category not in {"UR", "EWS", "OBC", "SC", "ST"} or rank is None or not college:
                continue
            key = (re.sub(r"[^a-z0-9]", "", college.lower()), course, category, quota)
            if key in known_keys:
                continue
            meta = college_meta.get(key[0], {})
            ctype = "BDS" if course == "BDS" else ("Deemed/Private" if quota == "Deemed/Private" or raw.get("College Type") == "Private" else "Govt MBBS")
            item = {
                "year": 2025, "college": college, "collegeCode": meta.get("collegeCode"),
                "state": raw.get("State") or meta.get("state"), "city": meta.get("city"),
                "course": course, "type": ctype, "quota": quota, "seatQuota": seat_quota,
                "category": category, "candidateCategory": category, "seatCategory": category_label,
                "counsellingQuota": "AIQ", "round": str(raw.get("Round") or "Round 1"),
                "rankBasis": "NEET All India Rank", "openingRank": int(rank), "closingRank": int(rank),
                "annualFeeINR": None, "source": AVANTI_NEET_DATA, "allotmentCount": None,
            }
            grouped[(2025, college, course, category, quota, item["round"], "AIQ")] = item
            known_keys.add(key)
            open_source_rows += 1
    except Exception as exc:
        warnings.append(f"Avanti Fellows NEET 2025 source not loaded: {exc}")

    def round_order(value: str) -> int:
        match = re.search(r"round\s*(\d+)", value.lower())
        return int(match.group(1)) if match else (4 if "mop" in value.lower() else 0)

    latest: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for item in grouped.values():
        key = (
            re.sub(r"[^a-z0-9]", "", item["college"].lower()), item["course"],
            item["category"], item["quota"], item.get("seatQuota"), item["counsellingQuota"],
        )
        current = latest.get(key)
        if current is None or (item["year"], round_order(item["round"])) > (current["year"], round_order(current["round"])):
            latest[key] = item
    records = list(latest.values())
    for item in records:
        item.pop("sourcePage", None)
    if len(records) < 100:
        warnings.append(f"Only {len(records)} NEET cutoff groups parsed (<100); no synthetic college records were added.")
    diagnostics["sources"]["neet"] = {
        "mcc2026Round1Page": MCC_2026_ROUND1_PAGE, "mcc2026Round1Result": MCC_2026_ROUND1_RESULT,
        "mcc2026AllotmentRowsParsed": mcc_2026_rows, "openSource2025": AVANTI_NEET_DATA,
        "openSourceSupplementalRows": open_source_rows,
        "stateORCR": state_url, "stateCutoffGroups": sum(1 for x in records if x["counsellingQuota"] == "State"),
        "collegeMetadata": metadata_source, "ntaResultPdfDownloadedBytes": nta_result_bytes,
        "scoreAnalysisSource": NEET_SCORE_ANALYSIS, "scoreAnalysisStatus": neet_analysis_status,
        "warnings": warnings,
    }
    if not any(item["year"] == 2026 and item["counsellingQuota"] == "State" for item in records):
        diagnostics["warnings"].append("No machine-readable 2026 state-merit cutoff source was available from the linked KEA/GitHub sources; state-rank records remain separately year-labeled.")

    score_bands = [
        (678, 686, 1, 8), (650, 677, 9, 77), (630, 649, 78, 250), (609, 629, 251, 845),
        (601, 608, 846, 1302), (577, 600, 1303, 4000), (549, 576, 4001, 12860),
        (528, 548, 12861, 25541), (515, 527, 25542, 36843), (481, 514, 36844, 76510),
        (459, 480, 76511, 107944), (402, 458, 107945, 206050), (302, 401, 206051, 436777),
        (228, 301, 436778, 684232), (135, 227, 684233, 1152192),
    ]
    score_air = []
    for score in range(720, 139, -1):
        band = next((b for b in score_bands if b[0] <= score <= b[1]), None)
        if band:
            low_score, high_score, low_air, high_air = band
            fraction = 1 if high_score == low_score else (high_score - score) / (high_score - low_score)
            estimate = round(low_air + fraction * (high_air - low_air))
            score_air.append({"score": score, "airEstimate": estimate, "airLow": low_air, "airHigh": high_air, "marksBand": [low_score, high_score], "method": "interpolated estimate; full source band retained to show uncertainty"})
        else:
            score_air.append({"score": score, "airLow": None, "airHigh": None, "observedRange": None, "method": "outside published 2025 observed score bands"})
    return {"meta": {"dataset": "NEET UG cutoff ranks and score-to-AIR planning table", "updated": date.today().isoformat(),
        "years": sorted({item["year"] for item in records}),
        "officialMCC2026Source": MCC_2026_ROUND1_PAGE,
        "openSource2025": AVANTI_NEET_DATA, "ntaResult": NEET_NTA_RESULT, "stateORCRSource": state_url,
        "collegeMetadataSource": metadata_source, "scoreAnalysisSource": NEET_SCORE_ANALYSIS, "scoreAnalysisSecondarySource": NEET_SCORE_ANALYSIS_SECONDARY,
        "quotaNotes": "MCC Round 1 2026 and open-source 2025 AIQ ranks are NEET AIR. Chhattisgarh OR-CR ranks are state merit ranks and are explicitly labeled; they must not be compared with AIR. The linked open-source NEET cutoff file contains 2025 data; 2026 MCC records are official Round 1 allotments.",
        "scoreAirNotice": "NTA does not publish a complete marks-to-AIR lookup table. Integer scores are interpolated from published result-analysis score bands; this is a 2025 reference, not a 2026 prediction.",
        "privacy": "MCC candidate result rows are reduced to grouped institution/course/category rank intervals. No names, application numbers, or roll numbers are serialized."},
        "scoreAir": score_air, "records": records}


def build_jee_marks() -> dict[str, Any]:
    # NTA explains percentile normalization but does not release a definitive marks-to-percentile table.
    # 2025 observed 99-percentile anchors span about 148–203 by shift; values below interpolate a
    # published expert-analysis curve and remain explicitly estimates, never official NTA outcomes.
    anchors = {
        "tough": [(0, 0), (40, 55), (70, 70), (90, 80), (100, 85), (120, 90), (140, 96), (148, 99), (180, 99.7), (220, 99.95), (260, 99.99), (300, 100)],
        "moderate": [(0, 0), (40, 50), (70, 65), (90, 75), (110, 85), (130, 92), (155, 97), (175, 99), (200, 99.6), (240, 99.95), (270, 99.99), (300, 100)],
        "easy": [(0, 0), (40, 45), (70, 60), (90, 70), (120, 82), (145, 90), (165, 95), (185, 98), (203, 99), (230, 99.7), (265, 99.97), (300, 100)],
    }
    curves = {}
    pool = 1475103
    for difficulty, points in anchors.items():
        curve = []
        for marks in range(0, 301):
            for i in range(len(points) - 1):
                x0, y0 = points[i]; x1, y1 = points[i + 1]
                if x0 <= marks <= x1:
                    percentile = y0 + (marks - x0) * (y1 - y0) / (x1 - x0)
                    break
            else:
                percentile = 100
            curve.append({"marks": marks, "percentile": round(percentile, 5), "estimatedAIR": max(1, round(pool * (100 - percentile) / 100))})
        curves[difficulty] = curve
    payload = {"meta": {"dataset": "JEE Main 2025 marks-to-percentile planning curves", "updated": date.today().isoformat(), "source": "2025 shift-wise public post-exam analysis; NTA normalization definition", "notice": "NTA does not publish deterministic raw marks-to-percentile conversion tables. These difficulty curves are estimates. Estimated AIR assumes 1,475,103 unique candidates (2025 scale) and must be treated as a range, not a result."}, "candidatePool": pool, "categoryRankRatios": {"OPEN": 1.0, "EWS": 0.1, "OBC-NCL": 0.27, "SC": 0.15, "ST": 0.075}, "curves": curves}
    jee_reference = "https://www.jeeinfo.in/jee-main/marks-vs-percentile-2025/"
    diagnostics["sources"]["jeeMarks"] = {"reference": jee_reference, "nta": "https://jeemain.nta.nic.in/", "candidatePool": pool, "pointsPerCurve": 301, "note": "Interpolated expert-analysis anchors; not official NTA score mapping."}
    return payload


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    DATA.mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser(description="Download and compile CampusKit's static admissions datasets.")
    parser.add_argument("--only", help="Comma-separated subset: josaa,jee-marks,kcet,neet. Omit to rebuild every dataset.")
    args = parser.parse_args()
    selected = set(x.strip() for x in args.only.split(",")) if args.only else {"josaa", "jee-marks", "kcet", "neet"}
    unknown = selected - {"josaa", "jee-marks", "kcet", "neet"}
    if unknown:
        parser.error(f"unknown dataset key(s): {', '.join(sorted(unknown))}")
    if args.only:
        previous_path = DATA / "dataset-sources.json"
        if previous_path.exists():
            try:
                previous = json.loads(previous_path.read_text(encoding="utf-8"))
                diagnostics["sources"].update(previous.get("sources", {}))
            except Exception:
                pass
    outputs = []
    failed = False
    try:
      if "josaa" in selected:
        jee = build_jee_cutoffs()
        write_json("josaa-cutoffs.json", jee)
        outputs.append("josaa-cutoffs.json")
    except Exception as exc:
        failed = True
        diagnostics["warnings"].append(f"JoSAA build failed; existing output preserved: {exc}")
        print(f"WARNING: JoSAA ingestion failed: {exc}", file=sys.stderr)
    try:
      if "jee-marks" in selected:
        write_json("jee-marks-percentile.json", build_jee_marks())
        outputs.append("jee-marks-percentile.json")
    except Exception as exc:
        failed = True
        diagnostics["warnings"].append(f"JEE curve build failed: {exc}")
    try:
      if "kcet" in selected:
        write_json("kcet-cutoffs.json", build_kcet())
        outputs.append("kcet-cutoffs.json")
    except Exception as exc:
        failed = True
        diagnostics["warnings"].append(f"KCET/COMEDK build failed; existing output preserved: {exc}")
        print(f"WARNING: Karnataka/COMEDK ingestion failed: {exc}", file=sys.stderr)
    try:
      if "neet" in selected:
        write_json("neet-cutoffs.json", build_neet())
        outputs.append("neet-cutoffs.json")
    except Exception as exc:
        failed = True
        diagnostics["warnings"].append(f"NEET build failed; existing output preserved: {exc}")
        print(f"WARNING: NEET ingestion failed: {exc}", file=sys.stderr)
    write_json("dataset-sources.json", diagnostics)
    print("\nBuild summary:")
    for name in outputs:
        print(f"  OK {name}")
    for warning in diagnostics["warnings"]:
        print(f"  ! {warning}")
    return 0 if outputs and not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
