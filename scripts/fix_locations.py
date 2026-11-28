#!/usr/bin/env python3
"""Fill missing college city/state/location fields in predictor datasets."""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rebuild_neet_clean import CITY_STATE, normalize

PLACEHOLDER = re.compile(
    r"^(?:location\s+(?:not\s+updated|not\s+published|unavailable|not\s+available|not\s+found)|"
    r"(?:city|state|location)\s+(?:not\s+updated|unknown|unavailable)|"
    r"not\s+updated|unknown|unavailable|n/?a|none|null)$",
    re.IGNORECASE,
)

# Additional spellings and localities found in the repository's college names
# and campus addresses. Values use a canonical city and state.
EXTRA_CITY_LOCATIONS: dict[str, tuple[str, str]] = {
    "Ahmadabad": ("Ahmedabad", "Gujarat"),
    "Amalapuram": ("Amalapuram", "Andhra Pradesh"),
    "Amreli": ("Amreli", "Gujarat"),
    "Agroha": ("Agroha", "Haryana"),
    "Bharuch": ("Bharuch", "Gujarat"),
    "Bhadohi": ("Bhadohi", "Uttar Pradesh"),
    "Bhuj": ("Bhuj", "Gujarat"),
    "Bolpur": ("Bolpur", "West Bengal"),
    "Chittoor": ("Chittoor", "Andhra Pradesh"),
    "Coimbatore": ("Coimbatore", "Tamil Nadu"),
    "Gajraula": ("Gajraula", "Uttar Pradesh"),
    "Harohalli": ("Harohalli", "Karnataka"),
    "Banur": ("Banur", "Punjab"),
    "Gurgaon": ("Gurugram", "Haryana"),
    "Hapur": ("Hapur", "Uttar Pradesh"),
    "Hisar": ("Hisar", "Haryana"),
    "Haldia": ("Haldia", "West Bengal"),
    "Jalandhar": ("Jalandhar", "Punjab"),
    "Kishanganj": ("Kishanganj", "Bihar"),
    "Katihar": ("Katihar", "Bihar"),
    "Kalburgi": ("Kalaburagi", "Karnataka"),
    "Kuppam": ("Kuppam", "Andhra Pradesh"),
    "Kumarhatti": ("Kumarhatti", "Himachal Pradesh"),
    "Moradabad": ("Moradabad", "Uttar Pradesh"),
    "Motihari": ("Motihari", "Bihar"),
    "Nagpur": ("Nagpur", "Maharashtra"),
    "Ponda": ("Ponda", "Goa"),
    "Chikkaballapur": ("Chikkaballapur", "Karnataka"),
    "Chikkaballapura": ("Chikkaballapur", "Karnataka"),
    "Seraikala": ("Seraikela", "Jharkhand"),
    "Umarda": ("Udaipur", "Rajasthan"),
    "Raniganj": ("Raniganj", "West Bengal"),
    "Saharsa": ("Saharsa", "Bihar"),
    "Sehore": ("Sehore", "Madhya Pradesh"),
    "Shivamogga": ("Shivamogga", "Karnataka"),
    "Sri Ganganagar": ("Sri Ganganagar", "Rajasthan"),
    "Tirunelveli": ("Tirunelveli", "Tamil Nadu"),
    "Yupia": ("Yupia", "Arunachal Pradesh"),
    "Ahmednagar": ("Ahilyanagar", "Maharashtra"),
    "Amargadh": ("Bhavnagar", "Gujarat"),
    "Amrutnagar": ("Sangamner", "Maharashtra"),
    "Ananthapur": ("Anantapur", "Andhra Pradesh"),
    "Ananthapuramu": ("Anantapur", "Andhra Pradesh"),
    "Anaparthi": ("Anaparthi", "Andhra Pradesh"),
    "Akkupete": ("Devanahalli", "Karnataka"),
    "Aziznagar": ("Hyderabad", "Telangana"),
    "Bagalkote": ("Bagalkot", "Karnataka"),
    "Bangalore": ("Bengaluru", "Karnataka"),
    "Bangaluru": ("Bengaluru", "Karnataka"),
    "Bantwal": ("Bantwal", "Karnataka"),
    "Bhatinda": ("Bathinda", "Punjab"),
    "Bhatkal": ("Bhatkal", "Karnataka"),
    "B.H. Road": ("Tiptur", "Karnataka"),
    "Bidadi": ("Bidadi", "Karnataka"),
    "Bijapur": ("Vijayapura", "Karnataka"),
    "Bellur": ("Bellur", "Karnataka"),
    "Bedwas": ("Udaipur", "Rajasthan"),
    "Bengaluru": ("Bengaluru", "Karnataka"),
    "Budge Budge": ("Kolkata", "West Bengal"),
    "Chamarajanagara": ("Chamarajanagar", "Karnataka"),
    "Chamarajanagar": ("Chamarajanagar", "Karnataka"),
    "Channapatna": ("Channapatna", "Karnataka"),
    "Channapatana": ("Channapatna", "Karnataka"),
    "Chevella": ("Chevella", "Telangana"),
    "Chickballapur": ("Chikkaballapur", "Karnataka"),
    "Chickmagalur": ("Chikkamagaluru", "Karnataka"),
    "Chikmagalur": ("Chikkamagaluru", "Karnataka"),
    "Chikkaballapura": ("Chikkaballapur", "Karnataka"),
    "Chinnoutpalli": ("Vijayawada", "Andhra Pradesh"),
    "Chinoutpalli": ("Vijayawada", "Andhra Pradesh"),
    "Chintamani": ("Chintamani", "Karnataka"),
    "Chitradurga": ("Chitradurga", "Karnataka"),
    "Chumukedima": ("Dimapur", "Nagaland"),
    "Coorg": ("Ponnampet", "Karnataka"),
    "Dandeli": ("Dandeli", "Karnataka"),
    "Devanahalli": ("Bengaluru", "Karnataka"),
    "Doddaballapur": ("Doddaballapur", "Karnataka"),
    "Dodda Kammanahalli": ("Bengaluru", "Karnataka"),
    "Davangere": ("Davanagere", "Karnataka"),
    "Davanagere": ("Davanagere", "Karnataka"),
    "Dharwad": ("Dharwad", "Karnataka"),
    "Dewas": ("Dewas", "Madhya Pradesh"),
    "Elayampalayam": ("Namakkal", "Tamil Nadu"),
    "Fatehgarh Sahib": ("Mandi Gobindgarh", "Punjab"),
    "Gannavaram": ("Vijayawada", "Andhra Pradesh"),
    "Ghanpur": ("Warangal", "Telangana"),
    "Gokak": ("Gokak", "Karnataka"),
    "Gulbarga": ("Kalaburagi", "Karnataka"),
    "Gulabgarh": ("Rupnagar", "Punjab"),
    "Hadiyol": ("Himatnagar", "Gujarat"),
    "Haliyal": ("Haliyal", "Karnataka"),
    "Hanamkonda": ("Warangal", "Telangana"),
    "Hesaraghatta": ("Bengaluru", "Karnataka"),
    "Himatnagar": ("Himatnagar", "Gujarat"),
    "Himmatnagar": ("Himatnagar", "Gujarat"),
    "Hoovina Hadagali": ("Hoovina Hadagali", "Karnataka"),
    "Huvinahadagali": ("Hoovina Hadagali", "Karnataka"),
    "Humnabad": ("Humnabad", "Karnataka"),
    "Jigani": ("Bengaluru", "Karnataka"),
    "Kalaburgi": ("Kalaburagi", "Karnataka"),
    "Kalaburagi": ("Kalaburagi", "Karnataka"),
    "Kalol": ("Kalol", "Gujarat"),
    "Kanaka": ("Hyderabad", "Telangana"),
    "Kancheepuram": ("Kanchipuram", "Tamil Nadu"),
    "Karakonam": ("Thiruvananthapuram", "Kerala"),
    "Karjat": ("Karjat", "Maharashtra"),
    "Karamsad": ("Anand", "Gujarat"),
    "Kavalkinaru": ("Tirunelveli", "Tamil Nadu"),
    "K.G.F.": ("Kolar", "Karnataka"),
    "Kolar Gold Fields": ("Kolar", "Karnataka"),
    "Kolenchery": ("Kochi", "Kerala"),
    "Komarapalayam": ("Namakkal", "Tamil Nadu"),
    "Kothamangalam": ("Kochi", "Kerala"),
    "Kothnur": ("Bengaluru", "Karnataka"),
    "Kotegangoorsagar": ("Shivamogga", "Karnataka"),
    "Kudligi": ("Kudligi", "Karnataka"),
    "Kundrathur": ("Chennai", "Tamil Nadu"),
    "Kushalanagar": ("Kushalanagar", "Karnataka"),
    "Kushalnagar": ("Kushalanagar", "Karnataka"),
    "Longowal": ("Sangrur", "Punjab"),
    "Maduranthagam": ("Maduranthakam", "Tamil Nadu"),
    "Mahabubnagar": ("Mahabubnagar", "Telangana"),
    "Mahbubnagar": ("Mahabubnagar", "Telangana"),
    "Mehboobnagar": ("Mahabubnagar", "Telangana"),
    "Malkajgiri": ("Hyderabad", "Telangana"),
    "Bachupally": ("Hyderabad", "Telangana"),
    "Mallur": ("Bengaluru", "Karnataka"),
    "Mangode": ("Palakkad", "Kerala"),
    "Mangaluru": ("Mangaluru", "Karnataka"),
    "Mangalore": ("Mangaluru", "Karnataka"),
    "Mandi Gobindgarh": ("Mandi Gobindgarh", "Punjab"),
    "Mehsana": ("Mehsana", "Gujarat"),
    "Melmaruvathur": ("Melmaruvathur", "Tamil Nadu"),
    "Mudhol": ("Mudhol", "Karnataka"),
    "Murshidabad": ("Murshidabad", "West Bengal"),
    "Mysore": ("Mysuru", "Karnataka"),
    "Mysuru": ("Mysuru", "Karnataka"),
    "Nadiad": ("Nadiad", "Gujarat"),
    "Narketpally": ("Narketpally", "Telangana"),
    "Narketpalli": ("Narketpally", "Telangana"),
    "Nelamangala": ("Nelamangala", "Karnataka"),
    "New Pargaon": ("Kolhapur", "Maharashtra"),
    "Nasik": ("Nashik", "Maharashtra"),
    "Nashik": ("Nashik", "Maharashtra"),
    "Palanpur": ("Palanpur", "Gujarat"),
    "Panchkula": ("Panchkula", "Haryana"),
    "Panipat": ("Panipat", "Haryana"),
    "Paonta Sahib": ("Paonta Sahib", "Himachal Pradesh"),
    "Patan": ("Patan", "Gujarat"),
    "Patancheru": ("Hyderabad", "Telangana"),
    "Peerancheru": ("Hyderabad", "Telangana"),
    "Ponnampet": ("Ponnampet", "Karnataka"),
    "Puttur": ("Puttur", "Karnataka"),
    "Purale": ("Shivamogga", "Karnataka"),
    "Ramanagaram": ("Ramanagara", "Karnataka"),
    "Ramanagara": ("Ramanagara", "Karnataka"),
    "Rajahmundry": ("Rajamahendravaram", "Andhra Pradesh"),
    "Rajamahendravaram": ("Rajamahendravaram", "Andhra Pradesh"),
    "Rajsamand": ("Rajsamand", "Rajasthan"),
    "Rangareddy": ("Hyderabad", "Telangana"),
    "Rangareddy District": ("Hyderabad", "Telangana"),
    "Sangamner": ("Sangamner", "Maharashtra"),
    "Seraikela": ("Seraikela", "Jharkhand"),
    "Shahabad": ("Kurukshetra", "Haryana"),
    "Shamli": ("Shamli", "Uttar Pradesh"),
    "Shivamogga": ("Shivamogga", "Karnataka"),
    "Shimoga": ("Shivamogga", "Karnataka"),
    "Shivamogga Road": ("Shivamogga", "Karnataka"),
    "Siruvachur": ("Perambalur", "Tamil Nadu"),
    "Sullia": ("Sullia", "Karnataka"),
    "Sundernagar": ("Sundernagar", "Himachal Pradesh"),
    "Sunam": ("Sunam", "Punjab"),
    "Surendranagar": ("Surendranagar", "Gujarat"),
    "Tadepalligudem": ("Tadepalligudem", "Andhra Pradesh"),
    "Tiptur": ("Tiptur", "Karnataka"),
    "Thodupuzha": ("Thodupuzha", "Kerala"),
    "Tiruvalla": ("Tiruvalla", "Kerala"),
    "Tiruvannamalai": ("Tiruvannamalai", "Tamil Nadu"),
    "Ujjire": ("Ujjire", "Karnataka"),
    "Ujire": ("Ujjire", "Karnataka"),
    "Vadnagar": ("Vadnagar", "Gujarat"),
    "Vadodara": ("Vadodara", "Gujarat"),
    "Varadanayakana Halli": ("Nelamangala", "Karnataka"),
    "Vijayapura": ("Vijayapura", "Karnataka"),
    "Virajpat": ("Virajpet", "Karnataka"),
    "Virajpet": ("Virajpet", "Karnataka"),
    "Visakhapatnam": ("Visakhapatnam", "Andhra Pradesh"),
    "Vishakhapatnam": ("Visakhapatnam", "Andhra Pradesh"),
    "Yadadri": ("Hyderabad", "Telangana"),
    "Yelahanka": ("Bengaluru", "Karnataka"),
    "Yamuna Nagar": ("Yamunanagar", "Haryana"),
    "Yamunanagar": ("Yamunanagar", "Haryana"),
    "Yenkapally": ("Hyderabad", "Telangana"),
    "Yeola": ("Yeola", "Maharashtra"),
}

