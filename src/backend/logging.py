"""
Logging configuration for the Game Insight project.
"""
import logging
from pythonjsonlogger import jsonlogger

def setup_logging():
    """
    Sets up structured JSON logging for the application.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove any existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    logHandler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)
