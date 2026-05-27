import os
from pathlib import Path
from functools import lru_cache

# Global Header Constants
SEMANTIC_SCHOLAR_HEADERS = {
    "x-api-key": None
}

SEMANTIC_SCHOLAR_RATE_LIMIT = 1.1

@lru_cache()
def get_config():
  
  # Try environment variables first (Render deployment)
  qdrant_url = os.environ.get('QDRANT_URL', '')
  qdrant_api_key = os.environ.get('QDRANT_API_KEY', '')
  supabase_url = os.environ.get('SUPABASE_URL', '')
  supabase_key = os.environ.get('SUPABASE_KEY', '')
  gemini_api_key = os.environ.get('GEMINI_API_KEY', '')
  neo4j_uri = os.environ.get('NEO4J_URI', '')
  neo4j_username = os.environ.get('NEO4J_USERNAME', 'neo4j')
  neo4j_password = os.environ.get('NEO4J_PASSWORD', '')
  redis_url = os.environ.get('REDIS_URL', '')
  redis_password = os.environ.get('REDIS_PASSWORD', '')
  semantic_scholar_key = os.environ.get(
      'SEMANTIC_SCHOLAR_API_KEY', ''
  )
  
  api_keys = []
  gemini_api_keys = []
  
  for i in range(1, 10):
      val = os.environ.get(f'API_KEY_{i}')
      if val: api_keys.append(val)
      val2 = os.environ.get(f'GEMINI_API_KEY_{i}')
      if val2: gemini_api_keys.append(val2)
  
  # If not in environment, try keys.txt (local dev)
  if not qdrant_url:
    keys_file = Path(__file__).parent / 'keys.txt'
    if keys_file.exists():
      with open(keys_file) as f:
        for line in f:
          line = line.strip()
          if '=' in line and not line.startswith('#'):
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            if key == 'QDRANT_URL':
              qdrant_url = value
            elif key == 'QDRANT_API_KEY':
              qdrant_api_key = value
            elif key == 'SUPABASE_URL':
              supabase_url = value
            elif key == 'SUPABASE_KEY':
              supabase_key = value
            elif key == 'GEMINI_API_KEY':
              gemini_api_key = value
            elif key == 'NEO4J_URI':
              neo4j_uri = value
            elif key == 'NEO4J_USERNAME':
              neo4j_username = value
            elif key == 'NEO4J_PASSWORD':
              neo4j_password = value
            elif key == 'REDIS_URL':
              redis_url = value
            elif key == 'REDIS_PASSWORD':
              redis_password = value
            elif key == 'SEMANTIC_SCHOLAR_API_KEY':
              semantic_scholar_key = value
            elif key.startswith('API_KEY_'):
              api_keys.append(value)
            elif key.startswith('GEMINI_API_KEY_'):
              gemini_api_keys.append(value)
  
  class Config:
    pass
  
  config = Config()
  config.qdrant_url = qdrant_url
  config.qdrant_api_key = qdrant_api_key
  config.supabase_url = supabase_url
  config.supabase_key = supabase_key
  config.gemini_api_key = gemini_api_key
  config.neo4j_uri = neo4j_uri
  config.neo4j_username = neo4j_username
  config.neo4j_password = neo4j_password
  config.redis_url = redis_url
  config.redis_password = redis_password
  config.semantic_scholar_api_key = semantic_scholar_key
  config.api_keys = api_keys
  config.gemini_api_keys = gemini_api_keys
  config.log_level = 'INFO'
  
  SEMANTIC_SCHOLAR_HEADERS["x-api-key"] = semantic_scholar_key
  
  return config
