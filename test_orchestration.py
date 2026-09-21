import shutil
import tempfile
import unittest
from unittest.mock import patch

from agents.answer_composer import compose_comparison_answer
from agents.goal_verifier import GoalVerifier
from agents.recovery_policy import RecoveryPolicy
from agents.step_verifier import StepVerifier
from browser.actions import BrowserExecutor
from context.context_builder import ContextBuilder
from llm.llm_client import DEFAULT_MODEL, LLMClient
from memory.graph import NavigationGraph
from memory.history import MemoryState
from agents.task_planner import TaskPlanner
from memory.signature import (
    descriptor_for_target, element_descriptor, normalize_url, page_key,
    target_for_descriptor, view_signature,
)
from models.action_models import AgentAction
from models.orchestration_models import ActionResult


class FakeMouse:
    def __init__(self):
        self.wheel_calls = []

    async def wheel(self, x, y):
        self.wheel_calls.append((x, y))


class FakePage:
    def __init__(self):
        self.url = "https://example.com"
        self.mouse = FakeMouse()
        self.frames = []


class FakeLLMClient:
    def __init__(self, response):
        self.response = response

    async def generate_json(self, system_prompt, user_prompt):
        return self.response


class LLMClientConfigurationTests(unittest.TestCase):
    def test_retired_cli_model_is_replaced(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True):
            client = LLMClient(model_name="llama-3.3-70b-versatile")

        self.assertEqual(client.model_name, DEFAULT_MODEL)

    def test_blank_environment_model_uses_default(self):
        with patch.dict(
            "os.environ",
            {"GROQ_API_KEY": "test-key", "MODEL_NAME": "", "VISION_MODEL_NAME": ""},
            clear=True,
        ):
            client = LLMClient()

        self.assertEqual(client.model_name, DEFAULT_MODEL)
        self.assertIsNone(client.vision_model_name)


class TaskPlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = TaskPlanner()

    def test_ambiguous_amazon_region_requires_clarification(self):
        plan = self.planner.plan("compare iphone 16 prices on amazon")

        self.assertTrue(plan.needs_clarification)
        self.assertEqual(plan.clarification_options, ["Amazon India (INR)", "Amazon US (USD)"])

    def test_indian_amazon_request_uses_whitelisted_site(self):
        plan = self.planner.plan("compare iphone 16 prices on amazon india")

        self.assertFalse(plan.needs_clarification)
        self.assertEqual(plan.preferred_sites, ["amazon_in"])
        self.assertEqual(plan.currency, "INR")

    def test_flight_request_without_site_asks_for_preference(self):
        plan = self.planner.plan("check ticket price for a flight from Delhi to London")

        self.assertTrue(plan.needs_clarification)
        self.assertIn("flight website", plan.clarification_question)

    def test_comparison_extracts_constraints(self):
        plan = self.planner.plan("compare iphone 16 across amazon india and flipkart with at least 4.5 star rating")

        self.assertEqual(plan.task_type, "compare")
        self.assertEqual(plan.preferred_sites, ["amazon_in", "flipkart_in"])
        self.assertEqual(plan.constraints["minimum_rating"], "4.5")

    def test_comparison_extracts_product_and_budget(self):
        plan = self.planner.plan("Open chrome and compare Galaxy S6 pro prices on Amazon with my budget being 40000")

        self.assertEqual(plan.subject, "Galaxy S6 pro")
        self.assertEqual(plan.constraints["maximum_price"], "40000")


