# src/core/observability.py
# Observability setup (e.g., Arize Phoenix)

import os
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from phoenix.otel import register
from loguru import logger
from dotenv import load_dotenv

def setup_observability():
    """
    Sets up Arize Phoenix for logging/observability using OpenInference.
    """
    load_dotenv() # Ensure env vars are loaded, e.g., for PHOENIX_COLLECTOR_ENDPOINT

    # Use environment variable for Phoenix endpoint, defaulting if not set
    phoenix_endpoint = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://127.0.0.1:6006")
    os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = phoenix_endpoint # Ensure it's set for Phoenix libs

    logger.info(f"Attempting to initialize Arize Phoenix with OpenInference. Endpoint: {phoenix_endpoint}")
    try:
        tracer_provider = register(set_global_tracer_provider=False)
        LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)
        logger.info("Arize Phoenix instrumentor initialized with LlamaIndex.")
        logger.info(f"Ensure Phoenix is running at {phoenix_endpoint} to view traces.")
    except Exception as e:
        logger.error(f"Failed to initialize Arize Phoenix instrumentor: {e}")
        logger.info("Proceeding without Phoenix observability.")
