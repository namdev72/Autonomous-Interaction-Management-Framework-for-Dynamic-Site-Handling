import json
import re
from typing import Optional

from loguru import logger

from agents.task_planner import TaskPlanner
from llm.llm_client import LLMClient
from models.task_models import TaskPlan
from sites.registry import SITE_POLICIES, policy_for, supports_comparison

TASK_TYPES = {"search", "compare", "extract", "book"}
CONSTRAINT_KEYS = {"minimum_rating", "maximum_price", "condition"}
# After this many answers, run with what is known rather than keep asking.
MAX_QUESTIONS = 3


MONTHS = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
          r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?")
# A travel date in the request or an answer: "23 October", "Oct 23", "23/10",
# "tomorrow", "next Friday".
DATE_GIVEN = re.compile(
    rf"\b(?:\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{MONTHS})\b|(?:{MONTHS})\s+\d{{1,2}}\b"
    r"|\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b|today|tonight|tomorrow"
    r"|(?:this|next)\s+(?:week|weekend|month|mon|tue|wed|thu|fri|sat|sun)\w*"
    r"|(?:mon|tues|wednes|thurs|fri|satur|sun)day)",
    re.IGNORECASE,
)


def _ask_for_missing_flight_date(plan: TaskPlan, query: str, answers: list[str]) -> TaskPlan:
    """
    A flight search without a date is asked for one, whichever planner made
    the plan. The LLM usually asks, but when its call failed, or it left the
    question out, the search ran without a date and Google Flights showed no
    one flight to report.
    """
    if plan.needs_clarification or "google_flights" not in plan.candidate_sites:
        return plan
    if DATE_GIVEN.search(" ".join([query, *answers])):
        return plan
    return plan.model_copy(update={
        "clarification_question": "What date do you want to fly? For a round trip, give the return date too.",
        "clarification_options": [],
    })


def _system_prompt() -> str:
    sites = "\n".join(
        f'- "{policy.key}": {policy.label} ({policy.country}, {", ".join(policy.capabilities)})'
        for policy in SITE_POLICIES.values()
    )
    return f"""
    You plan tasks for a browser agent that may only use these approved websites:
    {sites}

    Read the user's request, and their answers to earlier questions if any, and return ONLY JSON:
    {{
        "task_type": "search" | "compare" | "extract" | "book",
        "category": "product" | "flight" | "other",
        "sites": ["<approved site key>"],
        "unapproved_sites": ["<site the user named that is not listed>"],
        "search_query": "...",
        "constraints": {{"minimum_rating": "4.5", "maximum_price": "40000", "condition": "new"}},
        "missing": {{"question": "...", "options": ["..."]}} | null
    }}

    task_type: "compare" when the user wants prices compared or the cheapest/best among products;
    "extract" when they ask about something a list of search results (names, prices, ratings) does
    not answer, e.g. a product's specifications, how many variants are listed, or what a page says;
    "book" only when they want to book or reserve; otherwise "search".

    sites: keys of the approved sites the user named or clearly means; [] if they named none.
    Never include a site that is not listed above; put any site the user named that is not listed
    (e.g. "ebay") in unapproved_sites instead.

    search_query: the text to type into the site's search box.
    - Products: only the product, without site names, filler words or constraints, e.g. "iphone 16".
    - Flights: origin, destination, dates and trip type in words, keeping "cheapest" if asked,
      e.g. "cheapest flights from Pune to Goa on 5 Oct returning 9 Oct round trip".

    constraints: only what the user stated. minimum_rating as a number out of 5, maximum_price as
    digits only, condition only if they said new, used or refurbished. {{}} if none.

    missing: ONE question, only when the task cannot be done correctly without the answer:
    - Amazon named without a region (India or US): ask which region, options
      ["Amazon India (INR)", "Amazon US (USD)"].
    - A flight without a departure date: ask for the date, and the return date if it is a round trip.
    - A round trip without a return date: ask for the return date.
    Never ask about something the user already said, in the request or in an answer. Never ask about
    optional details (budget, rating, airline, class). Otherwise null.
    """