class ComparisonAnswerTests(unittest.TestCase):
    def test_answer_ranks_matching_offers_by_price(self):
        plan = TaskPlanner().plan("compare iphone 16 prices on amazon india")
        results = [
            {
                "site": "amazon_in",
                "status": "completed",
                "offers": [
                    {"site": "amazon_in", "title": "iPhone 16", "product_url": "https://example/1", "price": 64999, "currency": "INR", "rating": 4.2, "source_timestamp": "now"},
                    {"site": "amazon_in", "title": "iPhone 16 Pro", "product_url": "https://example/2", "price": 89999, "currency": "INR", "rating": 4.5, "source_timestamp": "now"},
                ],
                "warnings": [],
            }
        ]

        from models.task_models import SiteRunResult, ProductOffer
        typed_results = [SiteRunResult(
            site=item["site"],
            status=item["status"],
            offers=[ProductOffer(**offer) for offer in item["offers"]],
            warnings=item["warnings"],
        ) for item in results]
        answer = compose_comparison_answer(plan, typed_results)

        self.assertIn("Lowest matching price: INR 64,999.00", answer["answer"])
        self.assertEqual(answer["offers"][0]["price"], 64999)

    def test_budget_is_applied_to_ranking(self):
        plan = TaskPlanner().plan("compare iphone 16 prices on amazon india with my budget being 70000")
        from models.task_models import ProductOffer, SiteRunResult
        result = SiteRunResult(
            site="amazon_in",
            status="completed",
            offers=[
                ProductOffer(site="amazon_in", title="Over budget", product_url="https://example/1", price=80000, currency="INR", source_timestamp="now"),
                ProductOffer(site="amazon_in", title="Within budget", product_url="https://example/2", price=65000, currency="INR", source_timestamp="now"),
            ],
        )

        answer = compose_comparison_answer(plan, [result])

        self.assertEqual(answer["offers"][0]["title"], "Within budget")

    def test_unmet_rating_is_reported_not_presented_as_matches(self):
        plan = TaskPlanner().plan("compare iphone 16 on amazon india with at least 4.5 star rating")
        from models.task_models import ProductOffer, SiteRunResult
        result = SiteRunResult(
            site="amazon_in",
            status="completed",
            offers=[
                ProductOffer(site="amazon_in", title="Low rated", product_url="https://example/1", price=50000, currency="INR", rating=3.0, source_timestamp="now"),
                ProductOffer(site="amazon_in", title="Unrated", product_url="https://example/2", price=60000, currency="INR", source_timestamp="now"),
            ],
        )

        answer = compose_comparison_answer(plan, [result])

        self.assertIn("none met a rating of at least 4.5/5", answer["answer"])
        self.assertNotIn("Lowest matching price", answer["answer"])

    def test_every_unmet_constraint_is_named(self):
        plan = TaskPlanner().plan("compare iphone 16 on amazon india with at least 4.5 star rating and my budget being 40000")
        from models.task_models import ProductOffer, SiteRunResult
        result = SiteRunResult(
            site="amazon_in",
            status="completed",
            offers=[
                ProductOffer(site="amazon_in", title="Too expensive", product_url="https://example/1", price=80000, currency="INR", rating=4.8, source_timestamp="now"),
                ProductOffer(site="amazon_in", title="Too low rated", product_url="https://example/2", price=30000, currency="INR", rating=3.9, source_timestamp="now"),
            ],
        )

        answer = compose_comparison_answer(plan, [result])

        self.assertIn("a rating of at least 4.5/5 and the budget of INR 40,000.00", answer["answer"])
        self.assertEqual(len(answer["offers"]), 2)


class FakeController:
    """BrowserController stand-in whose navigation fails and whose close raises."""

    def __init__(self, *args, **kwargs):
        pass

    async def open_website(self, url):
        return False

    async def close_browser(self):
        raise RuntimeError("Connection closed while reading from the driver")


class SearchSiteTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_failure_does_not_replace_the_site_result(self):
        from sites.adapters import search_site
        from sites.registry import policy_for

        plan = TaskPlanner().plan("compare iphone 16 on amazon india")
        with patch("sites.adapters.BrowserController", FakeController):
            result = await search_site(policy_for("amazon_in"), plan)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.warnings, ["Initial navigation failed."])


class FakeFlipkartPage:
    """Returns cards shaped like FLIPKART_CARDS_JS output from the live site."""

    def __init__(self, cards):
        self.cards = cards

    async def wait_for_selector(self, selector, timeout=None):
        return None

    async def evaluate(self, script, limit):
        return self.cards[:limit]


