from langchain_openai import ChatOpenAI
import os

def get_model():
    return ChatOpenAI(
        api_key=os.environ.get("NOVITA_KEY"),
        base_url="https://api.novita.ai/openai",
        max_tokens=262144,
        temperature=0.7
    )