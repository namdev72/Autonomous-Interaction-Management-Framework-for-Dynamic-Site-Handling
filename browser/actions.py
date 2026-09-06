from playwright.async_api import Page
from models.action_models import AgentAction
from models.orchestration_models import ActionResult
from loguru import logger
import asyncio

class BrowserExecutor:
    def __init__(self, page: Page):
        self.page = page

    def _result(
        self,
        action: AgentAction,
        success: bool,
        value=None,
        error: str = None,
        recovery_hint: str = None,
        url_before: str = None,
    ) -> ActionResult:
        return ActionResult(
            success=success,
            action=action.action,
            target=action.target,
            value=value,
            error=error,
            recovery_hint=recovery_hint,
            url_before=url_before,
            url_after=self.page.url,
        )

    async def execute(self, action: AgentAction) -> ActionResult:
        """
        Executes an action mapped from the LLM's structured output.
        Returns a structured result for orchestration and recovery.
        """
        logger.info(f"Executing action: {action.action} on target: {action.target}")
        url_before = self.page.url
        
        try:
            if action.x is not None and action.y is not None:
                logger.info(f"Executing coordinate click at ({action.x}, {action.y})")
                await self.page.mouse.click(action.x, action.y)
                return self._result(action, True, url_before=url_before, recovery_hint="coordinate_click")
                
            if action.action == "done":
                logger.success("Agent signaled task completion.")
                return self._result(action, True, url_before=url_before)
                
            elif action.action == "wait":
                delay = int(action.value) if action.value and action.value.isdigit() else 2
                logger.info(f"Waiting for {delay} seconds...")
                await asyncio.sleep(delay)
                return self._result(action, True, url_before=url_before)
                
            elif action.action == "navigate":
                if not action.value:
                    logger.error("Navigate action missing 'value' URL.")
                    return self._result(action, False, error="Navigate action missing value URL.", recovery_hint="ask_llm_for_url", url_before=url_before)
                await self.page.goto(action.value, wait_until="load", timeout=30000)
                return self._result(action, True, url_before=url_before)
                
            elif action.action == "back":
                await self.page.go_back(wait_until="load")
                return self._result(action, True, url_before=url_before)

            elif action.action == "scroll" and not action.target:
                direction = (action.value or "down").lower()
                delta = -600 if direction in {"up", "top"} else 600
                await self.page.mouse.wheel(0, delta)
                return self._result(action, True, url_before=url_before, metadata={"direction": direction})
                
            # For actions that require a target
            if not action.target:
                logger.error(f"Action '{action.action}' requires a target.")
                return self._result(action, False, error=f"Action '{action.action}' requires a target.", recovery_hint="choose_visible_target_or_scroll", url_before=url_before)

            # Build a Playwright locator.
            # Prefer our injected data-playwright-id, otherwise fallback to standard text/css
            if action.target.startswith("pw-id-"):
                selector = f"[data-playwright-id='{action.target}']"
            else:
                # If the LLM returned a plain text or generic string, try text locator
                selector = f"text={action.target}"

            locators = self.page.locator(selector)
            count = await locators.count()
            if count == 0:
                logger.error(f"No element found for selector {selector}")
                return self._result(action, False, error=f"No element found for selector {selector}", recovery_hint="refresh_dom_or_use_vision", url_before=url_before)
            
            # Multi-Match Recovery: prefer the one that is actually visible
            locator = None
            if count > 1:
                logger.warning(f"Multiple elements ({count}) found for {selector}. Attempting multi-match recovery...")
                for i in range(count):
                    loc = locators.nth(i)
                    if await loc.is_visible():
                        locator = loc
                        break
                if not locator:
                    locator = locators.first
            else:
                locator = locators.first
            
            # Wait briefly for element to be attached/visible
            await locator.wait_for(state="attached", timeout=5000)

            if action.action == "click":
                await locator.click(timeout=5000)
                # If navigation happens, we might wait for network idle in the reasoning loop
                
            elif action.action == "type":
                if not action.value:
                    logger.error("Type action missing 'value'.")
                    return self._result(action, False, error="Type action missing value.", recovery_hint="provide_type_value", url_before=url_before)
                await locator.fill(action.value, timeout=5000)
                
            elif action.action == "scroll":
                await locator.scroll_into_view_if_needed(timeout=5000)
                
            elif action.action == "extract":
                text = await locator.text_content(timeout=5000)
                logger.info(f"Extracted Text: {text}")
                return self._result(action, True, value=text, url_before=url_before)

            elif action.action == "hover":
                await locator.hover(timeout=5000)
                
            elif action.action == "drag_to":
                if not action.value:
                    logger.error("drag_to requires 'value' (the target element id/text).")
                    return self._result(action, False, error="drag_to requires value target.", recovery_hint="provide_drag_destination", url_before=url_before)
                target_selector = f"[data-playwright-id='{action.value}']" if action.value.startswith("pw-id-") else f"text={action.value}"
                target_loc = self.page.locator(target_selector).first
                await locator.drag_to(target_loc, timeout=5000)
                
            elif action.action == "press_key":
                if not action.value:
                    logger.error("press_key requires 'value' (e.g. 'Enter').")
                    return self._result(action, False, error="press_key requires value.", recovery_hint="provide_key_name", url_before=url_before)
                await locator.press(action.value, timeout=5000)
                
            elif action.action == "select":
                if not action.value:
                    logger.error("select requires 'value' (option label/value).")
                    return self._result(action, False, error="select requires value.", recovery_hint="provide_option_label", url_before=url_before)
                await locator.select_option(label=action.value, timeout=5000)

            else:
                logger.warning(f"Unsupported action: {action.action}")
                return self._result(action, False, error=f"Unsupported action: {action.action}", recovery_hint="choose_supported_action", url_before=url_before)

            return self._result(action, True, url_before=url_before)

        except Exception as e:
            logger.error(f"Failed to execute action '{action.action}' on '{action.target}': {e}")
            return self._result(action, False, error=str(e), recovery_hint="retry_scroll_or_vision", url_before=url_before)