class FlipkartOfferTests(unittest.IsolatedAsyncioTestCase):
    async def test_cards_become_offers_and_accessories_are_dropped(self):
        from sites.adapters import _flipkart_offers
        from sites.registry import policy_for

        page = FakeFlipkartPage([
            {"href": "/apple-iphone-16-black-128-gb/p/itmb07?pid=MOB1", "title": "Apple iPhone 16 (Black, 128 GB)", "price": "₹69,900", "rating": "4.6"},
            {"href": "/rising-byte-back-cover-iphone-16/p/itmd48", "title": "RISING BYTE Back Cover for IPHONE 16", "price": "₹269", "rating": "4"},
            {"href": "/apple-iphone-16-teal-256-gb/p/itm2b7", "title": "Apple iPhone 16 (Teal, 256 GB)", "price": "₹79,900", "rating": None},
        ])

        offers = await _flipkart_offers(page, policy_for("flipkart_in"), "iPhone 16")

        self.assertEqual([o.title for o in offers], ["Apple iPhone 16 (Black, 128 GB)", "Apple iPhone 16 (Teal, 256 GB)"])
        self.assertEqual(offers[0].price, 69900.0)
        self.assertEqual(offers[0].rating, 4.6)
        self.assertIsNone(offers[1].rating)
        self.assertEqual(offers[0].product_url, "https://flipkart.com/apple-iphone-16-black-128-gb/p/itmb07?pid=MOB1")


class ComparisonRunStatusTests(unittest.IsolatedAsyncioTestCase):
    async def _completed_event(self, statuses):
        import server
        from models.task_models import SiteRunResult

        async def fake_compare(plan):
            return [SiteRunResult(site=f"site_{i}", status=s) for i, s in enumerate(statuses)]

        plan = TaskPlanner().plan("compare iphone 16 on amazon india and flipkart")
        session = server.AgentSession(plan.subject)
        with patch("server.compare_sites", fake_compare):
            await server._run_agent(session, plan.subject, plan)

        events = []
        while not session.queue.empty():
            events.append(await session.queue.get())
        return next(e for e in events if e and e["type"] == "agent_completed")["data"]["result"]

    async def test_one_completed_site_completes_the_comparison(self):
        result = await self._completed_event(["failed", "completed"])
        self.assertTrue(result["completed"])
        self.assertEqual(result["reason"], "comparison_complete")

    async def test_all_failed_sites_fail_the_comparison(self):
        result = await self._completed_event(["failed", "failed"])
        self.assertFalse(result["completed"])
        self.assertEqual(result["reason"], "comparison_failed")

    async def test_all_blocked_sites_are_reported_as_blocked(self):
        result = await self._completed_event(["blocked", "blocked"])
        self.assertFalse(result["completed"])
        self.assertEqual(result["reason"], "sites_blocked")


class FakeIntentParser:
    def __init__(self, website_url):
        self.website_url = website_url

    async def parse(self, user_query):
        from llm.intent_parser import ParsedIntent
        return ParsedIntent(website_url=self.website_url, intent="search")


class ConfiguredLLM:
    is_configured = True


class FakeGoalCompiler:
    async def compile(self, user_query):
        from models.goal_models import GoalContract, GoalRequirement
        return GoalContract(task_id="t", intent="search", requirements=[
            GoalRequirement(id="r", type="content", description=user_query)])


class FailingIntentParser:
    async def parse(self, user_query):
        raise AssertionError("intent parser should not be called")


def _test_agent(intent_parser, allowed_hosts=None):
    from agents.reasoning_agent import ReasoningAgent

    async def ignore(event_type, data):
        pass

    with patch("agents.reasoning_agent.MemoryState"):
        agent = ReasoningAgent(allowed_hosts=allowed_hosts, on_event=ignore)
    agent.llm_client = ConfiguredLLM()
    agent.goal_compiler = FakeGoalCompiler()
    agent.intent_parser = intent_parser
    agent.memory.extracted_data = {}
    return agent


