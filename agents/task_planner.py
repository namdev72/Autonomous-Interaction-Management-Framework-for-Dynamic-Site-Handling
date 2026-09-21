import re
from typing import Optional

from models.task_models import TaskPlan
from sites.registry import classify_sites, policy_for, supports_comparison

# Region hints for a plain "amazon". Matched as whole words: as substrings,
# "us" matched "mouse" and "business" and skipped the region question.
INDIA_HINTS = ("india", "indian", "inr", "rupee", "rupees")
US_HINTS = ("usa", "u.s.", "united states", "america", "american", "usd", "dollar", "dollars")


def _has_word(text: str, words) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) for word in words)


class TaskPlanner:
    """Low-cost deterministic pre-planner for safe routing and clarification."""

    def plan(self, query: str, clarification: Optional[str] = None) -> TaskPlan:
        text = f"{query} {clarification or ''}".strip()
        lowered = text.lower()
        sites = classify_sites(text)
        is_compare = _has_word(lowered, ("compare", "cheapest", "lowest price", "best price", "across"))
        is_flight = _has_word(lowered, ("flight", "flights", "airfare", "ticket price"))
        # Whole words, so "macbook" and "notebook" are not bookings.
        is_booking = _has_word(lowered, ("book", "booking", "reserve"))
        task_type = "compare" if is_compare else ("book" if is_booking else "search")
        if is_flight and not sites:
            return TaskPlan(
                task_type="book" if is_booking else "search",
                subject=self._subject(text, is_flight, sites),
                candidate_sites=["google_flights"],
                constraints=self._constraints(lowered),
                clarification_question="Which approved flight website do you prefer?",
                clarification_options=["Google Flights"],
            )

        if "amazon_in" in sites and "amazon_us" not in sites and not _has_word(lowered, ("amazon india", "amazon.in")):
            region = self._amazon_region(query, clarification)
            if region == "amazon_us":
                sites = ["amazon_us" if key == "amazon_in" else key for key in sites]
            elif region is None:
                return TaskPlan(
                    task_type=task_type,
                    subject=self._subject(text, is_flight, sites),
                    candidate_sites=["amazon_in", "amazon_us"],
                    constraints=self._constraints(lowered),
                    clarification_question="Which Amazon region should I use?",
                    clarification_options=["Amazon India (INR)", "Amazon US (USD)"],
                )

        if not sites:
            sites = ["amazon_in", "flipkart_in"] if is_compare and not is_flight else ["amazon_in"]

        # Comparisons read product cards, which only product sites have. Other
        # sites (Google Flights) go to the browsing agent instead, which can
        # use them, rather than a comparison that finds nothing.
        if task_type == "compare" and not all(supports_comparison(policy_for(key)) for key in sites):
            task_type = "search"

        country = policy_for(sites[0]).country
        currency = policy_for(sites[0]).currency or None
        return TaskPlan(
            task_type=task_type,
            subject=self._subject(text, is_flight, sites),
            preferred_sites=sites,
            candidate_sites=sites,
            country=country,
            currency=currency,
            constraints=self._constraints(lowered),
        )

    @staticmethod
    def _amazon_region(query: str, clarification: Optional[str]) -> Optional[str]:
        """Region for a plain "amazon", or None when it is unclear and must be asked."""
        text = f"{query} {clarification or ''}".lower()
        # "us" is also a pronoun ("help us find"), so in the query only
        # capitalised "US" counts; a clarification answer is just the region.
        says_us = _has_word(text, US_HINTS) or "$" in text or re.search(r"\bUS\b", query) is not None
        if clarification and re.fullmatch(r"\s*us\s*", clarification, re.IGNORECASE):
            says_us = True
        says_india = _has_word(text, INDIA_HINTS) or "₹" in text
        if says_india == says_us:
            return None
        return "amazon_in" if says_india else "amazon_us"

    @staticmethod
    def _subject(query: str, is_flight: bool = False, sites: Optional[list[str]] = None) -> str:
        """
        Reduce conversational wording to the product or route being searched:
        "compare the price of iphone 16 across amazon india and flipkart" is a
        search for "iphone 16", not for the whole sentence.
        """
        text = query.split("\nUser clarification:", 1)[0].strip()
        text = re.sub(r"^open\s+(?:chrome|browser)\s+and\s+", "", text, flags=re.IGNORECASE)
        lead = re.match(
            r"(?:compare|search(?:\s+for)?|find|look\s+for|show(?:\s+me)?|get)\s+(?:the\s+)?(?:prices?\s+(?:of|for)\s+)?",
            text, re.IGNORECASE,
        )
        if not lead:
            return text
        subject = text[lead.end():]
        if not is_flight:
            # A product search for "cheapest iphone 16" is a search for the
            # phone. Flights keep it: in Google Flights' query it sorts by price.
            subject = re.sub(r"^(?:cheapest|lowest[\s-]priced?|best[\s-]priced?)\s+", "", subject, flags=re.IGNORECASE)
        # The product ends where the sites or constraints begin.
        subject = re.split(r"\s+(?:prices?|on|across|between|with|under|below|within)\b", subject, maxsplit=1, flags=re.IGNORECASE)[0]

        # A query can name Amazon both as a routing hint and as the
        # destination, e.g. "search for amazon galaxy note 7 on amazon".
        # The routing hint must not become part of the product query.
        if sites and any(site.startswith("amazon_") for site in sites):
            subject = re.sub(r"^amazon\s+", "", subject, count=1, flags=re.IGNORECASE)
        return subject.strip(" ,.") or text

    @staticmethod
    def _constraints(query: str) -> dict[str, str]:
        constraints = {}
        rating = re.search(r"(?:at least|minimum|min)\s*(\d(?:\.\d)?)\s*star", query)
        if rating:
            constraints["minimum_rating"] = rating.group(1)
        budget = re.search(r"budget(?:\s+being|\s+is|\s+of|\s*=)?\s*(?:₹|rs\.?|inr)?\s*([\d,]+)", query)
        if budget:
            constraints["maximum_price"] = budget.group(1).replace(",", "")
        if _has_word(query, ("new", "brand new")):
            constraints["condition"] = "new"
        return constraints
