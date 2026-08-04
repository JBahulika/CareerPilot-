"""Location helpers for job search and filtering.

City names are normalized with aliases (Bangalore↔Bengaluru, Bombay↔Mumbai)
and optional state/country context so users can type a short city name without
the full “City, State, Country” string job boards show in dropdowns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from models.schemas import JobListing, UserProfile

_REMOTE_TERMS = (
    "remote",
    "anywhere",
    "work from home",
    "wfh",
    "distributed",
    "worldwide",
)

_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
_SPLIT_RE = re.compile(r"[,;/|]+")


@dataclass(frozen=True)
class _City:
    canonical: str
    aliases: frozenset[str]
    region: str = ""
    country: str = "india"
    region_aliases: frozenset[str] = frozenset()
    country_aliases: frozenset[str] = frozenset({"india", "in", "bharat"})


def _city(
    canonical: str,
    *aliases: str,
    region: str = "",
    country: str = "india",
    region_aliases: tuple[str, ...] = (),
    country_aliases: tuple[str, ...] = (),
) -> _City:
    alias_set = frozenset({canonical, *aliases})
    r_aliases = frozenset({region, *region_aliases}) - {""}
    c_aliases = (
        frozenset({"india", "in", "bharat", *country_aliases})
        if country == "india"
        else frozenset({country, *country_aliases}) - {""}
    )
    return _City(
        canonical=canonical,
        aliases=alias_set,
        region=region,
        country=country,
        region_aliases=r_aliases,
        country_aliases=c_aliases,
    )


# Metro catalog — short names expand to aliases + state/country for matching.
_CITIES: tuple[_City, ...] = (
    _city(
        "bengaluru",
        "bangalore",
        "blr",
        "bangalore urban",
        "bengaluru urban",
        region="karnataka",
        region_aliases=("ka",),
    ),
    _city(
        "mumbai",
        "bombay",
        "bom",
        region="maharashtra",
        region_aliases=("mh",),
    ),
    _city(
        "delhi",
        "new delhi",
        "ncr",
        "delhi ncr",
        "national capital region",
        region="delhi",
        region_aliases=("new delhi", "nct"),
    ),
    _city(
        "hyderabad",
        "hyd",
        region="telangana",
        region_aliases=("andhra pradesh", "ap"),  # historical listings
    ),
    _city("chennai", "madras", region="tamil nadu", region_aliases=("tn",)),
    _city("kolkata", "calcutta", region="west bengal", region_aliases=("wb",)),
    _city("pune", "poona", region="maharashtra", region_aliases=("mh",)),
    _city(
        "gurugram",
        "gurgaon",
        region="haryana",
        region_aliases=("hr", "ncr", "delhi ncr"),
    ),
    _city(
        "noida",
        "greater noida",
        region="uttar pradesh",
        region_aliases=("up", "ncr", "delhi ncr"),
    ),
    _city("jaipur", region="rajasthan"),
    _city("ahmedabad", "amdavad", region="gujarat", region_aliases=("gj",)),
    _city("kochi", "cochin", region="kerala", region_aliases=("kl",)),
    _city("thiruvananthapuram", "trivandrum", region="kerala"),
    _city("chandigarh", "mohali", region="chandigarh"),
    _city("indore", region="madhya pradesh", region_aliases=("mp",)),
    _city("lucknow", region="uttar pradesh", region_aliases=("up",)),
    _city("coimbatore", region="tamil nadu", region_aliases=("tn",)),
    _city("visakhapatnam", "vizag", region="andhra pradesh", region_aliases=("ap",)),
    _city(
        "san francisco",
        "sf",
        "bay area",
        region="california",
        country="united states",
        region_aliases=("ca", "california"),
        country_aliases=("usa", "us", "united states", "america"),
    ),
    _city(
        "new york",
        "nyc",
        "new york city",
        region="new york",
        country="united states",
        country_aliases=("usa", "us", "united states"),
    ),
    _city(
        "london",
        "greater london",
        region="england",
        country="united kingdom",
        country_aliases=("uk", "u.k", "britain", "great britain"),
    ),
    _city(
        "toronto",
        region="ontario",
        country="canada",
        country_aliases=("canada", "ca"),
    ),
    _city(
        "singapore",
        country="singapore",
        country_aliases=("singapore", "sg"),
    ),
)

# Alias token -> city (longest aliases matched first when scanning text).
_ALIAS_TO_CITY: dict[str, _City] = {}
for _c in _CITIES:
    for _a in _c.aliases:
        _ALIAS_TO_CITY[_a] = _c


def _normalize(text: str) -> str:
    return _NON_ALNUM_RE.sub(" ", (text or "").lower()).strip()


def _preference_parts(pref: str) -> list[str]:
    """Split 'Bangalore, Chennai' / 'Mumbai | Delhi' into city phrases."""
    raw = (pref or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in _SPLIT_RE.split(raw) if p.strip()]
    return parts or [raw]


def _cities_mentioned(text: str) -> list[_City]:
    """Find known cities referenced in free text (longest alias wins)."""
    norm = _normalize(text)
    if not norm:
        return []
    found: list[_City] = []
    seen: set[str] = set()
    # Longest alias first so "new delhi" beats "delhi", "greater noida" beats "noida"
    for alias in sorted(_ALIAS_TO_CITY.keys(), key=len, reverse=True):
        if alias not in norm:
            continue
        # Word-boundary-ish: alias as whole tokens
        pattern = rf"(^|\s){re.escape(alias)}(\s|$)"
        if not re.search(pattern, norm):
            continue
        city = _ALIAS_TO_CITY[alias]
        if city.canonical in seen:
            continue
        seen.add(city.canonical)
        found.append(city)
    return found


def resolve_cities(pref: str) -> list[_City]:
    """Resolve a user preference string into known cities (multi-city OK)."""
    cities: list[_City] = []
    seen: set[str] = set()
    for part in _preference_parts(pref):
        hit = _cities_mentioned(part)
        if hit:
            for c in hit:
                if c.canonical not in seen:
                    seen.add(c.canonical)
                    cities.append(c)
            continue
        # Exact alias key
        key = _normalize(part)
        city = _ALIAS_TO_CITY.get(key)
        if city and city.canonical not in seen:
            seen.add(city.canonical)
            cities.append(city)
    return cities


def format_geo_query(pref: str) -> str:
    """Canonical search string for scrapers (City, Region, Country)."""
    cities = resolve_cities(pref)
    if not cities:
        return (pref or "").strip()
    # Use first city; scrapers typically take one location param
    c = cities[0]
    parts = [c.canonical.title()]
    if c.region:
        parts.append(c.region.title())
    if c.country:
        parts.append(c.country.title())
    # Prefer common English spellings for search boxes
    display = {
        "bengaluru": "Bengaluru",
        "mumbai": "Mumbai",
        "delhi": "New Delhi",
        "gurugram": "Gurugram",
    }
    parts[0] = display.get(c.canonical, parts[0])
    return ", ".join(parts)


def preference_match_tokens(pref: str) -> set[str]:
    """Tokens that should count as a location hit for this preference."""
    tokens: set[str] = set()
    cities = resolve_cities(pref)
    for c in cities:
        tokens.update(c.aliases)
        tokens.update(c.region_aliases)
    if not cities:
        # Unknown city: still use raw normalized phrases
        for part in _preference_parts(pref):
            n = _normalize(part)
            if n:
                tokens.add(n)
                tokens.update(t for t in n.split() if len(t) > 2)
    return tokens


def effective_location(profile: UserProfile, override: str | None = None) -> str:
    """Run override -> preferred_location -> resume location."""
    if override and override.strip():
        return override.strip()
    if profile.preferred_location and profile.preferred_location.strip():
        return profile.preferred_location.strip()
    return (profile.location or "").strip()


def is_remote_location(text: str) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return False
    return any(term in normalized for term in _REMOTE_TERMS)


def locations_match(job_loc: str, pref: str) -> bool:
    """True when job location matches preferred city/aliases/region context."""
    job_n = _normalize(job_loc)
    pref_n = _normalize(pref)
    if not job_n or not pref_n:
        return False

    # Direct substring either way (handles "Bangalore" ⊂ "Bangalore, Karnataka")
    if pref_n in job_n or job_n in pref_n:
        return True

    pref_cities = resolve_cities(pref)
    job_cities = _cities_mentioned(job_loc)

    if pref_cities and job_cities:
        pref_ids = {c.canonical for c in pref_cities}
        if pref_ids & {c.canonical for c in job_cities}:
            return True

    # Alias / region tokens from preference appear in job string
    for token in preference_match_tokens(pref):
        if len(token) <= 2:
            continue
        if re.search(rf"(^|\s){re.escape(token)}(\s|$)", job_n):
            return True
        # Also allow compact forms without relying only on spaces
        if token in job_n and len(token) >= 4:
            return True

    # Preference names a city; job only has that city's state (e.g. Karnataka)
    if pref_cities:
        for c in pref_cities:
            for region in c.region_aliases:
                if region and re.search(rf"(^|\s){re.escape(region)}(\s|$)", job_n):
                    # Avoid matching bare country alone (too broad)
                    if region in c.country_aliases:
                        continue
                    return True

    return False


def location_filter_ok(
    job: JobListing,
    pref: str,
    *,
    include_remote: bool = True,
) -> bool:
    """Return True if job passes location preference."""
    pref = (pref or "").strip()
    if not pref:
        return True
    location = job.location or ""
    if include_remote and is_remote_location(location):
        return True
    if is_remote_location(location) and not include_remote:
        return False
    if not location.strip():
        return include_remote
    return locations_match(location, pref)
