"""
Live check: run the browsing agent once, headless, against a real site and
the real Groq API. Not a unit test; run it by hand:

    python scripts/live_agent_run.py
    python scripts/live_agent_run.py "search running shoes on flipkart"
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == "win32":
    # Playwright starts a subprocess, which needs the Proactor loop on Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from loguru import logger

from agents.reasoning_agent import ReasoningAgent

DEFAULT_TASK = "go to books.toscrape.com and extract the title and price of the first book you see"


async def main(task: str):
    logger.info(f"Live agent run: {task}")
    agent = ReasoningAgent(headless=True, max_iterations=15)
    result = await agent.execute_task(task)
    logger.info(f"completed={result.completed} reason={result.reason} iterations={result.iterations}")


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or DEFAULT_TASK))
