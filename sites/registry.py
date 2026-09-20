from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import quote_plus


@dataclass(frozen=True)
class SitePolicy:
    key: str
    label: str
    domains: tuple[str, ...]
    country: str
    currency: str
    capabilities: tuple[str, ...]

    def build_search_url(self, query: str) -> str:
        encoded = quote_plus(query.strip())
        if self.key == "amazon_in":
            return f"https://www.amazon.in/s?k={encoded}"
        if self.key == "amazon_us":
            return f"https://www.amazon.com/s?k={encoded}"
        if self.key == "flipkart_in":
            return f"https://www.flipkart.com/search?q={encoded}"
        if self.key == "google_flights":
            return f"https://www.google.com/travel/flights?q={encoded}"
        raise ValueError(f"No deterministic search URL for approved site: {self.key}")


SITE_POLICIES: Dict[str, SitePolicy] = {
    "amazon_in": SitePolicy("amazon_in", "Amazon India", ("amazon.in", "www.amazon.in"), "IN", "INR", ("product_search", "price", "rating")),
    "amazon_us": SitePolicy("amazon_us", "Amazon US", ("amazon.com", "www.amazon.com"), "US", "USD", ("product_search", "price", "rating")),
    "flipkart_in": SitePolicy("flipkart_in", "Flipkart", ("flipkart.com", "www.flipkart.com"), "IN", "INR", ("product_search", "price", "rating")),
    "google_flights": SitePolicy("google_flights", "Google Flights", ("google.com", "www.google.com"), "GLOBAL", "", ("flight_search", "price")),
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


def classify_sites(query: str) -> List[str]:
    lowered = query.lower()
    selected = []
    for alias, key in sorted(ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in lowered and key not in selected:
            selected.append(key)
    if "amazon_us" in selected:
        selected = [key for key in selected if key != "amazon_in"]
    return selected
