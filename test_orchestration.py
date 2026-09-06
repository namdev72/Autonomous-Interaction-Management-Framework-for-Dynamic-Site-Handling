import unittest

from agents.goal_verifier import GoalVerifier
from agents.recovery_policy import RecoveryPolicy
from browser.actions import BrowserExecutor
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


if __name__ == "__main__":
    unittest.main()
