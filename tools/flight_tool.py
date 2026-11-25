"""Airport resolution and AviationStack flight-status search utilities."""

import os
import re
from functools import lru_cache

import airportsdata
import certifi
import pycountry
import requests
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

API_KEY = os.getenv("AVIATIONSTACK_API_KEY")

# Default origin when user says only destination, e.g. "Japan trip"
# Change this if your default location is not Bangladesh/Dhaka.
DEFAULT_ORIGIN_IATA = os.getenv("DEFAULT_ORIGIN_IATA", "BLR")


BASE_URL = "https://api.aviationstack.com/v1/flights"


AIRPORTS = airportsdata.load("IATA")



COUNTRY_ALIASES = {
    "usa": "US",
    "u.s.a": "US",
    "u.s.": "US",
    "america": "US",
    "united states": "US",
    "uk": "GB",
    "u.k.": "GB",
    "britain": "GB",
    "england": "GB",
    "uae": "AE",
    "dubai": "AE",
    "south korea": "KR",
    "korea": "KR",
    "russia": "RU",
    "vietnam": "VN",
    "bangladesh": "BD",
    "india": "IN",
    "japan": "JP",
    "china": "CN",
    "singapore": "SG",
    "malaysia": "MY",
    "thailand": "TH",
    "indonesia": "ID",
    "nepal": "NP",
    "qatar": "QA",
    "saudi arabia": "SA",
    "turkey": "TR",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
}


# Preferred main airport for country-level search
COUNTRY_MAIN_AIRPORT = {
    "BD": "DAC",
    "IN": "DEL",
    "JP": "NRT",
    "US": "JFK",
    "GB": "LHR",
    "AE": "DXB",
    "SG": "SIN",
    "MY": "KUL",
    "TH": "BKK",
    "ID": "CGK",
    "CN": "PEK",
    "KR": "ICN",
    "NP": "KTM",
    "QA": "DOH",
    "SA": "JED",
    "TR": "IST",
    "CA": "YYZ",
    "AU": "SYD",
    "DE": "FRA",
    "FR": "CDG",
    "IT": "FCO",
    "ES": "MAD",
}




CITY_MAIN_AIRPORT = {
    "dhaka": "DAC",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "kolkata": "CCU",
    "chennai": "MAA",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "tokyo": "NRT",
    "osaka": "KIX",
    "kyoto": "KIX",
    "new york": "JFK",
    "london": "LHR",
    "dubai": "DXB",
    "singapore": "SIN",
    "kuala lumpur": "KUL",
    "bangkok": "BKK",
    "doha": "DOH",
    "istanbul": "IST",
    "toronto": "YYZ",
    "sydney": "SYD",
    "paris": "CDG",
    "rome": "FCO",
    "madrid": "MAD",
    "frankfurt": "FRA",
}

STOP_WORDS = frozenset({
    "flight", "flights", "ticket", "tickets", "trip", "travel",
    "plan", "complete", "days", "day", "including", "hotel",
    "hotels", "sightseeing", "under", "budget", "info", "information",
})
NON_ALPHANUMERIC_PATTERN = re.compile(r"[^a-z0-9\s]")
WHITESPACE_PATTERN = re.compile(r"\s+")
COUNTRY_ALIAS_PATTERNS = tuple(
    (alias, re.compile(rf"\b{re.escape(alias)}\b"))
    for alias in COUNTRY_ALIASES
)
COUNTRY_NAME_CODES = tuple(
    (country.name.lower(), country.alpha_2)
    for country in pycountry.countries
)
COUNTRY_NAME_PATTERNS = tuple(
    (name, re.compile(rf"\b{re.escape(name)}\b"))
    for name, _ in COUNTRY_NAME_CODES
)
CITY_PATTERNS = tuple(
    (city, re.compile(rf"\b{re.escape(city)}\b"))
    for city in CITY_MAIN_AIRPORT
)


def clean_text(text: str) -> str:
    """Normalize a location phrase and remove common travel-query filler.

    Punctuation becomes whitespace, repeated spaces are collapsed, and
    configured stop words are removed so the result can be compared with
    airport, city, and country names.

    Args:
        text: Free-form query fragment or location name.

    Returns:
        Lowercase, whitespace-normalized text without known stop words.
    """
    text = text.lower().strip()
    text = NON_ALPHANUMERIC_PATTERN.sub(" ", text)
    text = WHITESPACE_PATTERN.sub(" ", text)
    words = [word for word in text.split() if word not in STOP_WORDS]
    return " ".join(words).strip()



