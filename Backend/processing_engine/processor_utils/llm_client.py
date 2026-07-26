import os
import asyncio
import json
from pathlib import Path
from openai import OpenAI, AsyncOpenAI
from openai import RateLimitError, APIStatusError, APITimeoutError
from utils import load_env, get_logger

logger = get_logger(__name__)
load_env()

CURRENT_DIR = Path(__file__).parent
config_path = CURRENT_DIR / "llm_configs.json"
with open(config_path, 'r') as f:
    configs = json.load(f)

RETRYABLE_ERRORS = (RateLimitError, APITimeoutError)
MAX_RETRIES = 3
BASE_DELAY = 2.0

class LLMClient:
    def __init__(self, model: str):
        if model not in configs:
            raise ValueError(f"Model not configured: {model}")
        
        self.model = model
        self.config = configs[model]
        self._client = self._create_client()

    def _create_client(self) -> OpenAI:
        """Create an OpenAI client with the configured key and base_url"""
        key = os.getenv(self.config.get("api_key_name"))
        if not key:
            raise ValueError(f"API key not found for {self.config.get('api_key_name')}")
        
        url = self.config.get("base_url")
        return OpenAI(api_key=key, base_url=url)
    
    def call(self, messages, **kwargs):
        """Make a sync call to the LLM"""
        params = {**self.config["default_params"], **kwargs}
        
        response = self._client.chat.completions.create(
            model=self.config["model"],
            messages=messages,
            **params
        )
        return response.choices[0].message.content


class AsyncLLMClient:
    def __init__(self, model: str):
        if model not in configs:
            raise ValueError(f"Model not configured: {model}")
        
        self.model = model
        self.config = configs[model]
        self._client = self._create_client()

    def _create_client(self) -> AsyncOpenAI:
        """Create an OpenAI client with the configured key and base_url"""
        key = os.getenv(self.config.get("api_key_name"))
        if not key:
            raise ValueError(f"API key not found for {self.config.get('api_key_name')}")
        
        url = self.config.get("base_url")
        return AsyncOpenAI(api_key=key, base_url=url)
    
    async def call(self, messages, **kwargs):
        """Make an async call to the LLM with retry on transient errors."""
        params = {**self.config["default_params"], **kwargs}
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self.config["model"],
                    messages=messages,
                    **params
                )
                return response.choices[0].message.content
            except RETRYABLE_ERRORS as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = BASE_DELAY ** (attempt + 1)
                    logger.warning(
                        f"LLM {self.model}: {type(e).__name__}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(delay)
            except APIStatusError as e:
                if e.status_code >= 500:
                    last_error = e
                    if attempt < MAX_RETRIES:
                        delay = BASE_DELAY ** (attempt + 1)
                        logger.warning(
                            f"LLM {self.model}: HTTP {e.status_code}, "
                            f"retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})"
                        )
                        await asyncio.sleep(delay)
                        continue
                raise

        raise last_error