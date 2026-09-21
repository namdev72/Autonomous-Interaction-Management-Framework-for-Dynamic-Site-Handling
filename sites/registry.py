from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import quote, urlsplit


@dataclass(frozen=True)
class SitePolicy:
    key: str
    label: str
    domains: tuple[str, ...]
    country: str
    currency: str
    capabilities: tuple[str, ...]
    # Search results URL with a {query} placeholder. Adding a site is a new
    # entry below; no code changes.
    search_url: str
    # Where to start a task that is not a search, when the domain root is the
    # wrong place (Google Flights is not google.com).
    home_path: str = ""

    def build_search_url(self, query: str) -> str:
        return self.search_url.replace("{query}", quote(query.strip(), safe=""))

    @property
    def home_url(self) -> str:
        parts = urlsplit(self.search_url)
        return f"{parts.scheme}://{parts.netloc}{self.home_path}"


# The single registry of approved sites: the task planner, the router, the
# comparison adapters and the navigation whitelist all read from here.
SITE_POLICIES: Dict[str, SitePolicy] = {
    "amazon_in": SitePolicy("amazon_in", "Amazon India", ("amazon.in", "www.amazon.in"), "IN", "INR", ("product_search", "price", "rating"),
                            "https://www.amazon.in/s?k={query}"),
    "amazon_us": SitePolicy("amazon_us", "Amazon US", ("amazon.com", "www.amazon.com"), "US", "USD", ("product_search", "price", "rating"),
                            "https://www.amazon.com/s?k={query}"),
    "flipkart_in": SitePolicy("flipkart_in", "Flipkart", ("flipkart.com", "www.flipkart.com"), "IN", "INR", ("product_search", "price", "rating"),
                              "https://www.flipkart.com/search?q={query}"),
    "google_flights": SitePolicy("google_flights", "Google Flights", ("google.com", "www.google.com"), "GLOBAL", "", ("flight_search", "price"),
                                 "https://www.google.com/travel/flights?q={query}", "/travel/flights"),
}

ALIASES = {
    "amazon india": "amazon_in",
    "amazon.in": "amazon_in",
    "amazon us": "amazon_us",
    "amazon.com": "amazon_us",
    "amazon": "amazon_in",
    "flipkart": "flipkart_in",
    "google flights": "google_flights",
    "google flight": "google_flights",
}


def allowed_hosts() -> set[str]:
    return {domain for policy in SITE_POLICIES.values() for domain in policy.domains}


def policy_for(key: str) -> SitePolicy:
    try:
        return SITE_POLICIES[key]
    except KeyError as exc:
        raise ValueError(f"Site is not whitelisted: {key}") from exc


def supports_comparison(policy: SitePolicy) -> bool:
    """Price comparison reads product result cards; see sites/adapters.py."""
    return "product_search" in policy.capabilities


def classify_sites(query: str) -> List[str]:
    lowered = query.lower()
    selected = []
    for alias, key in sorted(ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in lowered and key not in selected:
            selected.append(key)
    if "amazon_us" in selected:
        selected = [key for key in selected if key != "amazon_in"]
    return selected
