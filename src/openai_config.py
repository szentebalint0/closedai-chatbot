import os
from dotenv import load_dotenv
from langfuse import openai


def get_llm():
    load_dotenv()
    api_key = os.getenv("API_KEY")
    base_url = os.getenv("BASE_URL")
    if not api_key:
        raise RuntimeError("Missing API_KEY environment variable")
    if not base_url:
        raise RuntimeError("Missing base url")

    return openai.OpenAI(
        api_key=api_key,
        base_url=base_url
    )