# Some institute names do not include a city. These campus-specific entries
# cover those names without assigning a city from the state alone.
COLLEGE_LOCATION_OVERRIDES: dict[str, tuple[str, str]] = {
    "aiims bibinagar": ("Hyderabad", "Telangana"),
    "iiitdm kancheepuram": ("Chennai", "Tamil Nadu"),
    "iiitdm kanchipuram": ("Chennai", "Tamil Nadu"),
    "rv college of engineering": ("Bengaluru", "Karnataka"),
    "ajay sangaal institute": ("Shamli", "Uttar Pradesh"),
    "anna gowri medical college": ("Rajamahendravaram", "Andhra Pradesh"),
    "arunai medical college": ("Tiruvannamalai", "Tamil Nadu"),
    "balvir singh tomar institute": ("Jaipur", "Rajasthan"),
    "believers church medical college": ("Tiruvalla", "Kerala"),
    "bhagyoday medical college": ("Patan", "Gujarat"),
    "cu shah medical college": ("Surendranagar", "Gujarat"),
    "career institute of medical sciences": ("Lucknow", "Uttar Pradesh"),
    "cmr institute of medical sciences": ("Hyderabad", "Telangana"),
    "dr b s kushwah institute": ("Agra", "Uttar Pradesh"),
    "dr chandramma dayananda sagar": ("Harohalli", "Karnataka"),
    "gian sagar medical college": ("Banur", "Punjab"),
    "dr s s tantia medical college": ("Sri Ganganagar", "Rajasthan"),
    "dr n d desai faculty": ("Nadiad", "Gujarat"),
    "dr n y tasgaonkar institute": ("Karjat", "Maharashtra"),
    "dr somervell memorial": ("Thiruvananthapuram", "Kerala"),
    "dr kiran c patel medical college": ("Bharuch", "Gujarat"),
    "driems institute": ("Cuttack", "Odisha"),
    "east west institute of medical": ("Kolkata", "West Bengal"),
    "farookh academy": ("Mangaluru", "Karnataka"),
    "jagannath gupta institute": ("Kolkata", "West Bengal"),
    "jakir hossain medical college": ("Murshidabad", "West Bengal"),
    "kamineni academy": ("Hyderabad", "Telangana"),
    "karpagam faculty": ("Coimbatore", "Tamil Nadu"),
    "kempegowda institute": ("Bengaluru", "Karnataka"),
    "kmch institute of health sciences": ("Coimbatore", "Tamil Nadu"),
    "jjm medical college": ("Davanagere", "Karnataka"),
    "nk p salve": ("Nagpur", "Maharashtra"),
    "naraina medical college": ("Kanpur", "Uttar Pradesh"),
    "nimra institute of medical sciences": ("Vijayawada", "Andhra Pradesh"),
    "laxmi chandravansi medical college": ("Bishrampur", "Jharkhand"),
    "m s ramaiah medical college": ("Bengaluru", "Karnataka"),
    "mahabodhi medical college": ("Gaya", "Bihar"),
    "mahadevappa rampure medical college": ("Kalaburagi", "Karnataka"),
    "malanakara orthodox syrian church": ("Kochi", "Kerala"),
    "malati multispeciality": ("Amravati", "Maharashtra"),
    "mansarovar medical college": ("Bhopal", "Madhya Pradesh"),
    "matushri prabhaben": ("Morbi", "Gujarat"),
    "neelima institute of medical sciences": ("Hyderabad", "Telangana"),
    "nova institute of medical sciences": ("Hyderabad", "Telangana"),
    "pa sangma international medical": ("Shillong", "Meghalaya"),
    "pkg medical college": ("Barasat", "West Bengal"),
    "pramukhswami medical college": ("Anand", "Gujarat"),
    "maharishi markandeshwar medical college": ("Kumarhatti", "Himachal Pradesh"),
    "school of medical sciences sri satya sai": ("Sehore", "Madhya Pradesh"),
    "shyamlal chandrashekhar medical college": ("Sitamarhi", "Bihar"),
    "psp medical college": ("Chennai", "Tamil Nadu"),
    "panimalar medical college": ("Chennai", "Tamil Nadu"),
    "tripura medical college": ("Agartala", "Tripura"),
    "tripura santiniketan medical college": ("Agartala", "Tripura"),
    "radha devi jageshwari": ("Muzaffarpur", "Bihar"),
    "santiniketan medical college": ("Bolpur", "West Bengal"),
    "shija academy": ("Imphal", "Manipur"),
    "shree narayan medical institute": ("Saharsa", "Bihar"),
    "gorakshnath medical college": ("Gorakhpur", "Uttar Pradesh"),
    "sks hospital medical college": ("Mathura", "Uttar Pradesh"),
    "teerthanker mahaveer medical college": ("Moradabad", "Uttar Pradesh"),
    "smt sakhubai narayanrao katkade": ("Yeola", "Maharashtra"),
    "sri madhusudan sai institute": ("Chikkaballapur", "Karnataka"),
    "swamy vivekanandha medical college": ("Namakkal", "Tamil Nadu"),
    "viraat ramayan institute": ("Motihari", "Bihar"),
    "faculty of den sci": ("Lucknow", "Uttar Pradesh"),
    "government medical college mumbai": ("Mumbai", "Maharashtra"),
}

