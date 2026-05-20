import json
import os
from loguru import logger
from pydantic import BaseModel
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model_name = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
        
        if not self.api_key:
            logger.warning("GROQ_API_KEY not found in environment.")
            
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        
    async def generate_json(self, system_prompt: str, user_prompt: str, response_model: BaseModel = None) -> dict:
        """
        Sends prompts to the LLM and requests a JSON response.
        If a response_model is provided, the LLM is instructed to match its schema.
        """
        logger.info(f"Generating JSON with Groq LLM (Model: {self.model_name})...")
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0 # Deterministic actions
            )
            
            content = response.choices[0].message.content
            logger.debug(f"LLM Raw Output: {content}")
            
            # Parse the string content to dict
            return json.loads(content)
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return {}
