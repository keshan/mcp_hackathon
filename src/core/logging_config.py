import logging
import os

DEFAULT_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logging.basicConfig(level=DEFAULT_LOG_LEVEL, format=LOG_FORMAT)

def get_logger(name: str) -> logging.Logger:
    """Returns a logger instance with the specified name."""
    return logging.getLogger(name)

# Example usage (can be removed or kept for testing):
if __name__ == "__main__":
    logger = get_logger(__name__)
    logger.debug("This is a debug message.")
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.critical("This is a critical message.")
