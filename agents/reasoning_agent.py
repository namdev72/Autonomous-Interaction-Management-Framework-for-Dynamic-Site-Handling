import asyncio
import os
import time
from typing import Awaitable, Callable, Optional

from loguru import logger

from agents.goal_verifier import GoalVerifier
from agents.recovery_policy import RecoveryPolicy
from browser.actions import BrowserExecutor
from browser.controller import BrowserController
from browser.dom_extractor import DOMExtractor
from context.context_builder import ContextBuilder
from llm.intent_parser import IntentParser
from llm.llm_client import LLMClient
from memory.history import MemoryState
from models.action_models import AgentAction
from models.orchestration_models import ActionResult, AgentRunResult, AgentState, StepDecision


async def default_cli_printer(event_type: str, data: dict):
    if event_type == "log":
        message = data.get("message", "")
        level = data.get("level", "info").lower()
        if level == "success":
            logger.success(message)
        elif level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)
    elif event_type == "action":
        action = data.get("action")
        target = data.get("target")
        value = data.get("value")
        reasoning = data.get("reasoning")
        logger.info(f"Action: {str(action).upper()} | Target: {target} | Value: {value}")
        logger.info(f"Reasoning: {reasoning}")
    elif event_type == "extraction":
        key = data.get("key")
        value = data.get("value")
        logger.success(f"Extracted Data [{key}]: {value}")


