import os
from openai import OpenAI, AsyncOpenAI
from pathlib import Path
from utils import load_env
import json

load_env()

CURRENT_DIR = Path(__file__).parent
config_path = CURRENT_DIR / "llm_configs.json"
with open(config_path, 'r') as f:
    configs = json.load(f)

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
        """Make an async call to the LLM"""
        params = {**self.config["default_params"], **kwargs}
        
        response = await self._client.chat.completions.create(
            model=self.config["model"],
            messages=messages,
            **params
        )
        return response.choices[0].message.content