class AgentStartTests(unittest.IsolatedAsyncioTestCase):
    """Where execute_task starts, per the router's strategy."""

    def _record_navigation(self, agent):
        visited = []

        async def record_open(url):
            visited.append(url)
            return False

        agent.browser_controller.open_website = record_open
        return visited

    async def test_direct_url_strategy_starts_there_without_parsing_intent(self):
        from models.strategy_models import DirectURLStrategy
        agent = _test_agent(FailingIntentParser(), allowed_hosts={"www.amazon.in"})
        visited = self._record_navigation(agent)
        strategy = DirectURLStrategy(url="https://www.amazon.in/s?k=iPhone%2016", website="amazon")

        await agent.execute_task("search iPhone 16 on amazon india", strategy=strategy)

        self.assertEqual(visited, ["https://www.amazon.in/s?k=iPhone%2016"])

    async def test_unapproved_named_site_stops_before_launching_a_browser(self):
        agent = _test_agent(FakeIntentParser("https://books.toscrape.com/"), allowed_hosts={"www.amazon.in"})
        visited = self._record_navigation(agent)

        result = await agent.execute_task("go to books.toscrape.com")

        self.assertEqual(result.reason, "site_not_approved")
        self.assertEqual(visited, [])

    async def test_unrestricted_query_without_a_site_uses_web_search(self):
        agent = _test_agent(FakeIntentParser(None))
        visited = self._record_navigation(agent)

        await agent.execute_task("find iphone 16")

        self.assertTrue(visited[0].startswith("https://duckduckgo.com/?q="))


class FakeObserver:
    """StateObserver stand-in returning a fixed sequence of page states."""
    states = []

    def __init__(self, page):
        pass

    async def observe(self):
        return FakeObserver.states.pop(0)


class CountingVerifier:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = 0

    async def verify(self, contract, state):
        from models.goal_models import VerificationResult
        self.calls += 1
        return VerificationResult(status=self.statuses.pop(0), confidence=0.9)


class GoalLoopTests(unittest.IsolatedAsyncioTestCase):
    """One iteration of the goal loop where the planner claims "done"."""

    async def _run(self, states, statuses):
        from models.orchestration_models import AgentState, StepDecision

        agent = _test_agent(FailingIntentParser())
        agent.max_iterations = 1
        agent.memory.extracted_data = {"Extraction_Iter_1": "₹69,900"}
        agent.goal_verifier = CountingVerifier(statuses)

        async def opened(url):
            return True

        async def build_state(*args):
            return AgentState(user_query="q", iteration=1, current_url=states[0].url, page_context="", memory_context="")

        async def decide(*args):
            return StepDecision(action=AgentAction(action="done"), needs_verification=True)

        async def act(*args):
            return ActionResult(success=True, action="scroll")

        agent.browser_controller.open_website = opened
        agent._build_state = build_state
        agent._decide_next_step = decide
        agent._execute_with_recovery = act
        FakeObserver.states = list(states)
        from models.strategy_models import DirectURLStrategy
        with patch("agents.reasoning_agent.StateObserver", FakeObserver):
            result = await agent.execute_task("q", strategy=DirectURLStrategy(url="https://www.amazon.in/s?k=q"))
        return result, agent.goal_verifier.calls

    async def test_unchanged_page_is_not_verified_twice(self):
        from models.goal_models import ObservedState
        same = ObservedState(url="https://www.amazon.in/s?k=q", title="t")

        result, calls = await self._run([same, same.model_copy()], ["NOT_ACHIEVED", "ACHIEVED"])

        self.assertEqual(calls, 1)
        self.assertFalse(result.completed)


class RecoveryPolicyTests(unittest.TestCase):
    def test_failed_locator_recovers_with_scroll(self):
        policy = RecoveryPolicy()
        result = ActionResult(
            success=False,
            action="click",
            target="pw-id-1",
            error="No element found",
            recovery_hint="refresh_dom_or_use_vision",
        )

        action = policy.from_result(result)

        self.assertEqual(action.action, "scroll")
        self.assertEqual(action.value, "down")


class BrowserExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_page_level_scroll_returns_structured_result(self):
        page = FakePage()
        executor = BrowserExecutor(page)

        result = await executor.execute(AgentAction(action="scroll", value="up"))

        self.assertTrue(result.success)
        self.assertEqual(result.action, "scroll")
        self.assertEqual(result.metadata["direction"], "up")
        self.assertEqual(page.mouse.wheel_calls, [(0, -600)])

    async def test_missing_target_returns_recovery_hint(self):
        executor = BrowserExecutor(FakePage())

        result = await executor.execute(AgentAction(action="click", reasoning="test"))

        self.assertFalse(result.success)
        self.assertEqual(result.recovery_hint, "choose_visible_target_or_scroll")


class GoalVerifierTests(unittest.IsolatedAsyncioTestCase):
    def _inputs(self):
        from models.goal_models import GoalContract, GoalRequirement, ObservedState
        contract = GoalContract(task_id="t", intent="find_price", requirements=[
            GoalRequirement(id="price", type="content", description="Price is shown")])
        return contract, ObservedState(url="https://example.test", title="Product", visible_text=["₹69,900"])

    async def test_verifier_accepts_achieved_response(self):
        verifier = GoalVerifier(FakeLLMClient({"status": "ACHIEVED", "confidence": 0.9, "evidence": {"found_text": "₹69,900"}}))

        result = await verifier.verify(*self._inputs())

        self.assertEqual(result.status, "ACHIEVED")
        self.assertEqual(result.confidence, 0.9)

    async def test_verifier_treats_empty_response_as_unknown(self):
        verifier = GoalVerifier(FakeLLMClient({}))

        result = await verifier.verify(*self._inputs())

        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(result.confidence, 0.0)


class ProgressTrackerTests(unittest.TestCase):
    def _state(self, scroll_y=0, forms=None):
        from models.goal_models import ObservedState
        return ObservedState(url="https://www.amazon.in/s?k=q", title="Results",
                             visible_text=["same page text"], scroll_y=scroll_y, forms=forms or [])

    def test_scrolling_is_progress(self):
        from agents.progress_tracker import ProgressTracker
        tracker = ProgressTracker()

        stuck = [tracker.is_stuck(self._state(scroll_y=y)) for y in (0, 600, 1200)]

        self.assertEqual(stuck, [False, False, False])

    def test_typing_is_progress(self):
        from agents.progress_tracker import ProgressTracker
        tracker = ProgressTracker()

        stuck = [tracker.is_stuck(self._state(forms=f)) for f in (
            [], [{"field": "k", "value": "iph"}], [{"field": "k", "value": "iphone 16"}])]

        self.assertEqual(stuck, [False, False, False])

    def test_identical_states_are_stuck(self):
        from agents.progress_tracker import ProgressTracker
        tracker = ProgressTracker()

        stuck = [tracker.is_stuck(self._state()) for _ in range(3)]

        self.assertEqual(stuck, [False, False, True])


class BrowserControllerTests(unittest.TestCase):
    def test_headless_setting_is_respected(self):
        from browser.controller import BrowserController

        self.assertTrue(BrowserController(headless=True).headless)
        self.assertFalse(BrowserController().headless)


