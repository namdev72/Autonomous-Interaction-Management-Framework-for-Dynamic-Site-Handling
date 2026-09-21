import re
from typing import Optional

from models.task_models import TaskPlan
from sites.registry import classify_sites, policy_for

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
                subject=self._subject(text, task_type),
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
                    subject=self._subject(text, task_type),
                    candidate_sites=["amazon_in", "amazon_us"],
                    constraints=self._constraints(lowered),
                    clarification_question="Which Amazon region should I use?",
                    clarification_options=["Amazon India (INR)", "Amazon US (USD)"],
                )

        if not sites:
            sites = ["amazon_in", "flipkart_in"] if is_compare and not is_flight else ["amazon_in"]

        country = policy_for(sites[0]).country
        currency = policy_for(sites[0]).currency or None
        return TaskPlan(
            task_type=task_type,
            subject=self._subject(text, task_type),
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
    def _subject(query: str, task_type: str) -> str:
        """Reduce conversational wording to the product or route being searched."""
        text = query.split("\nUser clarification:", 1)[0].strip()
        text = re.sub(r"^open\s+(?:chrome|browser)\s+and\s+", "", text, flags=re.IGNORECASE)
        if task_type == "compare":
            match = re.search(r"compare\s+(.+?)(?:\s+prices?|\s+on\s+|\s+with\s+my\s+budget|$)", text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        match = re.search(r"search\s+(?:for\s+)?(.+?)(?:\s+on\s+|$)", text, re.IGNORECASE)
        return match.group(1).strip() if match else text

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