@lru_cache(maxsize=512)
def country_name_to_code(text: str):
    """Resolve a country name, alias, or longer phrase to its ISO alpha-2 code.

    Exact lookup is preferred; substring matching handles country names embedded
    in a larger location phrase. Results are cached because country data is
    static for the lifetime of the process.

    Args:
        text: Country name, known alias, or phrase containing one.

    Returns:
        The two-letter country code, or ``None`` if no country is recognized.
    """
    text = clean_text(text)

    if text in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[text]

    try:
        country = pycountry.countries.lookup(text)
        return country.alpha_2
    except LookupError:
        pass

    # Detect country name inside longer text
    for country_name, code in COUNTRY_NAME_CODES:
        if country_name in text:
            return code

    for alias, code in COUNTRY_ALIASES.items():
        if alias in text:
            return code

    return None



def airport_country_matches(airport: dict, country_code: str, country_name=None) -> bool:
    """Check whether an airport record belongs to a country.

    Airport datasets may store either an ISO country code or a country name.
    Supplying ``country_name`` avoids repeating the country lookup while
    scanning many records.

    Args:
        airport: Airport record from the IATA airport dataset.
        country_code: ISO alpha-2 country code to match.
        country_name: Optional lowercase country name for comparison.

    Returns:
        ``True`` when the record's country matches either representation.
    """
    airport_country = str(airport.get("country", "")).upper().strip()

    if airport_country == country_code:
        return True

    if country_name is None:
        country = pycountry.countries.get(alpha_2=country_code)
        country_name = country.name.lower() if country else ""

    return bool(country_name) and airport_country.lower() == country_name




@lru_cache(maxsize=256)
def get_best_airport_for_country(country_code: str):
    """Select the configured preferred airport or best-scoring country airport.

    Preferred airports take precedence. Otherwise international-airport and
    city metadata are scored to select a suitable fallback. The result is
    cached because airport and country datasets do not change at runtime.

    Args:
        country_code: ISO alpha-2 code of the destination country.

    Returns:
        The selected IATA code, or ``None`` if the country has no known airport.
    """
    preferred = COUNTRY_MAIN_AIRPORT.get(country_code)

    if preferred and preferred in AIRPORTS:
        return preferred

    country = pycountry.countries.get(alpha_2=country_code)
    country_name = country.name.lower() if country else ""
    candidates = []

    for iata, airport in AIRPORTS.items():
        if not iata:
            continue

        if airport_country_matches(airport, country_code, country_name):
            name = str(airport.get("name", "")).lower()
            city = str(airport.get("city", "")).lower()

            score = 0

            if "international" in name:
                score += 50
            if "intl" in name:
                score += 40
            if "capital" in name:
                score += 20
            if city:
                score += 5

            candidates.append((score, iata))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]




@lru_cache(maxsize=512)
def resolve_location_to_iata(location: str):
    """
    Resolve a country, city, airport name, or IATA code to an airport code.

    Resolution tries a direct IATA code, configured city and country
    preferences, and finally a scored search over the airport dataset. Results
    are cached to avoid repeating the dataset scan for common locations.

    Args:
        location: A free-form location name or three-letter IATA code.

    Returns:
        The matching IATA code, or ``None`` when the location is unknown.

    Examples:
        ``resolve_location_to_iata("Bangladesh")`` returns ``"DAC"``.
        ``resolve_location_to_iata("Tokyo")`` returns ``"NRT"``.
    """

    if not location:
        return None

    raw_location = location.strip()

    # Direct IATA code
    if re.fullmatch(r"[A-Za-z]{3}", raw_location):
        code = raw_location.upper()
        if code in AIRPORTS:
            return code

    location_clean = clean_text(raw_location)

    if not location_clean:
        return None

    # City preferred airport
    if location_clean in CITY_MAIN_AIRPORT:
        return CITY_MAIN_AIRPORT[location_clean]

    # Country preferred airport
    country_code = country_name_to_code(location_clean)
    if country_code:
        airport = get_best_airport_for_country(country_code)
        if airport:
            return airport

    # Exact city match from airport database
    city_matches = []

    for iata, airport in AIRPORTS.items():
        city = str(airport.get("city", "")).lower().strip()
        name = str(airport.get("name", "")).lower().strip()

        score = 0

        if city == location_clean:
            score += 100
        elif location_clean in city:
            score += 70

        if location_clean in name:
            score += 50

        if "international" in name:
            score += 10

        if score > 0:
            city_matches.append((score, iata))

    if city_matches:
        city_matches.sort(reverse=True)
        return city_matches[0][1]

    return None




