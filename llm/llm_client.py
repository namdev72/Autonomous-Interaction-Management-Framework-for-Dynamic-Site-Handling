import base64
import asyncio
import json
import os
import re
import time
from pathlib import Path

from loguru import logger
from openai import AsyncOpenAI
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DEFAULT_MODEL = "qwen/qwen3.8-27b"
RETIRED_MODEL_REPLACEMENTS = {
    "llama-3.3-70b-versatile": DEFAULT_MODEL,
}
# Per-minute limits reset within a minute; a daily limit does not, so waiting
# for it would only hang the run.
MAX_RATE_LIMIT_WAIT = 65
MAX_RATE_LIMIT_RETRIES = 4


def rate_limit_wait(error: Exception):
    """Seconds until a 429 rate limit resets, or None if this is not one."""
    if getattr(error, "status_code", None) != 429:
        return None
    headers = getattr(getattr(error, "response", None), "headers", None) or {}
    try:
        return float(headers.get("retry-after")) + 0.5
    except (TypeError, ValueError):
        pass
    # Groq also says it in the message: "Please try again in 1m2.5s" / "in 7.66s".
    match = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", str(error))
    if match and any(match.groups()):
        hours, minutes, seconds = (float(group or 0) for group in match.groups())
        return hours * 3600 + minutes * 60 + seconds + 0.5
    return 10.0


def json_generation_failure(error: Exception):
    """
    The model's reply when Groq rejected it as not being JSON
    (json_validate_failed), or None for any other error.
    """
    body = getattr(error, "body", None)
    info = body.get("error", body) if isinstance(body, dict) else None
    if isinstance(info, dict) and info.get("code") == "json_validate_failed":
        return str(info.get("failed_generation") or "")
    return None