class ReasoningAgent:
    def __init__(
        self,
        headless: bool = False,
        max_iterations: int = 15,
        on_event: Optional[Callable[[str, dict], Awaitable[None]]] = None,
    ):
        self.browser_controller = BrowserController(headless=headless)
        self.llm_client = LLMClient()
        self.intent_parser = IntentParser(self.llm_client)
        self.context_builder = ContextBuilder()
        self.memory = MemoryState()
        self.recovery_policy = RecoveryPolicy()
        self.goal_verifier = GoalVerifier(self.llm_client)
        self.max_iterations = max_iterations
        self.on_event = on_event if on_event is not None else default_cli_printer

    async def _emit(self, event_type: str, data: dict):
        if self.on_event:
            await self.on_event(event_type, data)

    async def _emit_log(self, message: str, level: str = "info"):
        await self._emit("log", {"message": message, "level": level})

    async def _emit_screenshot(self, name_prefix: str = "screenshot") -> Optional[str]:
        try:
            if self.browser_controller.page:
                os.makedirs("screenshots", exist_ok=True)
                filename = f"screenshots/{name_prefix}_{int(time.time())}.png"
                await self.browser_controller.page.screenshot(path=filename, full_page=False)
                return filename
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
        return None

    def _agent_system_prompt(self, user_query: str) -> str:
        return f"""
        You are an autonomous web browser agent.
        Your goal is: {user_query}

        You only see elements currently visible in the viewport. If the target is not visible, use scroll.
        Prefer precise data-playwright-id targets from the context, such as pw-id-3.

        Supported actions:
        - click: click a target element.
        - type: fill a target input with value.
        - scroll: scroll the viewport or target element. Use value "down" or "up" when no target is needed.
        - wait: wait for value seconds.
        - navigate: go to the URL in value.
        - extract: extract text from target.
        - back: go to the previous page.
        - hover, drag_to, press_key, select: use only when required by the page control.
        - done: use only after the user goal is satisfied by visible page evidence or extracted data.

        If an element is hidden in an iframe, modal, captcha, or visual-only widget, set fallback_to_vision true.

        Respond ONLY with a valid JSON object matching this schema:
        {{
            "action": "<action_type>",
            "target": "<playwright_index_or_null>",
            "value": "<value_or_null>",
            "reasoning": "<brief_reasoning>",
            "fallback_to_vision": <boolean>
        }}
        """

    def _agent_user_prompt(self, state: AgentState) -> str:
        semantic = "\n\nRelevant Semantic Memory:\n" + "\n---\n".join(state.semantic_memory) if state.semantic_memory else ""
        result = ""
        if state.last_result:
            result = f"""

        Last Action Result:
        success={state.last_result.success}
        action={state.last_result.action}
        target={state.last_result.target}
        error={state.last_result.error}
        recovery_hint={state.last_result.recovery_hint}
        url_after={state.last_result.url_after}
        """
        return f"{state.memory_context}{semantic}{result}\n\nCurrent Page Context:\n{state.page_context}"

    async def _build_state(
        self,
        user_query: str,
        iteration: int,
        last_action: Optional[AgentAction],
        last_result: Optional[ActionResult],
    ) -> AgentState:
        dom_extractor = DOMExtractor(self.browser_controller.page)
        elements = await dom_extractor.extract_interactive_elements()
        await self._emit_log(f"Extracted {len(elements)} interactive DOM elements.")

        current_url = self.browser_controller.page.url
        self.memory.add_url(current_url)

        page_context = self.context_builder.build_context(current_url, elements)
        self.memory.index_page_content(current_url, page_context)
        memory_context = self.memory.get_context_string()
        semantic_memory = self.memory.semantic_search(user_query, n_results=2)

        return AgentState(
            user_query=user_query,
            iteration=iteration,
            current_url=current_url,
            page_context=page_context,
            memory_context=memory_context,
            semantic_memory=semantic_memory,
            last_action=last_action,
            last_result=last_result,
        )

    async def _decide_next_step(self, state: AgentState) -> Optional[StepDecision]:
        await self._emit_log("Querying LLM for next action...")
        response_json = await self.llm_client.generate_json(
            self._agent_system_prompt(state.user_query),
            self._agent_user_prompt(state),
        )
        if not response_json:
            await self._emit_log("Empty response from LLM. Retrying after wait.", "warning")
            return StepDecision(
                action=AgentAction(action="wait", value="2", reasoning="LLM returned an empty response."),
                source="orchestrator",
            )

        try:
            action = AgentAction(**response_json)
        except Exception as e:
            await self._emit_log(f"Invalid LLM action schema: {e}", "error")
            return None

        return StepDecision(action=action, source="llm", needs_verification=action.action == "done")

    async def _execute_with_recovery(
        self,
        executor: BrowserExecutor,
        action: AgentAction,
        state: AgentState,
    ) -> ActionResult:
        self.memory.add_action(action)
        self.memory.save_state()

        if self.memory.detect_loop():
            await self._emit_log("Detected repeated action loop. Applying recovery policy.", "warning")
            action = self.recovery_policy.from_loop()
            self.memory.add_action(action)
            await self._emit("action", action.model_dump())

        result = await executor.execute(action)

        if not result.success:
            recovery_action = self.recovery_policy.from_result(result)
            if recovery_action:
                await self._emit_log(f"Applying recovery action: {recovery_action.action}", "warning")
                self.memory.add_action(recovery_action)
                await self._emit("action", recovery_action.model_dump())
                result = await executor.execute(recovery_action)

        if (not result.success or action.fallback_to_vision) and action.action == "click":
            result = await self._run_vision_fallback(executor, action, state, result)

        return result

    async def _run_vision_fallback(
        self,
        executor: BrowserExecutor,
        action: AgentAction,
        state: AgentState,
        previous_result: ActionResult,
    ) -> ActionResult:
        await self._emit_log("Triggering vision fallback for click recovery.", "warning")
        screenshot_path = await self._emit_screenshot(name_prefix="vision_fallback")
        if not screenshot_path:
            previous_result.error = previous_result.error or "Failed to capture screenshot for vision fallback."
            return previous_result

        vision_prompt = self._agent_user_prompt(state)
        vision_json = await self.llm_client.generate_vision_json(screenshot_path, vision_prompt)
        if not vision_json or "x" not in vision_json or "y" not in vision_json:
            previous_result.error = previous_result.error or "Vision model did not return x/y coordinates."
            previous_result.screenshot_path = screenshot_path
            return previous_result

        vision_action = action.model_copy(update={"x": vision_json["x"], "y": vision_json["y"]})
        result = await executor.execute(vision_action)
        result.screenshot_path = screenshot_path
        return result

    async def _record_result(self, result: ActionResult, iteration: int):
        if result.action == "extract" and result.success:
            key = f"Extraction_Iter_{iteration}"
            self.memory.store_extracted_data(key, result.value)
            await self._emit_log(f"Extracted: {result.value}", "success")
            await self._emit("extraction", {"key": key, "value": result.value})

    async def execute_task(self, user_query: str) -> AgentRunResult:
        logger.info(f"Starting agent task: {user_query}")
        await self._emit_log(f"Starting task: {user_query}")

        last_action = None
        last_result = None
        iterations = 0

        try:
            intent = await self.intent_parser.parse(user_query)
            await self._emit_log(f"Parsed Intent: {intent.model_dump_json()}")

            if not intent.website_url:
                import urllib.parse

                query_encoded = urllib.parse.quote(user_query)
                intent.website_url = f"https://duckduckgo.com/?q={query_encoded}"
                await self._emit_log(f"Falling back to web search for: {user_query}", "warning")

            await self._emit_log(f"Launching browser and navigating to {intent.website_url}...")
            success = await self.browser_controller.open_website(intent.website_url)
            if not success:
                await self._emit_log("Failed to load website. Aborting.", "error")
                return AgentRunResult(completed=False, iterations=0, reason="initial_navigation_failed")

            await self.browser_controller.wait_for_load()
            executor = BrowserExecutor(self.browser_controller.page)

            for iterations in range(1, self.max_iterations + 1):
                logger.info(f"--- Iteration {iterations} ---")
                await self._emit_log(f"--- Iteration {iterations} ---")

                state = await self._build_state(user_query, iterations, last_action, last_result)
                decision = await self._decide_next_step(state)
                if not decision:
                    last_result = ActionResult(success=False, action="invalid", error="Invalid LLM action.")
                    await asyncio.sleep(2)
                    continue

                action = decision.action
                await self._emit_log(
                    f"Decided Action: {action.action} on {action.target} (Reasoning: {action.reasoning})",
                    "success",
                )
                await self._emit("action", action.model_dump())

                if decision.needs_verification:
                    verified = await self.goal_verifier.verify(user_query, state.page_context, state.memory_context)
                    if verified:
                        await self._emit_log("Goal verified as complete.", "success")
                        return AgentRunResult(
                            completed=True,
                            iterations=iterations,
                            reason="goal_verified",
                            extracted_data=self.memory.extracted_data,
                            last_url=state.current_url,
                        )
                    await self._emit_log("Done was not verified; continuing with recovery scroll.", "warning")
                    action = self.recovery_policy.from_loop()

                last_result = await self._execute_with_recovery(executor, action, state)
                self.memory.add_result(last_result)
                self.memory.save_state()
                last_action = action
                await self._record_result(last_result, iterations)

                screenshot_path = await self._emit_screenshot(name_prefix="iteration")
                if screenshot_path:
                    last_result.screenshot_path = screenshot_path

                await self.browser_controller.wait_for_load()
                await asyncio.sleep(1)

            await self._emit_log("Reached maximum iterations before achieving the goal.", "warning")
            return AgentRunResult(
                completed=False,
                iterations=iterations,
                reason="max_iterations_reached",
                extracted_data=self.memory.extracted_data,
                last_url=self.browser_controller.page.url if self.browser_controller.page else None,
            )
        finally:
            await self._emit_log("Task execution finished. Keeping browser open for 5 seconds for visual inspection.")
            await asyncio.sleep(5)
            await self.browser_controller.close_browser()