# JoSAA institute names often identify their campus by the institute, not by
# a city token. Keep these mappings explicit rather than guessing by state.
COLLEGE_LOCATION_OVERRIDES.update({
    "cu jharkhand": ("Ranchi", "Jharkhand"),
    "central university of haryana": ("Mahendragarh", "Haryana"),
    "central university of rajasthan": ("Ajmer", "Rajasthan"),
    "central institute of technology kokrajar": ("Kokrajhar", "Assam"),
    "indian institute of carpet technology": ("Bhadohi", "Uttar Pradesh"),
    "indian institute of engineering science and technology": ("Howrah", "West Bengal"),
    "islamic university of science and technology": ("Awantipora", "Jammu and Kashmir"),
    "national institute of electronics and information technology": ("Rupnagar", "Punjab"),
    "national institute of food technology entrepreneurship": ("Sonipat", "Haryana"),
    "north eastern regional institute of science and technology": ("Itanagar", "Arunachal Pradesh"),
    "sant longowal institute": ("Sangrur", "Punjab"),
    "iiit senapati": ("Senapati", "Manipur"),
    "indian institute of information technology senapati": ("Senapati", "Manipur"),
    "indian institute of information technology (iiit), sri city": ("Sri City", "Andhra Pradesh"),
    "indian institute of information technology, design manufacturing, kancheepuram": ("Chennai", "Tamil Nadu"),
    "indian institute of technology bombay": ("Mumbai", "Maharashtra"),
    "indian institute of technology goa": ("Ponda", "Goa"),
    "indian institute of technology kharagpur": ("Kharagpur", "West Bengal"),
    "indian institute of technology roorkee": ("Roorkee", "Uttarakhand"),
    "indian institute of technology ropar": ("Rupnagar", "Punjab"),
    "dr b r ambedkar national institute of technology": ("Jalandhar", "Punjab"),
    "national institute of technology arunachal pradesh": ("Yupia", "Arunachal Pradesh"),
    "national institute of technology goa": ("Ponda", "Goa"),
    "national institute of technology karnataka": ("Mangaluru", "Karnataka"),
    "national institute of technology meghalaya": ("Shillong", "Meghalaya"),
    "national institute of technology nagaland": ("Dimapur", "Nagaland"),
    "national institute of technology sikkim": ("Ravangla", "Sikkim"),
    "national institute of technology andhra pradesh": ("Tadepalligudem", "Andhra Pradesh"),
    "national institute of technology kurukshetra": ("Kurukshetra", "Haryana"),
    "national institute of technology manipur": ("Imphal", "Manipur"),
    "national institute of technology mizoram": ("Aizawl", "Mizoram"),
    "national institute of technology uttarakhand": ("Srinagar", "Uttarakhand"),
    "sri jagadguru murugharajendra university": ("Davanagere", "Karnataka"),
    "rathinam institute of technology": ("Bengaluru", "Karnataka"),
})