class SignatureTests(unittest.TestCase):
    TRACKED = "https://www.amazon.com/s?k=iPhone+16&crid=2MUZMVD8M5O0F&ref=nb_sb_noss_1"
    CLEAN = "https://amazon.com/s?k=iPhone+16"

    def test_normalize_url_strips_tracking_but_keeps_query(self):
        self.assertEqual(normalize_url(self.TRACKED), self.CLEAN)

    def test_normalize_url_drops_www_fragment_and_trailing_slash(self):
        self.assertEqual(
            normalize_url("https://www.example.com/a/#section"),
            normalize_url("https://example.com/a"),
        )

    def test_page_key_ignores_tracking_parameters(self):
        self.assertEqual(page_key(self.TRACKED), page_key(self.CLEAN))

    def test_page_key_distinguishes_meaningful_query(self):
        self.assertNotEqual(
            page_key("https://amazon.com/s?k=iphone"),
            page_key("https://amazon.com/s?k=ipad"),
        )

    def test_view_signature_ignores_playwright_index_renumbering(self):
        first = [{"playwright_index": "pw-id-0", "tag": "a", "text": "Books"}]
        # The extractor recounts indices on every extraction.
        renumbered = [{"playwright_index": "pw-id-9", "tag": "a", "text": "Books"}]

        self.assertEqual(
            view_signature(self.CLEAN, first),
            view_signature(self.CLEAN, renumbered),
        )

    def test_view_signature_ignores_dom_reordering(self):
        elements = [
            {"tag": "a", "text": "Books"},
            {"tag": "h1", "text": "Results"},
        ]

        self.assertEqual(
            view_signature(self.CLEAN, elements),
            view_signature(self.CLEAN, list(reversed(elements))),
        )

    def test_view_signature_changes_when_viewport_changes(self):
        top = [{"tag": "a", "text": "Books"}]
        scrolled = [{"tag": "h2", "text": "Next page"}]

        self.assertNotEqual(
            view_signature(self.CLEAN, top),
            view_signature(self.CLEAN, scrolled),
        )

    def test_element_descriptor_excludes_unstable_attributes(self):
        stable = {"tag": "button", "text": "Go"}
        with_generated = {
            "tag": "button",
            "text": "Go",
            "playwright_index": "pw-id-4",
            "id": "react-select-3-input",
            "className": "css-1x2y3z4",
        }

        self.assertEqual(element_descriptor(stable), element_descriptor(with_generated))

    def test_element_descriptor_strips_href_query(self):
        self.assertEqual(
            element_descriptor({"tag": "a", "href": "/dp/B0C?ref=sr_1_1&psc=1"}),
            element_descriptor({"tag": "a", "href": "/dp/B0C"}),
        )


class StepVerifierTests(unittest.TestCase):
    A = "https://a.test/"
    B = "https://b.test/"

    def setUp(self):
        self.verifier = StepVerifier()

    def _result(self, success=True, url_after=None, value=None):
        return ActionResult(
            success=success,
            action="x",
            url_before=self.A,
            url_after=url_after or self.A,
            value=value,
        )

    def test_url_change_verifies_a_click(self):
        verdict = self.verifier.verify(
            AgentAction(action="click"), self._result(url_after=self.B)
        )

        self.assertEqual(verdict.status, "verified")
        self.assertEqual(verdict.evidence, "url_changed")

    def test_viewport_change_verifies_a_scroll(self):
        verdict = self.verifier.verify(
            AgentAction(action="scroll"), self._result(), "view_aaa", "view_bbb"
        )

        self.assertEqual(verdict.status, "verified")
        self.assertEqual(verdict.evidence, "view_changed")

    def test_clean_execution_with_no_change_is_not_verified(self):
        # The gap ActionResult.success hides: Playwright did not raise, but
        # nothing on the page moved.
        verdict = self.verifier.verify(
            AgentAction(action="click"), self._result(), "view_aaa", "view_aaa"
        )

        self.assertTrue(self._result().success)
        self.assertEqual(verdict.status, "unverified")
        self.assertEqual(verdict.evidence, "no_observable_change")

    def test_navigation_to_the_same_url_is_not_verified(self):
        verdict = self.verifier.verify(AgentAction(action="navigate"), self._result())

        self.assertEqual(verdict.status, "unverified")

    def test_extract_is_judged_on_its_value(self):
        got = self.verifier.verify(AgentAction(action="extract"), self._result(value=" 19.99 "))
        empty = self.verifier.verify(AgentAction(action="extract"), self._result(value="   "))

        self.assertEqual(got.status, "verified")
        self.assertEqual(empty.status, "unverified")

    def test_failed_execution_is_never_verified(self):
        verdict = self.verifier.verify(
            AgentAction(action="click"), self._result(success=False, url_after=self.B)
        )

        self.assertEqual(verdict.status, "unverified")
        self.assertEqual(verdict.evidence, "execution_failed")

    def test_wait_and_done_are_not_applicable(self):
        for name in ("wait", "done"):
            verdict = self.verifier.verify(AgentAction(action=name), self._result())
            self.assertEqual(verdict.status, "not_applicable", name)

    def test_dom_is_not_re_extracted_when_the_answer_is_already_known(self):
        cases = {
            "url already changed": (AgentAction(action="click"), self._result(url_after=self.B)),
            "navigation": (AgentAction(action="navigate"), self._result()),
            "extraction": (AgentAction(action="extract"), self._result(value="x")),
            "wait": (AgentAction(action="wait"), self._result()),
            "failed": (AgentAction(action="click"), self._result(success=False)),
        }
        for label, (action, result) in cases.items():
            self.assertFalse(self.verifier.needs_view_signature(action, result), label)

    def test_dom_is_re_extracted_when_it_is_the_only_evidence(self):
        self.assertTrue(
            self.verifier.needs_view_signature(AgentAction(action="click"), self._result())
        )


