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


if __name__ == "__main__":
    unittest.main()