def find_location_mentions(query: str):
    """
    Find known country aliases, country names, and configured city names.

    Matching patterns are compiled once at module import. Results preserve the
    existing category priority (aliases, countries, then cities) and remove
    duplicate mentions without changing their order.

    Args:
        query: Natural-language flight or travel request.

    Returns:
        Unique recognized location strings in priority order.
    """

    q = query.lower()
    mentions = []

    # Keep the existing alias, country, and city priority while reusing compiled patterns.
    for alias, pattern in COUNTRY_ALIAS_PATTERNS:
        if pattern.search(q):
            mentions.append(alias)

    for name, pattern in COUNTRY_NAME_PATTERNS:
        if len(name) >= 4 and pattern.search(q):
            mentions.append(name)

    for city, pattern in CITY_PATTERNS:
        if pattern.search(q):
            mentions.append(city)

    # Remove duplicate while keeping order
    unique_mentions = []
    seen = set()
    for item in mentions:
        if item not in seen:
            unique_mentions.append(item)
            seen.add(item)

    return unique_mentions


def parse_route(query: str):
    """
    Extract an optional departure and arrival IATA code from a query.

    Handles global-flight phrases, explicit IATA routes, ``from X to Y`` and
    ``to Y from X`` wording, one-sided origin/destination searches, and finally
    location mentions as a fallback.

    Args:
        query: User request containing a route, location, or global search.

    Returns:
        A pair ``(departure_iata, arrival_iata)``. Either value may be ``None``;
        both are ``None`` for an unfiltered global-flight query.
    """

    q = query.strip()
    q_lower = q.lower()

    # Global / all-country query
    global_keywords = [
        "all country",
        "all countries",
        "global flight",
        "global flights",
        "all flight",
        "all flights",
        "worldwide flight",
        "worldwide flights",
    ]

    if any(keyword in q_lower for keyword in global_keywords):
        return None, None

    # Direct IATA code route: DAC to NRT
    codes = re.findall(r"\b[A-Z]{3}\b", q)

    if len(codes) >= 2:
        dep = codes[0].upper()
        arr = codes[1].upper()
        return dep, arr

    # Pattern: from X to Y
    match = re.search(
        r"\bfrom\s+(.+?)\s+\bto\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower,
    )

    if match:
        origin_text = match.group(1)
        dest_text = match.group(2)

        dep_iata = resolve_location_to_iata(origin_text)
        arr_iata = resolve_location_to_iata(dest_text)

        return dep_iata, arr_iata

    # Pattern: to Y from X
    match = re.search(
        r"\bto\s+(.+?)\s+\bfrom\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower,
    )

    if match:
        dest_text = match.group(1)
        origin_text = match.group(2)

        dep_iata = resolve_location_to_iata(origin_text)
        arr_iata = resolve_location_to_iata(dest_text)

        return dep_iata, arr_iata

    # Pattern: flights from X
    match = re.search(r"\bfrom\s+(.+?)(?:[.!?]|$)", q_lower)

    if match:
        origin_text = match.group(1)
        dep_iata = resolve_location_to_iata(origin_text)
        return dep_iata, None

    # Pattern: flights to X
    match = re.search(r"\bto\s+(.+?)(?:[.!?]|$)", q_lower)

    if match:
        dest_text = match.group(1)
        arr_iata = resolve_location_to_iata(dest_text)
        return None, arr_iata

    # Fallback: find country/city mentions
    mentions = find_location_mentions(q)

    if len(mentions) >= 2:
        dep_iata = resolve_location_to_iata(mentions[0])
        arr_iata = resolve_location_to_iata(mentions[1])
        return dep_iata, arr_iata

    if len(mentions) == 1:
        arr_iata = resolve_location_to_iata(mentions[0])
        return DEFAULT_ORIGIN_IATA, arr_iata

    return None, None


