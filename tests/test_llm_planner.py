import unittest

from agents.llm_planner import MAX_QUESTIONS, LLMTaskPlanner


class FakeLLM:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.prompts = []

    async def generate_json(self, system_prompt, user_prompt):
        self.prompts.append(user_prompt)
        if self.error:
            raise self.error
        return self.response


def _plan(response, query="q", answers=None, error=None):
    llm = FakeLLM(response, error)
    planner = LLMTaskPlanner(llm)
    import asyncio
    return asyncio.run(planner.plan(query, answers)), llm


class LLMPlannerTests(unittest.TestCase):
    def test_product_comparison_is_taken_from_the_llm(self):
        plan, _ = _plan({
            "task_type": "compare", "category": "product", "sites": ["amazon_in", "flipkart_in"],
            "search_query": "iphone 16", "constraints": {"minimum_rating": "4.5", "maximum_price": "₹70,000"},
            "missing": None,
        })

        self.assertEqual(plan.planner, "llm")
        self.assertEqual(plan.task_type, "compare")
        self.assertEqual(plan.subject, "iphone 16")
        self.assertEqual(plan.preferred_sites, ["amazon_in", "flipkart_in"])
        self.assertEqual(plan.constraints, {"minimum_rating": "4.5", "maximum_price": "70000"})
        self.assertEqual(plan.currency, "INR")

    def test_sites_outside_the_registry_are_dropped(self):
        plan, _ = _plan({"task_type": "search", "category": "product", "sites": ["ebay", "amazon.evil"],
                         "search_query": "kettle", "missing": None})

        self.assertEqual(plan.preferred_sites, ["amazon_in"])

    def test_unapproved_site_is_named_and_approved_ones_offered(self):
        plan, _ = _plan({"task_type": "search", "category": "product", "sites": [], "unapproved_sites": ["eBay"],
                         "search_query": "iphone 16", "missing": None})

        self.assertEqual(plan.clarification_question, "eBay is not an approved site. Which approved site should I use?")
        self.assertEqual(plan.clarification_options, ["Amazon India", "Amazon US", "Flipkart"])

    def test_once_an_approved_site_is_chosen_it_runs(self):
        plan, _ = _plan({"task_type": "search", "category": "product", "sites": ["flipkart_in"], "unapproved_sites": ["eBay"],
                         "search_query": "iphone 16", "missing": None}, answers=["Flipkart"])

        self.assertFalse(plan.needs_clarification)
        self.assertEqual(plan.preferred_sites, ["flipkart_in"])

    def test_product_searches_go_to_the_extractors_and_questions_to_the_agent(self):
        from sites.adapters import reads_product_cards

        search, _ = _plan({"task_type": "search", "category": "product", "sites": ["flipkart_in"],
                           "search_query": "mechanical keyboard"})
        question, _ = _plan({"task_type": "extract", "category": "product", "sites": ["flipkart_in"],
                             "search_query": "oneplus 13"})
        flight, _ = _plan({"task_type": "search", "category": "flight", "sites": ["google_flights"],
                           "search_query": "flights from Delhi to Mumbai on 15 Oct one way"})

        self.assertTrue(reads_product_cards(search))
        self.assertEqual(question.task_type, "extract")
        self.assertFalse(reads_product_cards(question))
        self.assertFalse(reads_product_cards(flight))

    def test_invalid_constraints_are_dropped(self):
        plan, _ = _plan({"task_type": "search", "sites": ["flipkart_in"], "search_query": "kettle",
                         "constraints": {"minimum_rating": "9", "maximum_price": "cheap", "colour": "red"}})

        self.assertEqual(plan.constraints, {})

    def test_missing_information_becomes_a_question(self):
        plan, _ = _plan({
            "task_type": "search", "category": "flight", "sites": ["google_flights"],
            "search_query": "cheapest round trip flights from Delhi to Mumbai",
            "missing": {"question": "What are your departure and return dates?", "options": []},
        })

        self.assertTrue(plan.needs_clarification)
        self.assertEqual(plan.clarification_question, "What are your departure and return dates?")

    def test_answers_reach_the_llm_and_questions_stop_after_the_limit(self):
        answers = [f"answer {n}" for n in range(MAX_QUESTIONS)]
        plan, llm = _plan({"task_type": "search", "category": "flight", "sites": ["google_flights"],
                           "search_query": "flights from Delhi to Mumbai",
                           "missing": {"question": "Anything else?", "options": []}}, answers=answers)

        self.assertIn("- answer 0", llm.prompts[0])
        self.assertFalse(plan.needs_clarification)

    def test_flight_without_a_site_uses_the_flight_site_and_is_not_a_comparison(self):
        plan, _ = _plan({"task_type": "compare", "category": "flight", "sites": [],
                         "search_query": "cheapest flights from Delhi to Mumbai on 5 Oct", "missing": None})

        self.assertEqual(plan.preferred_sites, ["google_flights"])
        self.assertEqual(plan.task_type, "search")

    def test_unusable_reply_falls_back_to_the_rules(self):
        for response in ({}, {"task_type": "search"}, None, ["not", "a", "dict"]):
            with self.subTest(response=response):
                plan, _ = _plan(response, query="compare iphone 16 prices on amazon india")

                self.assertEqual(plan.planner, "rules")
                self.assertEqual(plan.preferred_sites, ["amazon_in"])

    def test_llm_error_falls_back_to_the_rules(self):
        plan, _ = _plan(None, query="compare iphone 16 prices on amazon", error=RuntimeError("rate limited"))

        self.assertEqual(plan.planner, "rules")
        self.assertEqual(plan.clarification_question, "Which Amazon region should I use?")


