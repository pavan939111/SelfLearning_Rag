import itertools
from config import get_config
from utils.logger import get_logger

class GeminiKeyManager:
    """
    Manages Gemini API keys using a Round-Robin strategy to distribute load
    across multiple keys and mitigate rate limiting.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GeminiKeyManager, cls).__new__(cls)
            cls._instance._init_manager()
        return cls._instance
    
    def _init_manager(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
        
        # Combine the list of keys and the primary key
        keys = [self.config.gemini_api_key] + self.config.gemini_api_keys
        
        # Deduplicate keys while maintaining order
        seen = set()
        self.keys = [x for x in keys if x and not (x in seen or seen.add(x))]
        
        if not self.keys:
            self.logger.error("No Gemini API keys found in configuration!")
            self.keys = ["NO_KEY_FOUND"]
            
        self.key_cycle = itertools.cycle(self.keys)
        self.logger.info(f"Initialized GeminiKeyManager with {len(self.keys)} unique keys.")

    def get_next_key(self) -> str:
        """Returns the next API key in the cycle for round-robin rotation."""
        return next(self.key_cycle)

def get_gemini_key() -> str:
    """
    Thread-safe convenience function to retrieve the next available Gemini API key.
    """
    return GeminiKeyManager().get_next_key()
