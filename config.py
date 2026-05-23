import os
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache

def parse_keys_txt(filepath: str) -> dict:
    """Parses keys.txt and returns a dictionary of key-value pairs."""
    keys = {}
    if not os.path.exists(filepath):
        return keys
    
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                keys[key.strip()] = value.strip()
    return keys

# Load keys once at module level
keys_from_file = parse_keys_txt("keys.txt")

class Settings(BaseSettings):
    # Vector DB
    qdrant_url: str = keys_from_file.get("QDRANT_URL", "")
    qdrant_api_key: str = keys_from_file.get("QDRANT_API_KEY", "")
    
    # SQL DB & State Management
    supabase_url: str = keys_from_file.get("SUPABASE_URL", "")
    supabase_key: str = keys_from_file.get("SUPABASE_KEY", "")
    
    # LLM
    gemini_api_key: str = keys_from_file.get("GEMINI_API_KEY", "")
    gemini_api_keys: list[str] = [
        keys_from_file.get(f"GEMINI_API_KEY_{i}") 
        for i in range(1, 10) 
        if keys_from_file.get(f"GEMINI_API_KEY_{i}")
    ]
    
    # Graph DB
    neo4j_uri: str = keys_from_file.get("NEO4J_URI", "")
    neo4j_username: str = keys_from_file.get("NEO4J_USERNAME", "")
    neo4j_password: str = keys_from_file.get("NEO4J_PASSWORD", "")
    
    # Priority Queue & Cache
    redis_url: str = keys_from_file.get("REDIS_URL", "")
    redis_password: str = keys_from_file.get("REDIS_PASSWORD", "")
    
    # External APIs
    ncbi_api_key: str = keys_from_file.get("NCBI_API_KEY", "")
    
    # Semantic Scholar is now a required field
    semantic_scholar_api_key: str = Field(default=keys_from_file.get("SEMANTIC_SCHOLAR_API_KEY"))
    
    # Global Config
    log_level: str = keys_from_file.get("LOG_LEVEL", "INFO")
    
    # API Keys for auth
    api_keys: list[str] = [
        keys_from_file.get(f"API_KEY_{i}") 
        for i in range(1, 10) 
        if keys_from_file.get(f"API_KEY_{i}")
    ]

# Global Header Constants
SEMANTIC_SCHOLAR_HEADERS = {
    "x-api-key": None  # Filled at runtime from config
}

SEMANTIC_SCHOLAR_RATE_LIMIT = 1.1  # Seconds between requests

@lru_cache()
def get_config() -> Settings:
    config = Settings()
    
    # Initialize global headers
    SEMANTIC_SCHOLAR_HEADERS["x-api-key"] = config.semantic_scholar_api_key
    
    return config