class TargetDescriptorTests(unittest.TestCase):
    ELEMENTS = [
        {"playwright_index": "pw-id-0", "tag": "a", "text": "Home"},
        {"playwright_index": "pw-id-3", "tag": "input", "type": "submit", "aria_label": "Search"},
    ]

    def test_target_resolves_to_a_descriptor_without_the_index(self):
        descriptor = descriptor_for_target("pw-id-3", self.ELEMENTS)

        self.assertIn("aria_label=Search", descriptor)
        self.assertNotIn("pw-id", descriptor)

    def test_same_element_at_a_new_index_yields_the_same_descriptor(self):
        # What a later run sees after the extractor recounts.
        renumbered = [
            {"playwright_index": "pw-id-9", "tag": "input", "type": "submit", "aria_label": "Search"},
        ]

        self.assertEqual(
            descriptor_for_target("pw-id-3", self.ELEMENTS),
            descriptor_for_target("pw-id-9", renumbered),
        )

    def test_missing_or_absent_target_is_none(self):
        self.assertIsNone(descriptor_for_target(None, self.ELEMENTS))
        self.assertIsNone(descriptor_for_target("pw-id-99", self.ELEMENTS))
        self.assertIsNone(descriptor_for_target("pw-id-0", []))

    def test_ambiguous_target_descriptor_is_not_remembered(self):
        elements = [
            {"playwright_index": "pw-id-1", "tag": "a", "text": "Vote"},
            {"playwright_index": "pw-id-2", "tag": "a", "text": "Vote"},
        ]

        self.assertIsNone(descriptor_for_target("pw-id-2", elements))


class VerifiedActionIdTests(unittest.TestCase):
    def test_same_action_for_same_goal_reinforces_one_entry(self):
        first = MemoryState.verified_action_id("buy milk", "page_a", "click", "desc", "")
        again = MemoryState.verified_action_id("buy milk", "page_a", "click", "desc", "")

        self.assertEqual(first, again)

    def test_goal_and_page_both_separate_memories(self):
        base = MemoryState.verified_action_id("buy milk", "page_a", "click", "desc", "")
        other_goal = MemoryState.verified_action_id("buy bread", "page_a", "click", "desc", "")
        other_page = MemoryState.verified_action_id("buy milk", "page_b", "click", "desc", "")

        self.assertNotEqual(base, other_goal)
        self.assertNotEqual(base, other_page)


