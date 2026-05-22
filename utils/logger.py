import sys
from loguru import logger

def get_logger(name: str, level: str = "INFO"):
    """
    Configures and returns a loguru logger instance.
    """
    # Remove default handler
    logger.remove()
    
    # Add colored console handler
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan> | <level>{message}</level>",
        level=level,
        colorize=True
    )
    
    return logger.bind(name=name)
