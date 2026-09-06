from loguru import logger

from llm.llm_client import LLMClient


class GoalVerifier:
    """Checks whether a proposed done action actually satisfies the user goal."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def verify(self, user_query: str, page_context: str, memory_context: str) -> bool:
        system_prompt = """
        You verify whether a browser automation task is complete.
        Return ONLY a valid JSON object: {"complete": <boolean>, "reason": "<short reason>"}.
        Mark complete only when the user's requested outcome is clearly satisfied by the current page or extracted data.
        """
        user_prompt = f"User goal:\n{user_query}\n\nMemory:\n{memory_context}\n\nCurrent page:\n{page_context}"

        response = await self.llm_client.generate_json(system_prompt, user_prompt)
        complete = bool(response.get("complete")) if response else False
        logger.info(f"Goal verification result: complete={complete}, reason={response.get('reason') if response else 'empty response'}")
        return complete