class FlightTripTypeTests(unittest.TestCase):
    def test_trip_type_in_the_search_text_is_not_overridden(self):
        from models.task_models import TaskPlan
        from router.task_router import TaskRouter

        plan = TaskPlan(task_type="search", subject="cheapest flights from Delhi to Mumbai on 5 Oct returning 9 Oct round trip",
                        preferred_sites=["google_flights"], candidate_sites=["google_flights"])
        url = TaskRouter().route_task("find the cheapest flight from Delhi to Mumbai on google flights", plan).url

        self.assertNotIn("one%20way", url)
        self.assertIn("round%20trip", url)

    def test_flight_starts_on_the_search_without_the_site_named(self):
        from models.strategy_models import DirectURLStrategy
        from models.task_models import TaskPlan
        from router.task_router import TaskRouter

        plan = TaskPlan(task_type="search", subject="flights from Pune to Goa on 23 Sep",
                        preferred_sites=["google_flights"], candidate_sites=["google_flights"])
        strategy = TaskRouter().route_task("find flights from Pune to Goa\nUser clarification: 23 Sep", plan)

        self.assertIsInstance(strategy, DirectURLStrategy)
        self.assertIn("/travel/flights?q=flights%20from%20Pune%20to%20Goa", strategy.url)



class FlightDateTests(unittest.TestCase):
    """A flight without a date is always asked for one, whatever the LLM did."""

    FLIGHT = {"task_type": "search", "category": "flight", "sites": ["google_flights"],
              "search_query": "flights from Delhi to Bangalore", "missing": None}

    def test_llm_plan_without_the_question_still_asks_for_the_date(self):
        plan, _ = _plan(dict(self.FLIGHT), query="Find flights from Delhi to Bangalore")

        self.assertIn("What date", plan.clarification_question)

    def test_failed_llm_call_still_asks_for_the_date(self):
        plan, _ = _plan(None, query="Find flights from Delhi to Bangalore on google flights",
                        error=RuntimeError("timed out"))

        self.assertEqual(plan.planner, "rules")
        self.assertIn("What date", plan.clarification_question)

    def test_a_date_in_the_request_or_an_answer_is_not_asked_again(self):
        for query, answers in (("Find flights from Delhi to Bangalore on 23 October", None),
                               ("Find flights from Delhi to Bangalore", ["Oct 23"]),
                               ("Find flights from Delhi to Bangalore tomorrow", None)):
            with self.subTest(query=query, answers=answers):
                plan, _ = _plan(dict(self.FLIGHT), query=query, answers=answers)
                self.assertFalse(plan.needs_clarification)

    def test_products_are_not_asked_for_a_date(self):
        plan, _ = _plan({"task_type": "search", "category": "product", "sites": ["flipkart_in"],
                         "search_query": "kettle"}, query="search kettle on flipkart")

        self.assertFalse(plan.needs_clarification)


if __name__ == "__main__":
    unittest.main()
