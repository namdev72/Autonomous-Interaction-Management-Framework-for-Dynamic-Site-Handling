import argparse
import asyncio

from loguru import logger

from agents.reasoning_agent import ReasoningAgent


def parse_args():
    parser = argparse.ArgumentParser(description="Autonomous Web Browser Agent Framework")
    parser.add_argument("task", nargs="*", help="Natural language browser task to execute.")
    parser.add_argument("--headless", action="store_true", help="Run Chromium without a visible window.")
    parser.add_argument("--max-iterations", type=int, default=15, help="Maximum autonomous reasoning steps.")
    parser.add_argument("--model", default=None, help="Override the Groq model name for this run.")
    return parser.parse_args()


async def main():
    logger.info("Initializing Autonomous Web Agent Framework...")
    logger.add("execution_history.log", rotation="10 MB")

    args = parse_args()
    query = " ".join(args.task).strip()

    if not query:
        print("\n" + "=" * 60)
        print("        AUTONOMOUS WEB BROWSER AGENT (CLI MODE)")
        print("=" * 60)
        print(" Examples:")
        print('  - "open amazon website and search for iphone 16"')
        print('  - "go to books.toscrape.com and extract the price of a light in the attic"')
        print("=" * 60)
        query = input("\nEnter your browser task: ").strip()

    if not query:
        logger.error("Empty query provided. Exiting.")
        return

    agent = ReasoningAgent(
        headless=args.headless,
        max_iterations=args.max_iterations,
        model_name=args.model,
    )
    result = await agent.execute_task(query)
    logger.info(f"Run result: {result.model_dump_json()}")


if __name__ == "__main__":
    asyncio.run(main())
