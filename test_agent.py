import asyncio
from loguru import logger
from agents.reasoning_agent import ReasoningAgent

async def test():
    logger.info("Running Agent Headless Test")
    agent = ReasoningAgent(headless=True, max_iterations=15)
    query = "go to books.toscrape.com and extract the title and price of the first book you see"
    await agent.execute_task(query)

if __name__ == "__main__":
    asyncio.run(test())
