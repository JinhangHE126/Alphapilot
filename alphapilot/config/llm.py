import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

"""
    Multi-Model Support
"""


def get_llm(temperature: float = 0.1):
    return ChatGoogleGenerativeAI(
        model=os.getenv("GOOGLE_MODEL", "gemini-3.1-flash-lite-preview"),
        api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=temperature,
    )