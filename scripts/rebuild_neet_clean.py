#!/usr/bin/env python3
"""Rebuild the NEET college roster from the supplied medical-college list.

Usage: python scripts/rebuild_neet_clean.py "path/to/Neet Colleges list.txt"

The TXT supplies the roster and medical details. Existing sourced cutoff rows
and the score-to-rank table are retained when the old dataset is available;
this script never fabricates missing cutoffs or NIRF package values.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
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
STATE_NAMES = {
    "Andhra Pradesh": ("A.P.", "AP"),
    "Arunachal Pradesh": ("Arunachal",),
    "Assam": (),
    "Bihar": (),
    "Chandigarh": (),
    "Chhattisgarh": ("C.G.", "CG"),
    "Dadra and Nagar Haveli and Daman and Diu": ("Dadra and Nagar Haveli", "Daman and Diu"),
    "Delhi": ("NCT of Delhi", "New Delhi"),
    "Goa": (),
    "Gujarat": (),
    "Haryana": (),
    "Himachal Pradesh": ("H.P.", "HP"),
    "Jammu and Kashmir": ("J&K", "Jammu & Kashmir"),
    "Jharkhand": (),
    "Karnataka": (),
    "Kerala": (),
    "Ladakh": (),
    "Lakshadweep": (),
    "Madhya Pradesh": ("M.P.", "MP"),
    "Maharashtra": (),
    "Manipur": (),
    "Meghalaya": (),
    "Mizoram": (),
    "Nagaland": (),
    "Odisha": ("Orissa",),
    "Puducherry": ("Pondicherry",),
    "Punjab": (),
    "Rajasthan": (),
    "Sikkim": (),
    "Tamil Nadu": (),
    "Telangana": (),
    "Tripura": (),
    "Uttar Pradesh": ("U.P.", "UP"),
    "Uttarakhand": ("Uttaranchal",),
    "West Bengal": (),
    "Andaman and Nicobar Islands": ("Andaman & Nicobar Islands",),
}
CITY_GROUPS = {
    "Andhra Pradesh": "Adoni|Anantapur|Anantapuramu|Eluru|Guntur|Kadapa|Kakinada|Kurnool|Machilipatnam|Mangalagiri|Nandyal|Nellore|Ongole|Paderu|Piduguralla|Rajamahendravaram|Srikakulam|Tirupati|Vijayawada|Visakhapatnam|Vizianagaram",
    "Arunachal Pradesh": "Naharlagun|Pasighat",
    "Assam": "Barpeta|Dhubri|Dibrugarh|Diphu|Guwahati|Jorhat|Kokrajhar|Lakhimpur|Nagaon|Nalbari|Silchar|Tezpur|Tinsukia",
    "Bihar": "Arrah|Begusarai|Bhagalpur|Bettiah|Darbhanga|Gaya|Hajipur|Madhepura|Madhubani|Motihari|Muzaffarpur|Nalanda|Patna|Purnea|Purnia|Sasaram",
    "Chandigarh": "Chandigarh",
    "Chhattisgarh": "Ambikapur|Balod|Balodabazar|Bhilai|Bilaspur|Dantewada|Durg|Jagdalpur|Janjgir-Champa|Jashpur|Kabeerdham|Kanker|Kawardha|Korba|Koria|Mahasamund|Manendragarh|Raigarh|Raipur|Rajnandgaon",
    "Dadra and Nagar Haveli and Daman and Diu": "Silvassa|Daman",
    "Delhi": "Delhi|New Delhi",
    "Goa": "Bambolim|Panaji",
    "Gujarat": "Ahmedabad|Bhavnagar|Dahod|Gandhinagar|Godhra|Himatnagar|Jamnagar|Junagadh|Morbi|Nadiad|Navsari|Patan|Porbandar|Rajkot|Rajpipla|Surat|Vadodara|Valsad",
    "Haryana": "Ambala|Bhiwani|Faridabad|Gurugram|Hisar|Jhajjar|Karnal|Mullana|Narnaul|Nuh|Rewari|Rohtak|Sonepat|Sonipat|Yamunanagar",
    "Himachal Pradesh": "Bilaspur|Chamba|Hamirpur|Kangra|Mandi|Nahan|Shimla|Tanda|Una",
    "Jammu and Kashmir": "Anantnag|Baramulla|Doda|Jammu|Kathua|Kupwara|Rajouri|Srinagar|Udhampur",
    "Jharkhand": "Chaibasa|Deoghar|Dhanbad|Dumka|Hazaribagh|Jamshedpur|Palamu|Ranchi",
    "Karnataka": "Bagalkot|Ballari|Belagavi|Bengaluru|Bidar|Chamarajanagar|Chikkaballapura|Chikkamagaluru|Chitradurga|Davanagere|Dharwad|Gadag|Hassan|Haveri|Hubballi|Kalaburagi|Karwar|Kodagu|Kolar|Koppal|Madikeri|Mangaluru|Mandya|Manipal|Mysuru|Raichur|Shivamogga|T. Begur|Tumakuru|Udupi|Vijayapura|Yadgir",
    "Kerala": "Alappuzha|Ernakulam|Idukki|Kannur|Kasaragod|Kochi|Kollam|Kottayam|Kozhikode|Malappuram|Manjeri|Palakkad|Pariyaram|Pathanamthitta|Thiruvananthapuram|Thrissur|Wayanad|Konni",
    "Madhya Pradesh": "Bhopal|Chhindwara|Datia|Guna|Gwalior|Indore|Jabalpur|Khandwa|Mandsaur|Morena|Neemuch|Ratlam|Rewa|Sagar|Satna|Seoni|Shahdol|Sheopur|Shivpuri|Singrauli|Ujjain|Vidisha",
    "Maharashtra": "Akola|Ambernath|Amravati|Aurangabad|Ambajogai|Bhandara|Beed|Buldhana|Chandrapur|Chhatrapati Sambhajinagar|Dharashiv|Dhule|Gadchiroli|Gondia|Hingoli|Jalgaon|Jalna|Karad|Kolhapur|Latur|Loni|Mumbai|Nagpur|Nanded|Nandurbar|Nashik|Navi Mumbai|Osmanabad|Palghar|Parbhani|Pune|Raigad|Rahata|Ratnagiri|Sangli|Satara|Solapur|Sindhudurg|Thane|Wardha|Washim|Yavatmal",
    "Manipur": "Churachandpur|Imphal",
    "Meghalaya": "Shillong",
    "Mizoram": "Aizawl",
    "Nagaland": "Kohima",
    "Odisha": "Balangir|Balasore|Baleshwar|Baripada|Bhawanipatna|Bhubaneswar|Brahmapur|Berhampur|Burla|Cuttack|Dhenkanal|Jajpur|Jharsuguda|Keonjhar|Koraput|Phulbani|Puri|Rayagada|Rourkela|Sambalpur|Sundargarh|Talcher",
    "Punjab": "Amritsar|Bathinda|Faridkot|Firozpur|Gurdaspur|Hoshiarpur|Ludhiana|Moga|Mohali|Patiala|Sangrur",
    "Rajasthan": "Ajmer|Alwar|Barmer|Banswara|Baran|Bharatpur|Bhilwara|Bikaner|Bundi|Chittorgarh|Churu|Dausa|Dholpur|Dungarpur|Hanumangarh|Jaipur|Jaisalmer|Jhalawar|Jhunjhunu|Jodhpur|Karauli|Kota|Nagaur|Pali|Sawai Madhopur|Sikar|Sirohi|Sri Ganganagar|Tonk|Udaipur",
    "Sikkim": "Gangtok",
    "Tamil Nadu": "Ariyalur|Chengalpattu|Chennai|Chidambaram|Coimbatore|Cuddalore|Dharmapuri|Dindigul|Erode|Hosur|Kallakurichi|Kanchipuram|Kanyakumari|Karur|Kattankulathur|Krishnagiri|Madurai|Nagapattinam|Namakkal|Nilgiris|Ooty|Perambalur|Pudukkottai|Ramanathapuram|Salem|Sivaganga|Thanjavur|Theni|Thoothukudi|Tiruchirappalli|Tirunelveli|Tiruppur|Tiruvallur|Thiruvallur|Tiruvannamalai|Tiruvarur|Thiruvarur|Vellore|Villupuram|Virudhunagar",
    "Telangana": "Adilabad|Asifabad|Bhadradri|Gadwal|Hyderabad|Jagtial|Jangaon|Jayashankar Bhupalpally|Jogulamba Gadwal|Kamareddy|Karimnagar|Khammam|Kodangal|Mahabubabad|Mahabubnagar|Maheshwaram|Mancherial|Medak|Mulugu|Nagarkurnool|Nalgonda|Narsampet|Narayanpet|Nirmal|Nizamabad|Quthbullapur|Ramagundam|Rajanna Sircilla|Sangareddy|Secunderabad|Siddipet|Suryapet|Vikarabad|Wanaparthy|Warangal|Yadadri",
    "Tripura": "Agartala",
    "Uttar Pradesh": "Agra|Aligarh|Amethi|Ambedkar Nagar|Ambedkarnagar|Auraiya|Ayodhya|Azamgarh|Bahraich|Banda|Barabanki|Bareilly|Badaun|Basti|Bijnor|Budaun|Bulandshahr|Chandauli|Deoria|Etah|Etawah|Faizabad|Fatehpur|Firozabad|Ghaziabad|Ghazipur|Gonda|Gorakhpur|Hardoi|Hathras|Jalaun|Jaunpur|Jhansi|Kannauj|Kanpur|Kaushambi|Kushinagar|Lakhimpur|Lalitpur|Lucknow|Maharajganj|Mainpuri|Mathura|Meerut|Mirzapur|Moradabad|Muzaffarnagar|Noida|Pilibhit|Pratapgarh|Prayagraj|Raebareli|Rae Bareli|Rampur|Saifai|Saharanpur|Sambhal|Shahjahanpur|Shamli|Shravasti|Siddharthnagar|Sitapur|Sonbhadra|Sultanpur|Unnao|Varanasi",
    "Uttarakhand": "Almora|Dehradun|Haldwani|Haridwar|Nainital|Pauri|Pithoragarh|Rishikesh|Rudrapur|Srinagar",
    "West Bengal": "Arambagh|Bankura|Barasat|Bardhaman|Burdwan|Cooch Behar|Coochbehar|Darjeeling|Diamond Harbour|Durgapur|Howrah|Jhargram|Jalpaiguri|Kalyani|Kolkata|Malda|Medinipur|Midnapore|Murshidabad|Nadia|Purulia|Raiganj|Rampurhat|Siliguri|Tamluk|Uluberia",
    "Andaman and Nicobar Islands": "Port Blair",
    "Ladakh": "Leh",
    "Lakshadweep": "Kavaratti",
    "Puducherry": "Karaikal|Puducherry",
}
CITY_ALIASES = {
    "Allahabad": "Prayagraj", "Alleppey": "Alappuzha", "Bangalore": "Bengaluru",
    "Bellary": "Ballari", "Belgaum": "Belagavi", "Calcutta": "Kolkata",
    "Calicut": "Kozhikode", "Cannanore": "Kannur", "Chinsurah": "Hooghly",
    "Cochin": "Kochi", "Gulbarga": "Kalaburagi", "Jalpaiguri": "Jalpaiguri",
    "Madras": "Chennai", "Mangalore": "Mangaluru", "Mysore": "Mysuru",
    "Osm": "Osmanabad", "Pondicherry": "Puducherry", "Poona": "Pune",
    "Simla": "Shimla", "Sonepat": "Sonipat", "Tumkur": "Tumakuru",
    "Trichur": "Thrissur", "Trichy": "Tiruchirappalli",
    "Trivandrum": "Thiruvananthapuram", "Vizag": "Visakhapatnam",
    "Rae Bareli": "Raebareli", "SAS Nagar": "Mohali",
    "Ananthapuramu": "Anantapuramu",
}
CENTRAL_MARKERS = (
    "aiims", "jipmer", "central armed police", "aiims-capfims",
    "aligarh muslim university", "amu", "banaras hindu university", "ims bhu",
    "esic", "vardhman mahavir", "safdarjung",
)
GOVERNMENT_MARKERS = (
    "government", "govt", "municipal", "autonomous state medical college",
    "gmc", "government dental", "govt dental",
)
GENERIC_SOURCE_HEADER = {
    "College", "Course", "Internship Stipend", "Annual Fee", "Service Bond",
}
RUPEE_AMOUNT = re.compile(r"₹\s*([\d,]+(?:\.\d+)?)")
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"\b([A-Z])\.\s*([A-Z])\.", lambda m: m.group(1) + m.group(2), value, flags=re.I)
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def state_aliases() -> dict[str, str]:
    result: dict[str, str] = {}
    for state, aliases in STATE_NAMES.items():
        for alias in (state, *aliases):
            result[normalize(alias)] = state
    return result


STATE_ALIASES = state_aliases()
CITY_STATE: dict[str, list[tuple[str, str]]] = defaultdict(list)
for _state, _cities in CITY_GROUPS.items():
    for _city in _cities.split("|"):
        _canonical = CITY_ALIASES.get(_city, _city)
        _candidate = (_canonical, _state)
        if _candidate not in CITY_STATE[normalize(_city)]:
            CITY_STATE[normalize(_city)].append(_candidate)
for _alias, _canonical in CITY_ALIASES.items():
    if normalize(_canonical) in CITY_STATE:
        for _candidate in CITY_STATE[normalize(_canonical)]:
            if _candidate not in CITY_STATE[normalize(_alias)]:
                CITY_STATE[normalize(_alias)].append(_candidate)


def latest_location_match(text: str, lookup: dict[str, Any]) -> tuple[str, Any] | None:
    best: tuple[int, int, str, Any] | None = None
    for phrase, value in lookup.items():
        if not phrase:
            continue
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])")
        for match in pattern.finditer(text):
            candidate = (match.end(), len(phrase), phrase, value)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    return (best[2], best[3]) if best else None


def clean_college_name(value: str) -> str:
    parts = [re.sub(r"\s+", " ", part).strip() for part in value.split(",")]
    while len(parts) > 1 and normalize(parts[-1]) in STATE_ALIASES:
        parts.pop()
    return ", ".join(part for part in parts if part)


def extract_state_city(value: str) -> tuple[str | None, str | None]:
    text = normalize(value)
    full_state_aliases = {
        normalize(alias): state
        for state, aliases in STATE_NAMES.items()
        for alias in (state, *aliases)
        if len(normalize(alias).split()) > 1 or normalize(alias) not in {"ap", "cg", "hp", "jk", "mp", "up"}
    }
    explicit = latest_location_match(text, full_state_aliases)
    for component in reversed(value.split(",")):
        trailing_state = STATE_ALIASES.get(normalize(component))
        if trailing_state:
            explicit = (normalize(component), trailing_state)
            break
    city_match = latest_location_match(text, CITY_STATE)
    state = explicit[1] if explicit else None
    city = None
    if city_match:
        candidates = city_match[1]
        selected = next((candidate for candidate in candidates if candidate[1] == state), None) if state else None
        if selected is None:
            selected = candidates[0]
        if selected:
            city, inferred_state = selected
            state = inferred_state
    return state, city


def parse_detail(row: list[str], line_number: int) -> dict[str, str]:
    if len(row) < 5:
        raise ValueError(f"line {line_number}: expected at least five fields")
    fragments = row[2:]
    stipend_end = next(
        (i for i, value in enumerate(fragments) if "/month" in value.lower()),
        None,
    )
    if stipend_end is None:
        raise ValueError(f"line {line_number}: stipend field must end in /month")
    bond_start = next(
        (i for i, value in enumerate(fragments) if BOND_START.match(value.strip())),
        None,
    )
    if bond_start is None or bond_start <= stipend_end:
        raise ValueError(f"line {line_number}: could not identify the service-bond field")
    stipend = ",".join(fragments[: stipend_end + 1]).strip()
    fee = ",".join(fragments[stipend_end + 1 : bond_start]).strip()
    bond = ",".join(fragments[bond_start:]).strip()
    if not stipend or not fee or not bond:
        raise ValueError(f"line {line_number}: a medical detail is empty")
    return {"internshipStipend": stipend, "annualFeeDisplay": fee, "serviceBond": bond}


def stipend_number(value: str) -> float | None:
    amounts = [float(x.replace(",", "")) for x in RUPEE_AMOUNT.findall(value)]
    if amounts:
        return max(amounts)
    amounts = [float(x.replace(",", "")) for x in NUMBER.findall(value)]
    return max(amounts) if amounts else None


def fee_number(value: str) -> float | None:
    amounts = [float(x.replace(",", "")) for x in RUPEE_AMOUNT.findall(value)]
    return amounts[0] if amounts else None


def bond_applies(value: str) -> bool:
    return not bool(re.match(r"^\s*no\s+(?:rural\s+)?bond\b", value, re.IGNORECASE))


def compact_cutoff(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "year": record.get("year"),
        "quota": record.get("counsellingQuota") or record.get("quota"),
        "category": record.get("category") or record.get("candidateCategory"),
        "openingRank": record.get("openingRank"),
        "closingRank": record.get("closingRank"),
        "round": record.get("round"),
        "rankBasis": record.get("rankBasis"),
        "seatQuota": record.get("seatQuota"),
        "source": record.get("source"),
    }


def seat_quota_priority(record: dict[str, Any]) -> int:
    seat_quota = normalize(str(record.get("seatQuota") or ""))
    if any(marker in seat_quota for marker in ("all india", "open seat quota", "govt quota", "government quota")):
        return 0
    if any(marker in seat_quota for marker in ("deemed paid", "self financed merit")):
        return 1
    if "management quota" in seat_quota:
        return 3
    if any(marker in seat_quota for marker in ("employees state insurance", " esi ", "nri", "foreign")):
        return 4
    return 2


def cutoff_round_order(record: dict[str, Any]) -> int:
    round_name = normalize(str(record.get("round") or ""))
    if "stray" in round_name:
        return 100
    if "mop up" in round_name:
        return 90
    match = re.search(r"\bround\s+(\d+)\b", round_name)
    return int(match.group(1)) if match else 0


def choose_cutoff(records: list[dict[str, Any]]) -> dict[str, Any]:
    return min(
        records,
        key=lambda item: (
            seat_quota_priority(item),
            -cutoff_round_order(item),
            -int(item.get("closingRank") or 0),
            normalize(str(item.get("seatQuota") or "")),
            str(item.get("source") or ""),
        ),
    )


def deduplicate_cutoffs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(str(record.get("quota") or ""), str(record.get("category") or ""))].append(record)

    result: list[dict[str, Any]] = []
    for candidates in grouped.values():
        latest_year = max(int(item.get("year") or 0) for item in candidates)
        latest_candidates = [item for item in candidates if int(item.get("year") or 0) == latest_year]
        latest = dict(choose_cutoff(latest_candidates))
        previous_years = [int(item.get("year") or 0) for item in candidates if int(item.get("year") or 0) < latest_year]
        if previous_years:
            previous_year = max(previous_years)
            previous_candidates = [
                item for item in candidates if int(item.get("year") or 0) == previous_year
            ]
            matching_quota = [
                item for item in previous_candidates
                if normalize(str(item.get("seatQuota") or ""))
                == normalize(str(latest.get("seatQuota") or ""))
            ]
            matching_tier = [
                item for item in previous_candidates
                if seat_quota_priority(item) == seat_quota_priority(latest)
            ]
            previous = choose_cutoff(matching_quota or matching_tier) if matching_quota or matching_tier else None
            if previous:
                latest["previousYear"] = previous.get("year")
                latest["previousYearClosingRank"] = previous.get("closingRank")
                latest["previousYearRound"] = previous.get("round")
                latest["previousYearSeatQuota"] = previous.get("seatQuota")
        result.append(latest)
    return sorted(
        result,
        key=lambda item: (
            int(item.get("year") or 0),
            str(item.get("quota") or ""),
            str(item.get("category") or ""),
        ),
    )


def old_cutoffs(
    old: dict[str, Any], source_names: set[str]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Counter[str]]]:
    cutoff_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    type_votes: dict[str, Counter[str]] = defaultdict(Counter)
    clean_records = old.get("records", [])

    if clean_records and isinstance(clean_records[0].get("cutoffs"), list):
        for record in clean_records:
            source_name = record.get("sourceName") or record.get("college")
            if source_name not in source_names:
                continue
            cutoff_map[source_name].extend(record.get("cutoffs") or [])
            if record.get("collegeType"):
                type_votes[source_name][record["collegeType"]] += 1
        return cutoff_map, type_votes

    detail_rows = old.get("medicalCollegeDetails") or {}
    alias_owner: dict[tuple[str, str], str] = {}
    for key, details in detail_rows.items():
        source_name = details.get("sourceCollegeName") or key
        if source_name not in source_names:
            continue
        course = str(details.get("course") or "").upper()
        for alias in details.get("aliases") or []:
            alias_owner[(course, alias)] = source_name

    for record in clean_records:
        course = str(record.get("course") or "").upper()
        source_name = alias_owner.get((course, record.get("college")))
        if source_name is None:
            continue
        cutoff_map[source_name].append(compact_cutoff(record))
        if record.get("type"):
            type_votes[source_name][record["type"]] += 1
    return cutoff_map, type_votes


def classify_college(
    name: str, course: str, type_votes: Counter[str]
) -> str:
    normalized_name = normalize(name)
    if any(normalize(marker) in normalized_name for marker in CENTRAL_MARKERS):
        return "AIIMS / Central Govt"
    private_votes = type_votes.get("Deemed/Private", 0) + type_votes.get("Deemed / Private", 0)
    government_votes = type_votes.get("Govt MBBS", 0) + type_votes.get("Govt BDS", 0)
    if private_votes > government_votes:
        return "Deemed / Private"
    if government_votes or any(normalize(marker) in normalized_name for marker in GOVERNMENT_MARKERS):
        return "Govt MBBS" if course == "MBBS" else "Govt BDS"
    return "Deemed / Private"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="the five-column college text file")
    parser.add_argument("--dataset", type=Path, default=DATASET, help="NEET dataset to rebuild")
    args = parser.parse_args()

    with args.source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows or rows[0] != HEADER:
        raise ValueError(f"expected source header: {','.join(HEADER)}")

    old: dict[str, Any] = json.loads(args.dataset.read_text(encoding="utf-8"))
    score_to_rank = old.get("scoreToRank", old.get("scoreAir"))
    if not isinstance(score_to_rank, list) or len(score_to_rank) != 581:
        raise ValueError("the existing 720-to-140 score-to-rank table is missing or incomplete")

    parsed_by_pair: dict[tuple[str, str], tuple[str, dict[str, str], int]] = {}
    for line_number, row in enumerate(rows[1:], start=2):
        name = re.sub(r"\s+", " ", row[0]).strip()
        course = row[1].strip().upper()
        if course not in {"MBBS", "BDS"}:
            raise ValueError(f"line {line_number}: unsupported course {course!r}")
        details = parse_detail(row, line_number)
        key = (name, course)
        if key in parsed_by_pair:
            previous = parsed_by_pair[key][1]
            if previous != details:
                raise ValueError(f"line {line_number}: duplicate college/course has conflicting values")
            continue
        parsed_by_pair[key] = (name, details, line_number)

    if len(parsed_by_pair) != 616:
        raise ValueError(f"expected exactly 616 unique college/course records, found {len(parsed_by_pair)}")

    source_names = {name for name, _ in parsed_by_pair}
    cutoff_map, type_votes = old_cutoffs(old, source_names)
    missing_location: list[str] = []
    records: list[dict[str, Any]] = []
    seen_clean_pairs: set[tuple[str, str]] = set()
    cutoff_count = 0
    for (source_name, course), (name, details, _) in parsed_by_pair.items():
        college = clean_college_name(name)
        pair = (college, course)
        if pair in seen_clean_pairs:
            raise ValueError(f"college cleanup created a duplicate record: {pair}")
        seen_clean_pairs.add(pair)
        state, city = extract_state_city(name)
        if not state or not city:
            missing_location.append(name)
        cutoffs = cutoff_map.get(source_name, [])
        deduplicated: dict[str, dict[str, Any]] = {}
        for cutoff in cutoffs:
            compact = compact_cutoff(cutoff) if "closingRank" not in cutoff else cutoff
            signature = json.dumps(compact, sort_keys=True, ensure_ascii=False)
            deduplicated[signature] = compact
        cutoff_rows = deduplicate_cutoffs(list(deduplicated.values()))
        cutoff_count += len(cutoff_rows)
        records.append({
            "college": college,
            "sourceName": source_name,
            "state": state,
            "city": city,
            "course": course,
            "collegeType": classify_college(name, course, type_votes[source_name]),
            **details,
            "stipendNumeric": stipend_number(details["internshipStipend"]),
            "annualFeeNumeric": fee_number(details["annualFeeDisplay"]),
            "hasBond": bond_applies(details["serviceBond"]),
            "nirfMedianPackage": None,
            "cutoffs": cutoff_rows,
        })

    if missing_location:
        preview = "\n".join(f"- {name}" for name in missing_location[:30])
        raise ValueError(
            f"could not infer state and city for {len(missing_location)} rows:\n{preview}"
        )

    records.sort(key=lambda item: (item["college"].casefold(), item["course"]))
    dataset = {
        "meta": {
            "dataset": "NEET UG clean college/course roster",
            "updated": date.today().isoformat(),
            "rosterSource": "User-provided Neet Colleges list.txt",
            "rosterStatus": "User-provided text; stipend, fee, and bond values are unverified and have no source URLs",
            "cutoffStatus": (
                "Only existing sourced cutoff rows matched to this roster are retained. One latest "
                "year row is kept per college, course, quota, and category; a comparable prior-year "
                "closing rank is stored for trend display. No cutoff ranks are estimated."
            ),
            "scoreToRankNotice": (
                "Preserved the existing 720-to-140 score/AIR mapping. NTA does not publish an "
                "exact rank for every score; the mapping retains its published-band uncertainty."
            ),
            "nirfNotice": (
                "NIRF median-package values were not supplied or present in the existing medical "
                "records; values remain null rather than being inferred."
            ),
            "collegeCount": len(records),
            "courseCounts": dict(sorted(Counter(item["course"] for item in records).items())),
            "recordsWithCutoffs": sum(bool(item["cutoffs"]) for item in records),
            "cutoffRowCount": cutoff_count,
            "stateQuotaCoverage": "Retained only for colleges with existing sourced state-merit rows; no AIR-to-state-rank conversion.",
        },
        "scoreToRank": score_to_rank,
        "records": records,
    }

    temporary = args.dataset.with_suffix(args.dataset.suffix + ".tmp")
    temporary.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.dataset)
    print(
        f"Rebuilt {len(records)} college/course records; "
        f"{dataset['meta']['recordsWithCutoffs']} have sourced cutoffs "
        f"({cutoff_count} cutoff rows). "
        f"Location inference complete for all records."
    )


if __name__ == "__main__":
    main()
