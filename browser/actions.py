from playwright.async_api import Page
from models.action_models import AgentAction
from loguru import logger
import asyncio

class BrowserExecutor:
    def __init__(self, page: Page):
        self.page = page

    async def execute(self, action: AgentAction) -> bool:
        """
        Executes an action mapped from the LLM's structured output.
        Returns True if successful, False otherwise.
        """
        logger.info(f"Executing action: {action.action} on target: {action.target}")
        
        try:
            if action.action == "done":
                logger.success("Agent signaled task completion.")
                return True
                
            elif action.action == "wait":
                delay = int(action.value) if action.value and action.value.isdigit() else 2
                logger.info(f"Waiting for {delay} seconds...")
                await asyncio.sleep(delay)
                return True
                
            elif action.action == "navigate":
                if not action.value:
                    logger.error("Navigate action missing 'value' URL.")
                    return False
                await self.page.goto(action.value, wait_until="load", timeout=30000)
                return True
                
            elif action.action == "back":
                await self.page.go_back(wait_until="load")
                return True
                
            # For actions that require a target
            if not action.target:
                logger.error(f"Action '{action.action}' requires a target.")
                return False

            # Build a Playwright locator.
            # Prefer our injected data-playwright-id, otherwise fallback to standard text/css
            if action.target.startswith("pw-id-"):
                selector = f"[data-playwright-id='{action.target}']"
            else:
                # If the LLM returned a plain text or generic string, try text locator
                selector = f"text={action.target}"

            locator = self.page.locator(selector).first
            
            # Wait briefly for element to be attached/visible
            await locator.wait_for(state="attached", timeout=5000)

            if action.action == "click":
                await locator.click(timeout=5000)
                # If navigation happens, we might wait for network idle in the reasoning loop
                
            elif action.action == "type":
                if not action.value:
                    logger.error("Type action missing 'value'.")
                    return False
                await locator.fill(action.value, timeout=5000)
                
            elif action.action == "scroll":
                await locator.scroll_into_view_if_needed(timeout=5000)
                
            elif action.action == "extract":
                text = await locator.text_content(timeout=5000)
                logger.info(f"Extracted Text: {text}")
                # Real implementation would save this to memory, which we will do in reasoning agent
                return text

            else:
                logger.warning(f"Unsupported action: {action.action}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to execute action '{action.action}' on '{action.target}': {e}")
            return False
