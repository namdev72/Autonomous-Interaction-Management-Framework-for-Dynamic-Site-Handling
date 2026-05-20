import asyncio
import sys
from loguru import logger
from agents.reasoning_agent import ReasoningAgent

async def main():
    logger.info("Initializing Autonomous Web Agent Framework...")
    
    # Configure logger to be a bit cleaner or save to file
    logger.add("execution_history.log", rotation="10 MB")
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        print("\n" + "═" * 60)
        print("        🤖 AUTONOMOUS WEB BROWSER AGENT (CLI MODE)        ")
        print("═" * 60)
        print(" Examples:")
        print("  • \"open amazon website and search for iphone 16\"")
        print("  • \"go to books.toscrape.com and extract the price of a light in the attic\"")
        print("" + "═" * 60)
        query = input("\nEnter your browser task: ")
        
    if not query.strip():
        logger.error("Empty query provided. Exiting.")
        return
        
    # Run headful so the user can watch the browser actions
    agent = ReasoningAgent(headless=False, max_iterations=15)
    await agent.execute_task(query)

if __name__ == "__main__":
    asyncio.run(main())
