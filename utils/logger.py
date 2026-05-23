import sys
import time
import os
from functools import wraps
from loguru import logger
from contextvars import ContextVar

# Create a ContextVar to hold request_id or session_id
request_id_var = ContextVar("request_id", default=None)
session_id_var = ContextVar("session_id", default=None)

# Define logs directory
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Remove default handler
logger.remove()

# 1. Console Output (Colorized)
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[name]}</cyan> | <level>{message}</level> {extra}",
    level="INFO",
    colorize=True
)

# 2. File Outputs (Structured JSONish or Loguru Format)
file_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[name]} | req={extra[request_id]} sess={extra[session_id]} | {message} | {extra}"

# API Log
logger.add(
    os.path.join(LOGS_DIR, "api.log"),
    format=file_format,
    level="INFO",
    rotation="10 MB",
    retention="10 days"
)

# Agents Log
logger.add(
    os.path.join(LOGS_DIR, "agents.log"),
    format=file_format,
    level="DEBUG",
    rotation="10 MB",
    retention="10 days",
    filter=lambda record: "agents" in record["extra"].get("name", "")
)

# Errors Log
logger.add(
    os.path.join(LOGS_DIR, "errors.log"),
    format=file_format,
    level="ERROR",
    rotation="10 MB",
    retention="30 days"
)

# Benchmark Log
logger.add(
    os.path.join(LOGS_DIR, "benchmark.log"),
    format=file_format,
    level="INFO",
    rotation="10 MB",
    retention="30 days",
    filter=lambda record: "benchmark" in record["extra"].get("name", "")
)

def get_logger(name: str, level: str = "INFO"):
    """
    Returns a logger bound with the module name.
    Dynamically injects ContextVars via a filter or wrapper.
    """
    def context_injector(record):
        req_id = request_id_var.get()
        sess_id = session_id_var.get()
        record["extra"]["request_id"] = req_id if req_id else ""
        record["extra"]["session_id"] = sess_id if sess_id else ""
        
    bound_logger = logger.bind(name=name)
    return bound_logger.patch(context_injector)

def log_performance(func):
    """
    Decorator to log execution time of a method.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            duration_ms = int((time.time() - start) * 1000)
            bound_logger = get_logger(func.__module__)
            bound_logger.info(f"{func.__name__} completed in {duration_ms}ms", duration_ms=duration_ms)

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.time()
        try:
            return await func(*args, **kwargs)
        finally:
            duration_ms = int((time.time() - start) * 1000)
            bound_logger = get_logger(func.__module__)
            bound_logger.info(f"{func.__name__} completed in {duration_ms}ms", duration_ms=duration_ms)

    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return wrapper
