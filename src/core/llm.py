# src/core/llm.py
# LLM configuration and instantiation

import os
from llama_index.llms.openai_like import OpenAILike
from loguru import logger
from dotenv import load_dotenv

def get_llm():
    """
    Initializes and returns the LLM instance based on environment variables.
    """
    load_dotenv()
    llm = OpenAILike(
        model=os.environ.get("NEBIUS_LLM", "Qwen/Qwen3-30B-A3B"),
        api_base=os.environ.get("NEBIUS_API_BASE", "https://api.studio.nebius.com/v1/"),
        api_key=os.environ.get("NEBIUS_API_KEY"),
        is_chat_model=True,
        context_window=os.environ.get("NEBIUS_CONTEXT_WINDOW", 41000),
        temperature=os.environ.get("NEBIUS_TEMPERATURE", 0.001),

    )
    if not llm.api_key:
        logger.warning("NEBIUS_API_KEY environment variable not set. LLM calls will likely fail.")
    else:
        logger.info(f"LLM initialized: {llm.model} from {llm.api_base}")
    return llm