class NavigationGraphTests(unittest.TestCase):
    A, B, C = "page_a", "page_b", "page_c"

    def setUp(self):
        self._dir = tempfile.mkdtemp()
        self.graph = NavigationGraph(self._dir)

    def tearDown(self):
        self.graph.close()
        shutil.rmtree(self._dir, ignore_errors=True)

    def test_edge_is_recorded_and_readable(self):
        self.graph.record_edge(self.A, self.B, "click", "tag=a|text=Next")

        edges = self.graph.neighbours(self.A)

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["to_page"], self.B)
        self.assertEqual(edges[0]["target_descriptor"], "tag=a|text=Next")

    def test_repeating_a_route_reinforces_rather_than_duplicates(self):
        for _ in range(3):
            self.graph.record_edge(self.A, self.B, "click", "tag=a|text=Next")

        edges = self.graph.neighbours(self.A)

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["times_seen"], 3)

    def test_self_transition_is_not_an_edge(self):
        # The action changed the page in place; it went nowhere.
        self.assertFalse(self.graph.record_edge(self.A, self.A, "click"))
        self.assertEqual(self.graph.edge_count(), 0)

    def test_shortest_path_is_found_across_hops(self):
        self.graph.record_edge(self.A, self.B, "click", "to-b")
        self.graph.record_edge(self.B, self.C, "click", "to-c")

        route = self.graph.path_between(self.A, self.C)

        self.assertEqual([e["to_page"] for e in route], [self.B, self.C])
        self.assertEqual(route[0]["target_descriptor"], "to-b")

    def test_unknown_route_returns_empty(self):
        self.graph.record_edge(self.A, self.B, "click")

        self.assertEqual(self.graph.path_between(self.A, "page_unreachable"), [])

    def test_survives_reopening_the_store(self):
        self.graph.record_edge(self.A, self.B, "click")
        self.graph.close()

        reopened = NavigationGraph(self._dir)
        try:
            self.assertEqual(len(reopened.neighbours(self.A)), 1)
        finally:
            reopened.close()

    def test_missing_store_degrades_instead_of_raising(self):
        broken = NavigationGraph(self._dir)
        broken.close()

        self.assertFalse(broken.is_available)
        self.assertFalse(broken.record_edge(self.A, self.B, "click"))
        self.assertEqual(broken.neighbours(self.A), [])
        self.assertEqual(broken.path_between(self.A, self.B), [])


class RecallResolutionTests(unittest.TestCase):
    """A remembered action is only useful if it can be pointed at a live element."""

    SEARCH = {"playwright_index": "pw-id-3", "tag": "input", "type": "submit", "aria_label": "Search"}

    def test_remembered_descriptor_resolves_to_todays_index(self):
        descriptor = descriptor_for_target("pw-id-3", [self.SEARCH])
        # Next run: the extractor gave the same element a different index.
        today = [{**self.SEARCH, "playwright_index": "pw-id-11"}]

        self.assertEqual(target_for_descriptor(descriptor, today), "pw-id-11")

    def test_element_not_on_screen_resolves_to_none(self):
        descriptor = descriptor_for_target("pw-id-3", [self.SEARCH])
        scrolled_away = [{"playwright_index": "pw-id-0", "tag": "h2", "text": "Footer"}]

        self.assertIsNone(target_for_descriptor(descriptor, scrolled_away))

    def test_round_trip_is_stable(self):
        descriptor = descriptor_for_target("pw-id-3", [self.SEARCH])

        self.assertEqual(target_for_descriptor(descriptor, [self.SEARCH]), "pw-id-3")

    def test_ambiguous_descriptor_does_not_guess_a_live_target(self):
        descriptor = element_descriptor({"tag": "a", "text": "Vote"})
        elements = [
            {"playwright_index": "pw-id-1", "tag": "a", "text": "Vote"},
            {"playwright_index": "pw-id-2", "tag": "a", "text": "Vote"},
        ]

        self.assertIsNone(target_for_descriptor(descriptor, elements))


class MemoryRecallContextTests(unittest.TestCase):
    def setUp(self):
        self.builder = ContextBuilder()

    def test_resolved_action_is_rendered_with_its_live_target(self):
        text = self.builder.build_memory_recall(
            [{"action": "click", "target_descriptor": "tag=input", "live_target": "pw-id-7",
              "evidence": "url_changed"}],
            [],
        )

        self.assertIn("click on pw-id-7", text)
        self.assertIn("url_changed", text)

    def test_unresolved_action_is_still_offered_as_a_hint(self):
        text = self.builder.build_memory_recall(
            [{"action": "click", "target_descriptor": "tag=a|text=Next", "live_target": None}],
            [],
        )

        self.assertIn("not currently visible", text)
        self.assertIn("tag=a|text=Next", text)

    def test_routes_are_rendered_with_how_often_they_were_taken(self):
        text = self.builder.build_memory_recall(
            [], [{"action": "navigate", "to_page": "page_b", "times_seen": 4, "target_descriptor": ""}]
        )

        self.assertIn("page_b", text)
        self.assertIn("4x", text)

    def test_nothing_recalled_renders_nothing(self):
        self.assertEqual(self.builder.build_memory_recall([], []), "")


if __name__ == "__main__":
    unittest.main()
