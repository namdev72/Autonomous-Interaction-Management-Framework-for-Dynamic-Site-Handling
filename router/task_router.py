import re
from typing import Union
from loguru import logger
from models.task_models import TaskPlan
from models.strategy_models import DirectURLStrategy, RegistryStrategy, LLMStrategy
from router.query_normalizer import QueryNormalizer
from sites.registry import classify_sites, policy_for

# The user already said which kind of trip.
TRIP_TYPE_GIVEN = re.compile(r"\b(?:round[\s-]?trip|return(?:ing)?|one[\s-]?way)\b", re.IGNORECASE)


class TaskRouter:
    """Chooses how the agent starts: a direct search URL, a site's home page, or LLM-led."""

    def __init__(self):
        self.normalizer = QueryNormalizer()

    def route_task(self, user_query: str, plan: TaskPlan) -> Union[DirectURLStrategy, RegistryStrategy, LLMStrategy]:
        logger.info("[Agent] Understanding user request...")

        if plan.needs_clarification:
            return LLMStrategy(query=user_query)

        actual_sites = classify_sites(user_query)
        # A flight needs no site named: Google Flights is the only approved
        # flight site, so the planner's choice is the user's. Without this,
        # "find flights from Pune to Goa" started on the bare Google Flights
        # home page instead of its search. Other unnamed sites are planner
        # defaults (Amazon India for anything) and are not trusted.
        planned_flight = any("flight_search" in policy_for(key).capabilities for key in plan.preferred_sites)
        if not actual_sites and not planned_flight:
            logger.info("[Agent] No explicitly approved website detected in query. Falling back to LLM.")
            return LLMStrategy(query=user_query)

        if not plan.preferred_sites:
            logger.info("[Agent] No specific website detected in plan. Falling back to LLM.")
            return LLMStrategy(query=user_query)

        # Sites, their regions and their search URLs all come from the one
        # registry in sites/registry.py.
        policy = policy_for(plan.preferred_sites[0])
        website_key = policy.key.split("_")[0]  # "amazon", "flipkart", "google"
        logger.info(f"[Agent] Website detected: {policy.label}")

        search_query = self.normalizer.normalize_search_query(plan.subject, website_key)
        # Google Flights defaults to a round trip with dates it picks, so "the
        # cheapest flight" came back as a round-trip fare. Search one way unless
        # the user said which kind of trip.
        if search_query and "flight_search" in policy.capabilities and not TRIP_TYPE_GIVEN.search(f"{user_query} {search_query}"):
            search_query = f"{search_query} one way"

        if plan.task_type in ["search", "compare", "extract"] and search_query:
            logger.info(f"[Agent] {plan.task_type.title()} intent detected for query: '{search_query}'")
            direct_url = policy.build_search_url(search_query)
            logger.info("[Agent] Direct URL strategy available")
            logger.info(f"[Agent] Generated search URL: {direct_url}")
            return DirectURLStrategy(
                url=direct_url,
                website=website_key,
                source_locked=True
            )

        logger.info(f"[Agent] URL generation unavailable, starting from {policy.home_url}")
        return RegistryStrategy(
            config={"key": policy.key, "label": policy.label},
            domain=policy.home_url,
            website=website_key,
            source_locked=True
        )
