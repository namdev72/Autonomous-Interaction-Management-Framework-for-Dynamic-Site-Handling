from loguru import logger
from browser.controller import BrowserController
from browser.dom_extractor import DOMExtractor
from browser.actions import BrowserExecutor
from llm.llm_client import LLMClient
from llm.intent_parser import IntentParser
from context.context_builder import ContextBuilder
from memory.history import MemoryState
from models.action_models import AgentAction
import asyncio
import base64
import os
import time
from typing import Callable, Awaitable, Optional

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
        logger.info(f"🤖 Action: {action.upper()} | Target: {target} | Value: {value}")
        logger.info(f"💭 Reasoning: {reasoning}")
    elif event_type == "extraction":
        key = data.get("key")
        value = data.get("value")
        logger.success(f"💡 Extracted Data [{key}]: {value}")

class ReasoningAgent:
    def __init__(self, headless: bool = False, max_iterations: int = 15, on_event: Optional[Callable[[str, dict], Awaitable[None]]] = None):
        self.browser_controller = BrowserController(headless=headless)
        self.llm_client = LLMClient()
        self.intent_parser = IntentParser(self.llm_client)
        self.context_builder = ContextBuilder()
        self.memory = MemoryState()
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

    async def execute_task(self, user_query: str):
        logger.info(f"Starting agent task: {user_query}")
        await self._emit_log(f"Starting task: {user_query}")
        
        # Step 1: Parse intent
        intent = await self.intent_parser.parse(user_query)
        await self._emit_log(f"Parsed Intent: {intent.model_dump_json()}")
        
        if not intent.website_url:
            import urllib.parse
            query_encoded = urllib.parse.quote(user_query)
            intent.website_url = f"https://duckduckgo.com/?q={query_encoded}"
            await self._emit_log(f"Falling back to web search for: {user_query}", "warning")

        # Step 2: Open Browser and Navigate
        await self._emit_log(f"Launching browser and navigating to {intent.website_url}...")
        success = await self.browser_controller.open_website(intent.website_url)
        if not success:
            await self._emit_log("Failed to load website. Aborting.", "error")
            await self.browser_controller.close_browser()
            return
            
        await self.browser_controller.wait_for_load()
        executor = BrowserExecutor(self.browser_controller.page)

        # Autonomous Loop
        iterations = 0
        done = False
        
        while not done and iterations < self.max_iterations:
            iterations += 1
            logger.info(f"--- Iteration {iterations} ---")
            await self._emit_log(f"--- Iteration {iterations} ---")
            
            # Step 3: Extract DOM
            dom_extractor = DOMExtractor(self.browser_controller.page)
            elements = await dom_extractor.extract_interactive_elements()
            await self._emit_log(f"Extracted {len(elements)} interactive DOM elements.")
            
            current_url = self.browser_controller.page.url
            self.memory.add_url(current_url)
            
            # Step 4: Build Context
            page_context = self.context_builder.build_context(current_url, elements)
            self.memory.index_page_content(current_url, page_context)
            memory_context = self.memory.get_context_string()
            
            system_prompt = f"""
            You are an autonomous web browser agent. 
            Your goal is: {user_query}
            
            IMPORTANT: You are only seeing the elements CURRENTLY VISIBLE on the screen (the viewport). 
            If you cannot find your target, you MUST use the 'scroll' action to look further down the page!
            
            You have the ability to execute the following actions:
            - click: Clicks on a target element.
            - type: Types text into a target input. Provide the text in 'value'.
            - scroll: Scrolls the target element into view.
            - wait: Waits for 'value' seconds (default 2).
            - navigate: Navigates to the URL in 'value'.
            - extract: Extracts text content from the target element.
            - back: Goes to the previous page.
            - done: Call this when the user's goal has been completely achieved.
            
            For actions requiring a target (click, type, extract, scroll), you MUST provide the EXACT 'playwright_index' (e.g. 'pw-id-3') from the context.
            If the element you need to interact with is NOT listed in the Available Interactive Elements (for example, if it's hidden inside an iframe, like a captcha or a complex widget), you MUST set "fallback_to_vision" to true and set "action" to "click".
            
            Respond ONLY with a valid JSON object matching this schema:
            {{
                "action": "<action_type>",
                "target": "<playwright_index_or_null>",
                "value": "<value_or_null>",
                "reasoning": "<brief_reasoning>",
                "fallback_to_vision": <boolean>
            }}
            """
            
            user_prompt = f"{memory_context}\n\nCurrent Page Context:\n{page_context}"
            
            await self._emit_log("Querying LLM for next action...")
            response_json = await self.llm_client.generate_json(system_prompt, user_prompt)
            
            if not response_json:
                await self._emit_log("Empty response from LLM. Retrying...", "warning")
                await asyncio.sleep(2)
                continue
                
            try:
                action = AgentAction(**response_json)
                await self._emit_log(f"Decided Action: {action.action} on {action.target} (Reasoning: {action.reasoning})", "success")
                await self._emit("action", action.model_dump())
                
                # Save to history
                self.memory.add_action(action)
                self.memory.save_state()
                
                if self.memory.detect_loop():
                    await self._emit_log("Detected loop of identical actions. Breaking loop...", "warning")
                    action.action = "scroll"
                    action.target = None
                
                # Execute Action
                action_success = await executor.execute(action)
                
                if not action_success or action.fallback_to_vision:
                    await self._emit_log("Execution failed or vision fallback requested. Triggering Vision Fallback...", "warning")
                    screenshot_path = await self._emit_screenshot(name_prefix="vision_fallback")
                    if screenshot_path:
                        vision_json = await self.llm_client.generate_vision_json(screenshot_path, user_prompt)
                        if vision_json and "x" in vision_json and "y" in vision_json:
                            action.x = vision_json["x"]
                            action.y = vision_json["y"]
                            action_success = await executor.execute(action)
                        else:
                            await self._emit_log("Vision LLM failed to return valid coordinates.", "error")
                    else:
                        await self._emit_log("Failed to take screenshot for Vision fallback.", "error")
                    
                if action.action == "done":
                    done = True
                    await self._emit_log("Goal achieved according to the agent.", "success")
                    break
                    
                if action.action == "extract" and action_success:
                    key = f"Extraction_Iter_{iterations}"
                    self.memory.store_extracted_data(key, action_success)
                    await self._emit_log(f"Extracted: {action_success}", "success")
                    await self._emit("extraction", {"key": key, "value": action_success})
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to parse or execute action: {e}")
                await self._emit_log(f"Error executing action: {e}", "error")
                await asyncio.sleep(2)
        
        if not done:
            await self._emit_log("Reached maximum iterations before achieving the goal.", "warning")
            
        await self._emit_log("Task execution finished. Keeping browser open for 5 seconds for visual inspection.")
        await asyncio.sleep(5)
        await self.browser_controller.close_browser()