def _json_object_in(text: str):
    """The JSON object inside a reply that wraps it in prose, or None."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def configured_api_keys() -> list[str]:
    """GROQ_API_KEY, then GROQ_API_KEY_2, GROQ_API_KEY_3, ... in that order."""
    def order(name: str) -> int:
        suffix = name.rsplit("_", 1)[-1]
        return int(suffix) if suffix.isdigit() else 1

    names = sorted((name for name in os.environ if re.fullmatch(r"GROQ_API_KEY(?:_\d+)?", name)), key=order)
    keys = []
    for name in names:
        key = os.environ[name].strip()
        if key and key not in keys:
            keys.append(key)
    return keys


# When each rate-limited key can be used again (time.monotonic()). Shared by
# every client in the process, so a new run does not start on a blocked key.
KEY_COOLDOWNS: dict[str, float] = {}


class LLMClient:
    def __init__(self, model_name: str = None, max_retries: int = 3):
        self.api_keys = configured_api_keys()
        self._clients: dict[str, AsyncOpenAI] = {}
        self.api_key = self._first_available_key()
        configured_model = (model_name or os.getenv("MODEL_NAME") or DEFAULT_MODEL).strip()
        self.model_name = RETIRED_MODEL_REPLACEMENTS.get(configured_model, configured_model)
        self.vision_model_name = (os.getenv("VISION_MODEL_NAME") or "").strip() or None
        self.max_retries = max_retries
        self.client = None

        if configured_model != self.model_name:
            logger.warning(
                f"Groq model '{configured_model}' is retired or unavailable; "
                f"using '{self.model_name}' instead."
            )
        model_source = "CLI" if model_name else ("environment" if os.getenv("MODEL_NAME") else "default")
        logger.info(f"Configured Groq text model: {self.model_name} (source: {model_source})")
        
        if not self.api_key:
            logger.warning("GROQ_API_KEY not found in environment.")
            return

        if len(self.api_keys) > 1:
            logger.info(f"{len(self.api_keys)} Groq API keys configured; rotating on rate limits.")
        self.client = self._client_for(self.api_key)

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def _client_for(self, key: str) -> AsyncOpenAI:
        if key not in self._clients:
            self._clients[key] = AsyncOpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
        return self._clients[key]

    def _key_label(self, key: str) -> str:
        # Keys are never logged, only their position.
        return f"key {self.api_keys.index(key) + 1} of {len(self.api_keys)}"

    def _first_available_key(self):
        if not self.api_keys:
            return None
        now = time.monotonic()
        return next((key for key in self.api_keys if KEY_COOLDOWNS.get(key, 0) <= now), self.api_keys[0])

    def _use_key(self, key: str):
        self.api_key = key
        self.client = self._client_for(key)

    def _rotate_after_rate_limit(self, wait: float) -> bool:
        """Put the current key on cooldown and switch to a free one; False if none is free."""
        KEY_COOLDOWNS[self.api_key] = time.monotonic() + wait
        now = time.monotonic()
        start = self.api_keys.index(self.api_key)
        for offset in range(1, len(self.api_keys)):
            key = self.api_keys[(start + offset) % len(self.api_keys)]
            if KEY_COOLDOWNS.get(key, 0) <= now:
                logger.warning(f"Groq rate limit on {self._key_label(self.api_key)}; switching to {self._key_label(key)}.")
                self._use_key(key)
                return True
        return False

    async def _chat_completion_with_retry(self, **kwargs):
        last_error = None
        attempt = 0
        rate_limit_waits = 0
        while True:
            attempt += 1
            try:
                return await self.client.chat.completions.create(**kwargs)
            except Exception as e:
                last_error = e
                # A rate limit is not a failure to retry quickly: Groq's limits
                # are per minute, so 1-2 s retries all fail and the agent then
                # loops on empty responses. Wait for the window to reset.
                wait = rate_limit_wait(e)
                if wait is not None:
                    # Another key is the fastest fix; waiting is the fallback
                    # when every key is limited.
                    if self._rotate_after_rate_limit(wait):
                        continue
                    soonest = min(self.api_keys, key=lambda key: KEY_COOLDOWNS.get(key, 0))
                    wait = max(KEY_COOLDOWNS.get(soonest, 0) - time.monotonic(), 0)
                    if wait > MAX_RATE_LIMIT_WAIT or rate_limit_waits >= MAX_RATE_LIMIT_RETRIES:
                        logger.error(f"Groq rate limit reached on all {len(self.api_keys)} key(s); "
                                     f"the next is free in {wait:.0f}s, not waiting.")
                        break
                    rate_limit_waits += 1
                    logger.warning(f"Groq rate limit reached on all {len(self.api_keys)} key(s); "
                                   f"waiting {wait:.0f}s for {self._key_label(soonest)}.")
                    await asyncio.sleep(wait)
                    self._use_key(soonest)
                    continue
                # At temperature 0 the same request gets the same prose back,
                # so retrying it unchanged only adds delay; generate_json
                # asks again with the rejected reply in view instead.
                if attempt >= self.max_retries or json_generation_failure(e) is not None:
                    break
                delay = min(2 ** (attempt - 1), 8)
                logger.warning(f"LLM request failed on attempt {attempt}; retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
        raise last_error
        
    async def generate_json(self, system_prompt: str, user_prompt: str, response_model: BaseModel = None) -> dict:
        """
        Sends prompts to the LLM and requests a JSON response.
        If a response_model is provided, the LLM is instructed to match its schema.
        """
        logger.info(f"Generating JSON with Groq LLM (Model: {self.model_name})...")
        if not self.is_configured:
            logger.error("Cannot generate JSON because GROQ_API_KEY is not configured.")
            return {}
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        for attempt in range(2):
            try:
                response = await self._chat_completion_with_retry(
                    model=self.model_name,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.0 # Deterministic actions
                )
                content = response.choices[0].message.content
                logger.debug(f"LLM Raw Output: {content}")
                return json.loads(content)
            except Exception as e:
                failed = json_generation_failure(e)
                if failed is None:
                    logger.error(f"LLM request failed: {e}")
                    return {}
                recovered = _json_object_in(failed)
                if recovered is not None:
                    logger.warning("LLM wrapped its JSON in prose; using the JSON.")
                    return recovered
                if attempt == 1:
                    logger.error(f"LLM replied in prose again instead of JSON: {failed[:200]}")
                    return {}
                # Show the model its own reply and ask for the JSON alone.
                logger.warning("LLM replied in prose instead of JSON; asking once more for JSON only.")
                messages = messages + [
                    {"role": "assistant", "content": failed},
                    {"role": "user", "content": "That reply was not JSON. Reply again with only the JSON "
                                                "object, in the format the system message gives, and nothing else."},
                ]
        return {}

    async def generate_vision_json(self, image_path: str, prompt: str) -> dict:
        """
        Sends a screenshot to the configured Vision LLM and requests a JSON response.
        """
        logger.info("Generating Vision fallback coordinates with Groq Vision...")
        if not self.is_configured:
            logger.error("Cannot generate vision JSON because GROQ_API_KEY is not configured.")
            return {}
        
        try:
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
            if not self.vision_model_name:
                logger.error("VISION_MODEL_NAME is not configured; vision fallback is disabled.")
                return {}

            response = await self._chat_completion_with_retry(
                model=self.vision_model_name,
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