def format_flight(flight: dict):
    """Render one AviationStack flight record as readable departure/arrival text.

    Missing fields are replaced with clear placeholders so partial API records
    can still be presented without failing the whole search.

    Args:
        flight: One flight object returned in AviationStack's ``data`` list.

    Returns:
        A multiline string containing airline, status, departure, and arrival
        details.
    """
    airline = (flight.get("airline") or {}).get("name") or "Unknown airline"
    flight_number = (flight.get("flight") or {}).get("iata") or "Unknown flight number"
    status = flight.get("flight_status") or "Unknown"

    dep = flight.get("departure", {}) or {}
    arr = flight.get("arrival", {}) or {}

    dep_airport = dep.get("airport") or "Unknown departure airport"
    dep_iata = dep.get("iata") or "Unknown"
    dep_terminal = dep.get("terminal") or "N/A"
    dep_gate = dep.get("gate") or "N/A"
    dep_scheduled = dep.get("scheduled") or "Unknown"
    dep_delay = dep.get("delay")
    dep_delay_text = f"{dep_delay} minutes" if dep_delay is not None else "N/A"

    arr_airport = arr.get("airport") or "Unknown arrival airport"
    arr_iata = arr.get("iata") or "Unknown"
    arr_terminal = arr.get("terminal") or "N/A"
    arr_gate = arr.get("gate") or "N/A"
    arr_scheduled = arr.get("scheduled") or "Unknown"
    arr_delay = arr.get("delay")
    arr_delay_text = f"{arr_delay} minutes" if arr_delay is not None else "N/A"

    return f"""
Airline: {airline}
Flight: {flight_number}
Status: {status}

Departure:
- Airport: {dep_airport}
- IATA: {dep_iata}
- Terminal: {dep_terminal}
- Gate: {dep_gate}
- Scheduled: {dep_scheduled}
- Delay: {dep_delay_text}

Arrival:
- Airport: {arr_airport}
- IATA: {arr_iata}
- Terminal: {arr_terminal}
- Gate: {arr_gate}
- Scheduled: {arr_scheduled}
- Delay: {arr_delay_text}
""".strip()


def search_flights(query: str, limit: int = 10):
    """Search AviationStack and format the matching live flight-status records.

    The route is extracted from ``query`` and translated into API filters. The
    API limit is capped at 100. Missing credentials and provider/data errors are
    returned as explanatory text; an invalid local ``limit`` raises ``ValueError``.

    Args:
        query: Natural-language request used to infer route filters.
        limit: Maximum number of returned records; must be a positive integer.

    Returns:
        A formatted result or an explanatory message when flight data is
        unavailable.

    Raises:
        ValueError: If ``limit`` is not a positive integer.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer.")

    if not API_KEY:
        return (
            "Flight API error: AVIATIONSTACK_API_KEY is missing.\n"
            "Please add this in your .env file:\n"
            "AVIATIONSTACK_API_KEY=your_api_key_here"
        )

    dep_iata, arr_iata = parse_route(query)

    params = {
        "access_key": API_KEY,
        "limit": min(limit, 100),
    }

    if dep_iata:
        params["dep_iata"] = dep_iata

    if arr_iata:
        params["arr_iata"] = arr_iata

    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        data = response.json()
    except requests.exceptions.RequestException as e:
        return f"Flight API request failed: {e}"
    except ValueError:
        return "Flight API returned invalid JSON."

    if "error" in data:
        error = data["error"]
        return (
            "Flight API error:\n"
            f"Code: {error.get('code', 'Unknown')}\n"
            f"Message: {error.get('message', 'Unknown error')}"
        )

    flight_data = data.get("data") or []
    if not isinstance(flight_data, list):
        return "Flight API returned invalid flight data."

    if not flight_data:
        route_text = ""

        if dep_iata and arr_iata:
            route_text = f" for route {dep_iata} to {arr_iata}"
        elif dep_iata:
            route_text = f" from {dep_iata}"
        elif arr_iata:
            route_text = f" to {arr_iata}"

        return (
            f"No live flight data found{route_text}.\n\n"
            "Note: AviationStack provides live/status flight data, not ticket prices. "
            "For actual fare prices, use a flight-pricing API such as Amadeus."
        )

    route_info = "Global live flights"

    if dep_iata and arr_iata:
        route_info = f"Live flights from {dep_iata} to {arr_iata}"
    elif dep_iata:
        route_info = f"Live flights from {dep_iata}"
    elif arr_iata:
        route_info = f"Live flights to {arr_iata}"

    formatted_flights = [format_flight(flight) for flight in flight_data[:limit]]

    return f"{route_info}\n\n" + "\n\n---\n\n".join(formatted_flights)


if __name__ == "__main__":
    # print(search_flights("Plan a 7 days Srilanka trip from Bangalore"))
    # print(search_flights("Plan a 3 days Goa trip from Bangalore"))
    pass