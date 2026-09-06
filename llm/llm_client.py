import json
import os
import base64
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

    async def generate_vision_json(self, image_path: str, prompt: str) -> dict:
        """
        Sends a screenshot to the Vision LLM (llama-3.2-90b-vision-preview) and requests JSON response.
        """
        logger.info("Generating Vision fallback coordinates with Groq Vision...")
        
        try:
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
            response = await self.client.chat.completions.create(
                model="llama-3.2-90b-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt + "\n\nProvide ONLY a valid JSON object matching this schema: {\"x\": <int>, \"y\": <int>}. Give the X and Y coordinates to click to accomplish the goal on this screen."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}",
                                },
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            content = response.choices[0].message.content
            logger.debug(f"Vision LLM Raw Output: {content}")
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"Vision LLM request failed: {e}")
            return {}
