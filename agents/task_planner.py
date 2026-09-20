import re
from typing import Optional

from models.task_models import TaskPlan
from sites.registry import classify_sites, policy_for


class TaskPlanner:
    """Low-cost deterministic pre-planner for safe routing and clarification."""

    def plan(self, query: str, clarification: Optional[str] = None) -> TaskPlan:
        text = f"{query} {clarification or ''}".strip()
        lowered = text.lower()
        sites = classify_sites(text)
        is_compare = any(word in lowered for word in ("compare", "cheapest", "lowest price", "best price", "across"))
        is_flight = any(word in lowered for word in ("flight", "flights", "airfare", "ticket price"))
        task_type = "compare" if is_compare else ("book" if "book" in lowered else "search")
        if is_flight and not sites:
            return TaskPlan(
                task_type="book" if "book" in lowered else "search",
                subject=text,
                candidate_sites=["google_flights"],
                clarification_question="Which approved flight website do you prefer?",
                clarification_options=["Google Flights"],
            )

        if "amazon" in lowered and "amazon_in" in sites and "amazon_us" not in sites:
            if not any(token in lowered for token in ("india", ".in", "inr", "rupee", "us", ".com", "usd", "dollar")):
                return TaskPlan(
                    task_type=task_type,
                    subject=text,
                    candidate_sites=["amazon_in", "amazon_us"],
                    clarification_question="Which Amazon region should I use?",
                    clarification_options=["Amazon India (INR)", "Amazon US (USD)"],
                )

        if not sites:
            sites = ["amazon_in", "flipkart_in"] if is_compare and not is_flight else ["amazon_in"]

        country = policy_for(sites[0]).country
        currency = policy_for(sites[0]).currency or None
        return TaskPlan(
            task_type=task_type,
            subject=text,
            preferred_sites=sites,
            candidate_sites=sites,
            country=country,
            currency=currency,
            constraints=self._constraints(lowered),
        )

    @staticmethod
    def _constraints(query: str) -> dict[str, str]:
        constraints = {}
        rating = re.search(r"(?:at least|minimum|min)\s*(\d(?:\.\d)?)\s*star", query)
        if rating:
            constraints["minimum_rating"] = rating.group(1)
        if "new" in query:
            constraints["condition"] = "new"
        return constraints
