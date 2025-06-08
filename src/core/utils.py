from typing import Any
import json
from loguru import logger

def parse_thinking_outputs(agent_response_str: str) -> Any: # Ensure 'Any' is from 'typing'
        try:
            logger.debug(f"parse_thinking_outputs: Received agent response: {agent_response_str}")
            if "</think>" in agent_response_str:
                agent_response_str = agent_response_str.split("</think>")[-1].strip()
            return json.loads(agent_response_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse final aggregation JSON: {e}. Raw response: {agent_response_str}")
            return None