class LLMTaskPlanner:
    """
    Understands the request with the LLM, then checks the result against the
    site registry. The rule-based TaskPlanner stays as the fallback when the
    LLM fails or returns something unusable.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
        self.fallback = TaskPlanner()

    async def plan(self, query: str, answers: Optional[list[str]] = None) -> TaskPlan:
        answers = [answer for answer in (answers or []) if answer.strip()]
        user_prompt = f"Request: {query}"
        if answers:
            user_prompt += "\nAnswers to earlier questions:\n" + "\n".join(f"- {answer}" for answer in answers)
        try:
            response = await self.llm_client.generate_json(_system_prompt(), user_prompt)
            plan = self._validated(response, allow_question=len(answers) < MAX_QUESTIONS)
        except Exception as exc:
            logger.warning(f"LLM planner failed ({exc}); using the rule-based planner.")
            plan = None
        if plan is None:
            plan = self.fallback.plan(query, "\n".join(answers) or None)
        else:
            logger.info(f"LLM plan: {json.dumps(plan.model_dump(), ensure_ascii=False)}")
        if len(answers) < MAX_QUESTIONS:
            plan = _ask_for_missing_flight_date(plan, query, answers)
        return plan

    @staticmethod
    def _validated(response: dict, allow_question: bool = True) -> Optional[TaskPlan]:
        """The LLM's plan, restricted to what the registry allows; None if unusable."""
        if not isinstance(response, dict):
            return None
        search_query = response.get("search_query")
        if not isinstance(search_query, str) or not search_query.strip():
            return None
        task_type = response.get("task_type") if response.get("task_type") in TASK_TYPES else "search"
        category = response.get("category")

        # The registry, not the model, decides which sites exist.
        sites = [key for key in response.get("sites") or [] if isinstance(key, str) and key in SITE_POLICIES]
        sites = list(dict.fromkeys(sites))
        if "amazon_in" in sites and "amazon_us" in sites and task_type != "compare":
            sites = [key for key in sites if key != "amazon_us"]

        raw = response.get("constraints") if isinstance(response.get("constraints"), dict) else {}
        constraints = {key: str(value).strip() for key, value in raw.items()
                       if key in CONSTRAINT_KEYS and value not in (None, "")}
        if "maximum_price" in constraints:
            digits = "".join(char for char in constraints["maximum_price"] if char.isdigit())
            if digits:
                constraints["maximum_price"] = digits
            else:
                del constraints["maximum_price"]
        if "minimum_rating" in constraints:
            try:
                if not 0 < float(constraints["minimum_rating"]) <= 5:
                    constraints.pop("minimum_rating")
            except ValueError:
                constraints.pop("minimum_rating")

        # A site the user asked for that is not approved: say so and offer the
        # approved ones, rather than quietly searching somewhere else.
        unapproved = [name.strip() for name in response.get("unapproved_sites") or []
                      if isinstance(name, str) and name.strip()]
        if unapproved and not sites and allow_question:
            wanted = "flight_search" if category == "flight" else "product_search"
            options = [policy.label for policy in SITE_POLICIES.values() if wanted in policy.capabilities]
            return TaskPlan(
                task_type=task_type,
                subject=search_query.strip(),
                constraints=constraints,
                clarification_question=f"{', '.join(unapproved)} is not an approved site. Which approved site should I use?",
                clarification_options=options,
                planner="llm",
            )

        missing = response.get("missing") if allow_question else None
        if isinstance(missing, dict) and isinstance(missing.get("question"), str) and missing["question"].strip():
            options = [option.strip() for option in missing.get("options") or []
                       if isinstance(option, str) and option.strip()][:5]
            return TaskPlan(
                task_type=task_type,
                subject=search_query.strip(),
                candidate_sites=sites,
                constraints=constraints,
                clarification_question=missing["question"].strip(),
                clarification_options=options,
                planner="llm",
            )

        if not sites:
            if category == "flight":
                sites = [key for key, policy in SITE_POLICIES.items() if "flight_search" in policy.capabilities][:1]
            else:
                sites = ["amazon_in", "flipkart_in"] if task_type == "compare" else ["amazon_in"]
        # Comparisons read product cards, which only product sites have.
        if task_type == "compare" and not all(supports_comparison(policy_for(key)) for key in sites):
            task_type = "search"

        policy = policy_for(sites[0])
        return TaskPlan(
            task_type=task_type,
            subject=search_query.strip(),
            preferred_sites=sites,
            candidate_sites=sites,
            country=policy.country,
            currency=policy.currency or None,
            constraints=constraints,
            planner="llm",
        )
