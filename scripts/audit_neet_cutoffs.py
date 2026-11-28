#!/usr/bin/env python3
"""Preserve fetched NEET history and normalize one active 2027 row per key.

Reads the current roster and previously fetched aggregate data from Git HEAD
(or --historical-data). No college roster or fee/stipend/bond field is rebuilt.
Historical source years/ranks remain exact; 2027 is a display/projection year.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from append_neet_private_colleges import AIR, LABEL, ROOT, YEAR, identity, reference_for
from import_neet_college_details import TOKEN_ALIASES
from rebuild_neet_clean import CITY_ALIASES, normalize

QUOTA_PREFIX = re.compile(
    r"^(?:(?:university quota|country quota|puducherry ut domicile|self finance all india|"
    r"finance internal|women quota|minority quota|quota)\s+)+", re.I)
SYNONYMS = {**TOKEN_ALIASES, "sci": "science", "sciences": "science", "sce": "science",
            "institue": "institute", "institutes": "institute", "instt": "institute",
            "hos": "hospital", "hosp": "hospital", "hospt": "hospital", "hsopt": "hospital",
            "dent": "dental", "col": "college", "coll": "college", "collage": "college",
            "centre": "center", "res": "research", "gov": "government", "goverment": "government",
            "tamilnadu": "tamil nadu", "dentalcollege": "dental college", "den": "dental",
            "dc": "dental college", "gdc": "government dental college", "medial": "medical",
            "deogarh": "deoghar", "sonebhadra": "sonbhadra", "asifafabad": "asifabad",
            "kozikode": "kozhikode", "shahjhanpur": "shahjahanpur", "colleges": "college",
            "mc": "medical college", "univ": "university", "sc": "science"}
GENERIC = {"and", "of", "the", "dr", "shri", "sri", "smt", "late", "a", "an"}
DESCRIPTORS = {"hospital", "research", "center", "deemed", "university", "du", "general"}
INSTITUTION_WORDS = {"government", "medical", "dental", "college", "institute", "science", "state", "autonomous", "health", "school", "society", "memorial", "faculty"}
HISTORY_FIELDS = ("year", "quota", "category", "openingRank", "closingRank", "round", "rankBasis", "seatQuota", "source")
REVIEWED_ALIASES = {
    "MBBS": {
        "Amrita Institute of Medical Science, Kochi": "Amrita School of Medicine, Kochi",
        "Andaman and Nicobar Islands Institute of Medical S, Director ANIIMS": "Andaman & Nicobar Islands Institute of Medical Sciences, Port Blair",
        "B.L.D.E University, Bijapur": "B.L.D.E. Deemed University Shri B.M. Patil Medical College, Vijayapura",
        "BPS Govt. Med. College, Sonepat": "BPS Government Medical College for Women, Sonepat",
        "BV Deemed Uni. Med. College and Hos., Sangli": "Bharati Vidyapeeth Deemed University Medical College & Hospital, Sangli",
        "Bharati Vidyapeeth University Medical College, Pune": "Bharati Vidyapeeth DU Medical College, Dhankawadi, Pune",
        "Bharatratna Late shri Atal Bihari Vajpayee MGMC Rajnandgaon": "Bharatratna Late Shri Atal Bihari Vajpayee Memorial GMC, Rajnandgaon",
        "Chamrajanagar Institute of Medical Sciences, Karnataka": "Chamarajanagar Institute of Medical Sciences, Chamarajanagar",
        "DR. VAISHAMPAYAM MEMORIAL M.C., SHOLAPUR": "Dr. Vaishampayan Memorial Medical College, Solapur",
        "Dr. B.S.A. Medical College, Delhi": "Dr. Baba Saheb Ambedkar Medical College, Rohini",
        "Dr. DY Patil Medical College and Hospt., Pune": "Dr. D. Y. Patil Medical College, Hospital and Research Centre, Pimpri, Pune",
        "Dr. DYP Edu. Soc. Deemed Uni., Kolhapur": "Dr. D. Y. Patil Medical College, Kolhapur",
        "ESI-MC&PGIMS&R, Banglore": "ESIC Medical College, Rajajinagar, Bangalore",
        "ESIC Medical College, Hyderbad": "ESIC Medical College, Sanathnagar, Hyderabad",
        "ESIC PGIMSR, Joka": "ESIC Medical College, Joka, Kolkata",
        "GMC, Shahjhanpur": "Pt. Ram Prasad Bismil Autonomous State Medical College (GMC), Shahjahanpur",
        "GOVERNMENT MEDICAL COLLEGE, AMBIKAPUR": "Rajmata Shrimati Devendra Kumari Singhdeo GMC, Ambikapur",
        "GOVERNMENT MEDICAL COLLEGE, LATUR": "Vilasrao Deshmukh Government Medical College (GMC), Latur",
        "GURU GOVIND SINGH MED COLL, FARIDKOT": "Guru Gobind Singh Medical College & Hospital, Faridkot",
        "Guru Govind Singh Medical College, Faridkot": "Guru Gobind Singh Medical College & Hospital, Faridkot",
        "Government Medical College (Bharat Ratna Shri Atal Bihari Vajpyee Memorial Med. Col.), Rajnandgaon": "Bharatratna Late Shri Atal Bihari Vajpayee Memorial GMC, Rajnandgaon",
        "Government Medical College, Rajnandgaon": "Bharatratna Late Shri Atal Bihari Vajpayee Memorial GMC, Rajnandgaon",
        "Government Medical College, Chhindwara": "Chhindwara Institute of Medical Sciences, Chhindwara",
        "Government Medical College, Faizabad": "Rajarshi Dashrath Autonomous State Medical College (GMC), Ayodhya",
        "Govt Medical College Faizabad": "Rajarshi Dashrath Autonomous State Medical College (GMC), Ayodhya",
        "Government Medical College, Morbi": "GMERS Medical College, Morbi",
        "Government Medical College, Porbandar": "GMERS Medical College, Porbandar",
        "Government Medical College, ESIC, Coimbatore": "Government Medical College & ESIC Hospital, Coimbatore",
        "Hazaribagh Medical College, Hazaribagh": "Sheikh Bhikhari Medical College (Hazaribagh Medical College), Hazaribagh",
        "Jawaharlal Nehru Medical College, Aligarh": "Jawaharlal Nehru Medical College, Aligarh Muslim University (AMU), Aligarh",
        "Jawaharlal Nehru Medical College, AMU": "Jawaharlal Nehru Medical College, Aligarh Muslim University (AMU), Aligarh",
        "K A P Viswanathan Government Medical College, Trichy": "K.A.P. Viswanatham Government Medical College, Tiruchirappalli",
        "KGMC, LUCKNOW": "King George's Medical University (KGMU), Lucknow",
        "M G M Medical College, Indore": "Mahatma Gandhi Memorial (MGM) Medical College, Indore",
        "M.G.M. MEDICAL COLLEGE, INDORE": "Mahatma Gandhi Memorial (MGM) Medical College, Indore",
        "M G M Medical College, Jamshedpur": "Mahatma Gandhi Memorial (MGM) Medical College, Jamshedpur",
        "M.G.M. MEDICAL COLLEGE, JAMSHEDPUR": "Mahatma Gandhi Memorial (MGM) Medical College, Jamshedpur",
        "MKCG Medical College, Berhampur": "Maharaja Krishna Chandra Gajapati (MKCG) Medical College, Brahmapur",
        "MAHARAJA K.C. GAJAPATI M.C., BRAHMAPUR": "Maharaja Krishna Chandra Gajapati (MKCG) Medical College, Brahmapur",
        "NDMC Medical College, Delhi": "North Delhi Municipal Corporation (NDMC) Medical College",
        "North Eastern Indira Gandhi Regional Instt. of Health and Medical Sciences, Shillong": "NEIGRIHMS, Shillong",
        "Palamu Medical College, Palamu": "Medinirai Medical College (Palamu Medical College), Palamu",
        "Rajashree Chatrapati Shahu Maharaj Government Medical College, Kolhapur": "Rajarshi Chhatrapati Shahu Maharaj Government Medical College, Kolhapur",
        "Rajarshee Chhatrapati Shahu Maharaj Government Medical College Kolhapur": "Rajarshi Chhatrapati Shahu Maharaj Government Medical College, Kolhapur",
        "Rajiv Gandhi Medical College and Chhatrapati Shivaji Maharaj Hospital, Thane": "Rajiv Gandhi Medical College and CSM Hospital, Thane",
        "Shri B M Patil Medical College, Hospital & Research Centre, Vijayapura (Bijapur": "B.L.D.E. Deemed University Shri B.M. Patil Medical College, Vijayapura",
        "Shrimati Indira Gandhi Memorial Govt. Medical College, Kanker": "Government Medical College, Kanker",
        "Thoothukudi Medical College, Thoothukudi": "Thoothukudi Government Medical College, Thoothukudi",
        "Tinsukia Medical College - Assam Pin - 786146": "Tinsukia Medical College & Hospital, Tinsukia",
        "VARDHMAN INSTITUTE OF MEDICAL SCIENCES, NALANDA": "Bhagwan Mahavir Institute of Medical Sciences (BMIMS), Pawapuri, Nalanda",
        "Vijaynagar Institute of Medical Sciences, Bellary": "Vijayanagara Institute of Medical Sciences (VIMS), Ballari",
        "VIJAYNAGAR INST OF MED. SC, BELLARY": "Vijayanagara Institute of Medical Sciences (VIMS), Ballari",
        "Government Medical College & Hospital (Renamed as Bhima Bhoi Medical College & Hospital), Balangir": "Bhima Bhoi Medical College and Hospital, Balangir",
        "Government Medical College (Institute of Integrated Medical Sciences), Yakkara, Palakkad": "Government Medical College, Palakkad",
        "Padmashree Dr. DY. Patil Medical College, Navi Mumbai": "Dr. DY Patil Medical College, Navi Mumbai",
        "Rajmata Shrimata Devendra Kumari Singhdeo Government Medical College, Ambikapur (Surguja)": "Rajmata Shrimati Devendra Kumari Singhdeo GMC, Ambikapur",
        "GOVT. MEDICAL COLLEGE, TIRUNELVELI": "Tirunelveli Medical College (TVMC), Tirunelveli",
        "GTMC, THIRUVARUR": "Government Thiruvarur Medical College (GTMC), Thiruvarur",
        "GUWAHATI MEDICAL COLLEGE, GUWAHATI": "Gauhati Medical College, Guwahati",
        "GVMC, VILLUPURAM": "Government Villupuram Medical College, Villupuram",
        "Government Medical College, Mahabubangar": "Government Medical College, Mahabubnagar",
        "Govt Medical College Ratlam, Gram Banjali": "Dr. Laxminarayan Pandey Govt. Medical College, Ratlam",
        "Govt. Sivgangai M. C. Sivagangai": "Government Sivagangai Medical College, Sivaganga",
        "Hinduhridayasamrat Balasaheb Thackeray Medical College and Dr. R. N. Cooper Municipal General Hospital, Maharashtra": "H.B.T. Medical College & Dr. R.N. Cooper Municipal General Hospital, Mumbai",
        "INST OF PG MED EDU & RESEARCH, KOLKATA": "Institute of Post Graduate Medical Education & Research (IPGMER), Kolkata",
        "JLN IMS, IMPHAL": "Jawaharlal Nehru Institute of Medical Sciences (JNIMS), Imphal",
        "KARNATAK INST. OF MEDICAL SC., HUBLI": "Karnataka Medical College & Research Institute (KIMS), Hubballi",
        "LOKMANYA TILAK MUNICIPAL M C, MUMBAI": "Lokmanya Tilak Municipal Medical College (LTMMC), Sion, Mumbai",
        "Lt. B R K Government Medical College, Jagdalpur": "Late Shri Baliram Kashyap Memorial NDMC Govt. Medical College, Jagdalpur",
        "Lt. L A M Govt. Medical College, Raigarh": "Late Shri Lakhi Ram Agrawal Memorial Govt. Medical College, Raigarh",
        "MEDICAL COLLEGE, BHAVNAGAR": "Government Medical College, Bhavnagar",
        "MGM Medical College, Aurangabad": "Mahatma Gandhi Mission's Medical College, Aurangabad",
        "MM Inst. Med. and Research, Mullana": "Maharishi Markandeshwar Institute of Medical Sciences & Research, Mullana",
        "MRA MEDICAL COLLEGE AMBEDKAR NAGAR, UP": "Mahamaya Rajkiya Allopathic Medical College, Ambedkarnagar",
        "MYSORE MED.& RESEARCH INST. MYSORE": "Mysore Medical College and Research Institute (MMCRI), Mysore",
        "Maharaja Jitendra Narayan Medical College and Hospital Coochbehar, Vivekananda Street": "Coochbehar Government Medical College & Hospital, Coochbehar",
        "Mursidabad M C & Hospital, Mursidabad": "Murshidabad Medical College & Hospitals, Berhampore",
        "Pt. D.D.U MEDICAL COLLEGE, RAJKOT": "Pandit Deendayal Upadhyay (PDU) Medical College, Rajkot",
        "RAJIV GANDHI MEDICAL COLLEGE, THANE": "Rajiv Gandhi Medical College and CSM Hospital, Thane",
        "RIMS Srikakulam, Balaga Srikakulam": "Government Medical College (Previously RIMS), Srikakulam",
        "RIMS, Ongole": "Government Medical College, Ongole",
        "S.S. MEDICAL COLLEGE, REWA": "Shyam Shah (S.S.) Medical College, Rewa",
        "SHKM GMC, Nalhar": "Shaheed Hasan Khan Mewati Government Medical College, Nalhar, Nuh",
        "SJP Medical College, Bharatpur": "Shri Jagannath Pahadia Government Medical College, Bharatpur",
        "SLBS Govt. Medical College, Mandi": "Shri Lal Bahadur Shastri Government Medical College, Mandi",
        "SRI LALITHAMBIGAI MEDICAL COLLEGE & HOSPITAL": "Faculty of Medicine, Sri Lalithambigai Medical College and Hospital, Chennai",
        "SUH Maulana Mahmood Hasan Medical College, Saharanpur": "Shaikh-Ul-Hind Maulana Mahmood Hasan Medical College, Saharanpur",
        "SWAMI RAMANAND TiRTH RURAL M.C, AMBAJOGAI": "Swami Ramanand Teerth Rural (SRTR) Government Medical College, Ambajogai",
        "Shri Shankaracharya IMS Bhilai": "Shri Shankaracharya Institute of Medical Sciences, Bhilai",
        "Siddartha Medical College, Vijayawada": "Siddhartha Medical College, Vijayawada",
        "Sri Lakshmi Narayana Inst. of Med. Scien., Puducherry": "Sri Lakshmi Narayana Institute of Medical Sciences",
        "Sri Siddhartha Academy T Begur": "Sri Siddhartha Institute of Medical Sciences & Research Centre, T. Begur",
        "UTTARANCHAL F HOSP TRUST MC, HALDWANI": "Government Medical College, Haldwani",
        "V.S.S. MEDICAL COLLEGE, BURLA": "Veer Surendra Sai Institute of Medical Sciences and Research (VIMSAR), Burla",
        "VMKV Medical College and Hospital, Salem": "Vinayaka Mission's Kirupananda Variyar Medical College, Salem",
        "DR.S.C.GOVT MEDICAL COLLEGE": "Dr. Shankarrao Chavan Govt. Medical College, Nanded",
        "GOVERNMENT MEDICAL COLLEGE AND HOSPITAL, CHANDIGAR": "Government Medical College and Hospital (GMCH)",
        "NILRATAN SIRKAR MEDICAL COLLEGE, KOLKATA": "Nilratan Sircar (NRS) Medical College, Kolkata",
        "Sagar Dutta Medical College & Hospital, Kolkata": "College of Medicine and Sagore Dutta Hospital, Kolkata",
        "Thiruvannamalai MC, Thiruvannamalai": "Government Tiruvannamalai Medical College, Tiruvannamalai",
    },
    "BDS": {
        "Dr. Ziauddin Ahmed Dental College and Hospital, ALIGARH": "Dr. Ziauddin Ahmad Dental College and Hospital, AMU, Aligarh",
        "FACULTY OF DEN SCI, KG MED UNIV": "Faculty of Dental Sciences, KGMU, Lucknow",
        "GDC,PT.BDS UNIV.OF HEALTH SCI,ROHTAK": "Postgraduate Institute of Dental Sciences (GDC), Rohtak",
        "GOVT. D.C. & RESEARCH INST,BANGALORE": "Government Dental College & Research Institute (GDCRI), Bangalore",
        "IMS BHU Dental, Varanasi": "Faculty of Dental Sciences, IMS BHU, Varanasi",
        "K M Shah Dental Collegel": "K.M. Shah Dental College & Hospital, Vadodara",
        "M.G.D.C. & HOSPITAL, PUDUCHERRY": "Mahatma Gandhi Postgraduate Institute of Dental Sciences",
        "PB. GOVT. DENTAL COLLEGE & HOSP,AMRITSAR": "Punjab Government Dental College & Hospital, Amritsar",
        "Sri Ramachandra Dental and Hospt., Chennai": "Sri Ramachandra Dental College and Hospital, Chennai",
        "TAMILNADU GOVT D.C. & HOSP, CHENNAI": "Tamil Nadu Government Dental College & Hospital, Chennai",
        "VMS Dental College, Salem": "Vinayaka Mission's Sankarachariyar Dental College, Salem",
    },
}


def quota(value):
    return "SQ" if value in {"State", "SQ", "State Quota"} else "AIQ" if value in {"AIQ", "AIQ/Central", "Deemed/Private"} else value


def name_form(name):
    text = str(name).replace("&", " and ")
    text = re.sub(r"(?<![a-zA-Z])(?:[a-zA-Z]\.\s*){2,}", lambda m: re.sub(r"[^a-zA-Z]", "", m[0]) + " ", text)
    for old, new in CITY_ALIASES.items():
        text = re.sub(r"\b" + re.escape(old) + r"\b", new, text, flags=re.I)
    text = QUOTA_PREFIX.sub("", normalize(text))
    text = re.sub(r"^muslim university amu quota\s+", "", text)
    text = text.replace("all india institute of medical sciences", "aiims")
    text = re.sub(r"employees? state insurance (?:corporation|coporation)", "esic", text)
    text = text.replace("rai bareli", "raebareli")
    words = []
    for word in text.split():
        words.extend(SYNONYMS.get(word, word).split())
    return " ".join(word for word in words if word not in GENERIC | DESCRIPTORS)


def name_forms(name):
    parts = str(name).split(",")
    forms = {name_form(name), name_form(re.sub(r"\([^)]*\)", " ", name))}
    # Institution names followed by a city/address are common in MCC exports.
    # Short generic prefixes cannot select a college; ambiguity is retained.
    for length in (1, 2, 3):
        form = name_form(",".join(parts[:length]))
        if len(form.replace(" ", "")) >= 8:
            forms.add(form)
    return forms - {""}


def history_signature(course, row):
    return (course, row.get("year"), quota(row.get("quota") or row.get("counsellingQuota")),
            *(row.get(key) for key in HISTORY_FIELDS[2:]))


def source_rows(data):
    result = copy.deepcopy(data.get("unmatchedHistoricalCutoffs", []))
    for record in data.get("records", []):
        if "cutoffs" in record:
            rows = record.get("historicalCutoffs", []) + [c for c in record["cutoffs"]
                    if c.get("status") != "projected" and int(c.get("year", 0)) <= 2026]
            for row in rows:
                result.append({**row, "college": record["college"], "course": record["course"]})
        elif record.get("year", 0) <= 2026:
            result.append(record)
    return result


def build_matches(records, fetched):
    signatures = defaultdict(set)
    alias_sets = [set([r["college"], r.get("sourceName", ""), r.get("registryName", ""), *r.get("aliases", [])]) - {""} for r in records]
    roster = {(r["course"], r["college"]): i for i, r in enumerate(records)}
    for course, aliases in REVIEWED_ALIASES.items():
        for alias, target in aliases.items():
            owner = roster[(course, target)]
            alias_sets[owner].add(alias)
    for index, record in enumerate(records):
        for row in record.get("historicalCutoffs", []):
            signatures[history_signature(record["course"], row)].add(index)
    seeds = defaultdict(set)
    for row in fetched:
        candidates = signatures.get(history_signature(row["course"], row), set())
        if len(candidates) == 1:
            seeds[(row["college"], row["course"])].update(candidates)
    for (name, _), owners in seeds.items():
        if len(owners) != 1:
            raise ValueError(f"Conflicting historical source ownership for {name}")
        alias_sets[next(iter(owners))].add(name)
    groups = defaultdict(list)
    for row in fetched:
        groups[(row["college"], row["course"])].append(row)
    matches = {key: next(iter(owners)) for key, owners in seeds.items()}
    while True:
        index, token_index = defaultdict(set), defaultdict(set)
        for owner, aliases in enumerate(alias_sets):
            for alias in aliases:
                for form in name_forms(alias):
                    index[(records[owner]["course"], form.replace(" ", ""))].add(owner)
                    words = frozenset(form.split())
                    if len(words) >= 4 and words - INSTITUTION_WORDS:
                        token_index[(records[owner]["course"], words)].add(owner)
        added, unresolved = 0, []
        for key, rows in sorted(groups.items()):
            if key in matches:
                continue
            name, course = key
            candidates = set()
            source_states = {normalize(r["state"]) for r in rows if r.get("state")}
            # Longer exact normalized forms take precedence over shorter prefixes.
            for form in sorted(name_forms(name), key=len, reverse=True):
                owners = index.get((course, form.replace(" ", "")), set())
                if len(owners) > 1 and len(source_states) == 1:
                    same_state = {owner for owner in owners if normalize(records[owner].get("state", "")) in source_states}
                    if same_state:
                        owners = same_state
                if len(owners) == 1:
                    candidates = owners
                    break
            if not candidates:
                full_words = set(name_form(name).split())
                for (alias_course, words), owners in token_index.items():
                    if alias_course == course and words.issubset(full_words):
                        candidates.update(owners)
            if not candidates:
                for form in name_forms(name):
                    query_words = set(form.split())
                    if len(query_words) < 4 or not query_words - INSTITUTION_WORDS:
                        continue
                    for (alias_course, words), owners in token_index.items():
                        if alias_course == course and query_words.issubset(words):
                            candidates.update(owners)
            if len(candidates) == 1:
                owner = next(iter(candidates))
                matches[key] = owner
                alias_sets[owner].add(name)
                added += 1
            else:
                unresolved.append({"college": name, "course": course, "years": sorted({r["year"] for r in rows}), "rows": len(rows)})
        if not added:
            break
    return matches, unresolved


def retained_reference(row):
    fields = (*HISTORY_FIELDS, "candidateCategory", "seatCategory", "sourceCollege", "sourceQuota")
    return {key: copy.deepcopy(row[key]) for key in fields if key in row}


def normalize_rows(record):
    grouped = defaultdict(list)
    for row in record.get("cutoffs", []):
        grouped[(quota(row.get("quota")), row.get("category"))].append(row)
    normalized = []
    for (pool, category), candidates in sorted(grouped.items()):
        # Pick one active row; historical alternatives live only in history.
        selected = max(candidates, key=lambda c: (c.get("status") == "projected", int(c.get("year", 0))))
        row = copy.deepcopy(selected)
        row.update(year=YEAR, projectionYear=YEAR, yearLabel=LABEL, status="projected", quota=pool)
        ref = reference_for(record, pool, category)
        if ref:
            row.update(historicalReference=retained_reference(ref), sourceYear=ref["year"],
                       historicalClosingRank=ref["closingRank"])
            if row.get("available", True):
                row.update(closingRank=ref["closingRank"], model="historical-air-scenario",
                           projectionMethod="unchanged-historical-baseline", rankBasis=ref["rankBasis"],
                           categoryBasis="Exact historical category AIR retained; check current seat-category eligibility")
        elif row.get("historicalReference"):
            # A missing category may have a UR-derived planning proxy. Its
            # reference remains exact; its projected rank is a separate estimate.
            reference = row["historicalReference"]
            if row.get("model") == "historical-category-proxy" and row.get("available", True):
                factor = 1 if row.get("categoryBasis", "").startswith("Open competition") else {"UR": 1, "EWS": 1.08, "OBC": 1.20, "SC": 1.85, "ST": 2.10}.get(category, 1)
                row["closingRank"] = max(1, round(reference["closingRank"] * factor))
            row.update(sourceYear=reference.get("year"), historicalClosingRank=reference.get("closingRank"),
                       projectionMethod="category-proxy" if row.get("model") == "historical-category-proxy" else "planning-assumption")
        else:
            row.update(sourceYear=None, historicalClosingRank=None,
                       projectionMethod="unavailable" if not row.get("available", True) else "planning-assumption")
        normalized.append(row)
    record["cutoffs"] = normalized


def audit(before, fetched, evidence):
    output = copy.deepcopy(before)
    # A future audit against a smaller/newer source must not discard previously
    # archived intervals that still have an ambiguous institution name.
    fetched = list({json.dumps(row, sort_keys=True): row for row in
                    [*fetched, *before.get("unmatchedHistoricalCutoffs", [])]}.values())
    matches, unresolved = build_matches(output["records"], fetched)
    added = 0
    added_by_year = Counter()
    for source in fetched:
        owner = matches.get((source["college"], source["course"]))
        if owner is None:
            continue
        record = output["records"][owner]
        row = {key: copy.deepcopy(source.get(key)) for key in HISTORY_FIELDS}
        row["quota"] = source.get("counsellingQuota") or source.get("quota")
        signature = history_signature(record["course"], row)
        if any(history_signature(record["course"], existing) == signature for existing in record.get("historicalCutoffs", [])):
            continue
        # Source identity is retained with every restored interval; no rank is
        # recomputed, averaged, scaled or converted to another rank list.
        row.update(sourceCollege=source["college"], sourceQuota=source.get("quota"))
        for key in ("candidateCategory", "seatCategory", "allotmentCount", "allotmentStatus"):
            if key in source:
                row[key] = source[key]
        record.setdefault("historicalCutoffs", []).append(row)
        added += 1
        added_by_year[str(row["year"])] += 1
    for record in output["records"]:
        normalize_rows(record)
    # Keep unresolved fetched intervals as evidence without guessing their
    # college or adding another active course row to the roster.
    unresolved_rows = [copy.deepcopy(row) for row in fetched if (row["college"], row["course"]) not in matches]
    output["unmatchedHistoricalCutoffs"] = unresolved_rows
    old_history = [(i, c) for i, r in enumerate(before["records"]) for c in r.get("historicalCutoffs", [])]
    history = [c for r in output["records"] for c in r.get("historicalCutoffs", [])]
    exact = [(r, c) for r in output["records"] for c in r["cutoffs"] if c.get("projectionMethod") == "unchanged-historical-baseline"]
    coverage = Counter(str(c["sourceYear"]) for _, c in exact)
    active_keys = [(identity(r["college"], r["course"]), c["quota"], c["category"]) for r in output["records"] for c in r["cutoffs"]]
    assert len(active_keys) == len(set(active_keys)), "Duplicate active course/quota/category"
    assert len(output["records"]) == len(before["records"])
    assert all(c in output["records"][i]["historicalCutoffs"] for i, c in old_history), "Existing historical record changed"
    assert output.get("scoreToRank") == before.get("scoreToRank")
    for old, new in zip(before["records"], output["records"]):
        assert {k: v for k, v in old.items() if k not in {"cutoffs", "historicalCutoffs"}} == {k: v for k, v in new.items() if k not in {"cutoffs", "historicalCutoffs"}}, "Roster or financial details changed"
        assert all(c["year"] == YEAR and c["yearLabel"] == LABEL for c in new["cutoffs"])
        for c in new["cutoffs"]:
            ref = reference_for(new, c["quota"], c["category"])
            if ref and c.get("available", True):
                assert c["closingRank"] == ref["closingRank"], "Sourced rank was modified"
    for source in fetched:
        owner = matches.get((source["college"], source["course"]))
        if owner is not None:
            source_signature = history_signature(source["course"], {**source, "quota": source.get("counsellingQuota") or source.get("quota")})
            assert any(history_signature(source["course"], row) == source_signature for row in output["records"][owner]["historicalCutoffs"]), "Fetched historical rank lost"
        else:
            assert source in unresolved_rows
    historical_coverage = Counter(str(year) for r in output["records"] for year in {c["year"] for c in r.get("historicalCutoffs", [])})
    report = {
        "collegeCourseRecords": len(output["records"]), "activeUniqueRows": len(active_keys), "duplicateActiveRows": 0,
        "existingHistoricalRowsPreservedExactly": len(old_history), "historicalRowsRestored": added,
        "restoredByYear": dict(added_by_year), "historicalRowsAfterAudit": len(history),
        "historicalRowsByYear": dict(Counter(str(c["year"]) for c in history)),
        "collegesWithHistoricalDataByYear": dict(historical_coverage),
        "exactHistoricalBaselineRowsByYear": dict(coverage),
        "collegesWith2026HistoricalData": sum(any(c["year"] == 2026 for c in r.get("historicalCutoffs", [])) for r in output["records"]),
        "availableRowsWithoutExactCategoryAIR": sum(c.get("available", True) and c.get("projectionMethod") != "unchanged-historical-baseline" for r in output["records"] for c in r["cutoffs"]),
        "historicalRankLists": dict(Counter(c["rankBasis"] for c in history)),
        "unassignedHistoricalRowsPreserved": len(unresolved_rows),
        "evidence": evidence, "matchedSourceNames": len(matches), "unmatchedSourceNames": unresolved,
        "policy": "One active 2027 Projected Cutoff per college/course/quota/category. Exact latest matching historical AIR is carried forward unchanged. Original source years and all historical intervals remain preserved. Older/state-merit evidence and unsourced assumptions are never labeled as actual 2026 AIR.",
    }
    meta = output.setdefault("meta", {})
    meta.update(collegeCount=len(output["records"]), cutoffRowCount=len(active_keys), cutoffLabel=LABEL,
                activeCutoffYear=YEAR, historicalCutoffRowCount=len(history),
                unmatchedHistoricalCutoffCount=len(unresolved_rows),
                cutoffStatus="2027 display/projection year. Matching sourced AIR closing ranks are retained exactly as historical baselines, with their original source year. Rows without exact AIR evidence remain explicit planning assumptions.")
    meta.setdefault("projectionMethodology", {}).update({
        "historical-air-scenario": "Carry forward the exact closing AIR for the latest matching college/course/quota/category source; prefer 2026 to older years. No 4% tightening or other scaling is applied. projectionYear/yearLabel describe the 2027 display; sourceYear and historicalReference retain the real source year and rank.",
        "historical-category-proxy": "When exact category AIR is absent, a UR-based category scenario may remain. The underlying source rank/year remain exact in historicalReference; the proxy is not an observed category cutoff or guaranteed 2026 evidence.",
    })
    meta["cutoffAudit"] = {key: value for key, value in report.items() if key not in {"unmatchedSourceNames", "evidence"}}
    return output, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "neet-cutoffs.json")
    parser.add_argument("--historical-data", type=Path)
    parser.add_argument("--git-ref", default="HEAD")
    parser.add_argument("--report", type=Path, default=ROOT / "reports" / "neet-cutoff-audit.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    before = json.loads(args.dataset.read_text(encoding="utf-8"))
    if args.historical_data:
        raw = args.historical_data.read_bytes()
        evidence = {"file": str(args.historical_data)}
    else:
        raw = subprocess.run(["git", "show", f"{args.git_ref}:data/neet-cutoffs.json"], cwd=ROOT, capture_output=True, check=True).stdout
        revision = subprocess.run(["git", "rev-parse", args.git_ref], cwd=ROOT, capture_output=True, check=True, text=True).stdout.strip()
        evidence = {"gitRevision": revision, "file": "data/neet-cutoffs.json"}
    evidence["sha256"] = hashlib.sha256(raw).hexdigest()
    fetched = source_rows(json.loads(raw))
    output, report = audit(before, fetched, evidence)
    # Repeating the audit must not change a single college or cutoff row.
    repeated, _ = audit(output, fetched, evidence)
    assert repeated["records"] == output["records"], "Audit is not idempotent"
    if not args.dry_run:
        temporary = args.dataset.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.dataset)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"dryRun": args.dry_run, **{k: v for k, v in report.items() if k not in {"unmatchedSourceNames", "evidence", "policy"}},
                      "unmatchedSourceNameCount": len(report["unmatchedSourceNames"])}, indent=2))


if __name__ == "__main__":
    main()
