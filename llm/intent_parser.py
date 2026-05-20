from pydantic import BaseModel
from typing import Optional
from loguru import logger
from .llm_client import LLMClient
import json

class ParsedIntent(BaseModel):
    website: Optional[str] = None
    website_url: Optional[str] = None
    intent: str
    query: str

class IntentParser:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def parse(self, user_query: str) -> ParsedIntent:
        """
        Parses the user query to extract the target website, intent, and parameters.
        """
        logger.info(f"Parsing user query: '{user_query}'")
        
        system_prompt = f"""
        You are an intelligent intent parser for a browser automation agent.
        Your job is to extract structured information from the user's natural language request.
        
        Extract the following and return ONLY a valid JSON object matching this schema:
        {{
            "website": "The name of the target website (e.g., 'amazon', 'google', 'wikipedia'). Null if not specified.",
            "website_url": "The likely starting URL for this website (e.g., 'https://www.amazon.com'). Null if unknown.",
            "intent": "A short string describing the main action (e.g., 'search_product', 'read_article', 'login').",
            "query": "The main subject or search term."
        }}
        """
        
        response_json = await self.llm_client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_query
        )
        
        try:
            parsed = ParsedIntent(**response_json)
            logger.info(f"Parsed Intent: {parsed.model_dump_json()}")
            return parsed
        except Exception as e:
            logger.error(f"Failed to parse LLM output into Intent model: {e}")
            # Fallback
            return ParsedIntent(intent="unknown", query=user_query)
