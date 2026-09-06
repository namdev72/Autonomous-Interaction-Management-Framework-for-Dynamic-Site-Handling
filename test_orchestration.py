import unittest

from agents.goal_verifier import GoalVerifier
from agents.recovery_policy import RecoveryPolicy
from browser.actions import BrowserExecutor
from memory.signature import element_descriptor, normalize_url, page_key, view_signature
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
    async def test_verifier_accepts_complete_response(self):
        verifier = GoalVerifier(FakeLLMClient({"complete": True, "reason": "found"}))

        complete = await verifier.verify("find price", "page has price", "memory")

        self.assertTrue(complete)

    async def test_verifier_rejects_empty_response(self):
        verifier = GoalVerifier(FakeLLMClient({}))

        complete = await verifier.verify("find price", "page", "memory")

        self.assertFalse(complete)


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


if __name__ == "__main__":
    unittest.main()