CITY_INDEX: dict[str, list[tuple[str, str]]] = {
    key: list(candidates) for key, candidates in CITY_STATE.items()
}
for alias, location in EXTRA_CITY_LOCATIONS.items():
    CITY_INDEX[normalize(alias)] = [location]
CITY_PATTERNS = [
    (re.compile(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"), alias, candidates)
    for alias, candidates in CITY_INDEX.items()
]
OVERRIDE_PATTERNS = sorted(
    ((normalize(name), location) for name, location in COLLEGE_LOCATION_OVERRIDES.items()),
    key=lambda item: len(item[0]),
    reverse=True,
)


def valid(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and not PLACEHOLDER.fullmatch(text)


def explicit_college_location(name: str, preferred_state: str | None) -> tuple[str, str] | None:
    normalized_name = normalize(name)
    for fragment, location in OVERRIDE_PATTERNS:
        if fragment and fragment in normalized_name and (
            not preferred_state or location[1].casefold() == preferred_state.casefold()
        ):
            return location
    return None


@lru_cache(maxsize=None)
def college_location(name: str, preferred_state: str | None) -> tuple[str | None, str | None]:
    normalized_name = normalize(name)
    override = explicit_college_location(name, preferred_state)
    if override:
        return override

    text = normalize(name)
    matches = []
    for pattern, alias, candidates in CITY_PATTERNS:
        match = pattern.search(text)
        if match:
            location = next(
                (candidate for candidate in candidates if preferred_state and candidate[1].casefold() == preferred_state.casefold()),
                candidates[0],
            )
            matches.append((match.end(), len(alias), location))
    if not matches:
        return None, preferred_state
    _, _, (city, inferred_state) = max(matches, key=lambda item: (item[0], item[1]))
    return city, preferred_state or inferred_state


DATASETS = (
    (ROOT / "data" / "josaa-cutoffs.json", ("records",)),
    (ROOT / "data" / "kcet-cutoffs.json", ("kea", "comedk")),
    (ROOT / "data" / "neet-cutoffs.json", ("records", "unmatchedHistoricalCutoffs")),
)
# These two source datasets are intentionally compact; NEET uses two-space JSON.
PRETTY_DATASETS = {"neet-cutoffs.json"}


def update_dataset(path: Path, sections: tuple[str, ...]) -> tuple[dict[str, Any], int]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    unresolved: list[str] = []
    for section in sections:
        for row in dataset.get(section, []):
            name = str(row.get("college") or row.get("sourceName") or "").strip()
            if not name:
                continue
            city = str(row.get("city") or "").strip() if valid(row.get("city")) else ""
            state = str(row.get("state") or row.get("collegeState") or "").strip()
            supporting_names = [
                row.get("sourceName"),
                *(row.get("aliases") or []),
                *(
                    cutoff.get("sourceCollege")
                    for cutoff in row.get("historicalCutoffs", [])
                    if isinstance(cutoff, dict)
                ),
            ]
            location_from_name = explicit_college_location(name, state or None)
            for candidate in [name, *(str(value).strip() for value in supporting_names if value)]:
                if location_from_name:
                    break
                city_from_name, state_from_name = college_location(candidate, state or None)
                if city_from_name:
                    location_from_name = (city_from_name, state_from_name)
                    break
            city_from_name, state_from_name = location_from_name or (None, state or None)
            if not city or explicit_college_location(name, state or None):
                city = city_from_name or ""
            if not valid(state):
                state = state_from_name or ""
            city_candidates = CITY_INDEX.get(normalize(city), [])
            city_states = {candidate_state for _, candidate_state in city_candidates}
            if state and state.casefold() not in {candidate.casefold() for candidate in city_states} and len(city_states) == 1:
                state = next(iter(city_states))
            if not valid(state) and path.name == "kcet-cutoffs.json":
                state = "Karnataka"
            if not city or not state:
                unresolved.append(name)
                continue

            location = f"{city}, {state}"
            if row.get("city") != city or row.get("state") != state or not valid(row.get("location")):
                row["city"] = city
                row["state"] = state
                row["location"] = location
                changed += 1
    if unresolved:
        preview = "\n".join(f"- {name}" for name in unresolved[:40])
        raise ValueError(f"{path.name}: could not resolve {len(unresolved)} college locations:\n{preview}")
    return dataset, changed


def main() -> None:
    pending = []
    total_changed = 0
    for path, sections in DATASETS:
        dataset, changed = update_dataset(path, sections)
        pending.append((path, dataset, changed))
        total_changed += changed

    for path, dataset, _ in pending:
        temporary = path.with_suffix(path.suffix + ".tmp")
        if path.name in PRETTY_DATASETS:
            serialized = json.dumps(dataset, ensure_ascii=False, indent=2) + "\n"
        else:
            serialized = json.dumps(dataset, ensure_ascii=False, separators=(",", ":")) + "\n"
        temporary.write_bytes(serialized.encode("utf-8"))
        temporary.replace(path)

    for path, _, changed in pending:
        print(f"{path.relative_to(ROOT)}: filled or corrected locations on {changed} rows")
    print(f"Location update complete: {total_changed} rows updated.")


if __name__ == "__main__":
    main()
