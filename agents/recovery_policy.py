from typing import Optional

from models.action_models import AgentAction
from models.orchestration_models import ActionResult


class RecoveryPolicy:
    """Deterministic recovery actions for common browser-agent failures."""

    def from_loop(self) -> AgentAction:
        return AgentAction(
            action="scroll",
            target=None,
            value="down",
            reasoning="Repeated action loop detected; scrolling to expose new page state.",
        )

    def from_result(self, result: ActionResult) -> Optional[AgentAction]:
        if result.success:
            return None

        hint = result.recovery_hint or ""
        if hint in {"choose_visible_target_or_scroll", "refresh_dom_or_use_vision", "retry_scroll_or_vision"}:
            return AgentAction(
                action="scroll",
                target=None,
                value="down",
                reasoning=f"Previous action failed ({result.error}); scrolling to refresh visible DOM context.",
            )

        if hint == "ask_llm_for_url":
            return AgentAction(
                action="back",
                target=None,
                reasoning="Navigation URL was missing; returning to the previous page before replanning.",
            )

        return None
