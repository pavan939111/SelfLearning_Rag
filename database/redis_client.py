import redis
from tenacity import retry, stop_after_attempt, wait_fixed
from config import get_config
from utils.logger import get_logger

config = get_config()
logger = get_logger(__name__, level=config.log_level)

class RedisManager:
    def __init__(self):
        try:
            # Use rediss:// for SSL support (required by Upstash)
            url = config.redis_url
            if not url.startswith("rediss://") and "upstash.io" in url:
                url = url.replace("redis://", "rediss://")
            
            # For redis-py 5.x, the 'ssl' argument can conflict with rediss:// in from_url
            self.client = redis.from_url(
                url, 
                password=config.redis_password,
                decode_responses=True
            )
            logger.info("Initialized Redis client")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            self.client = None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def test_connection(self) -> bool:
        """
        Tests connection to Redis using ping().
        """
        if not self.client:
            return False
        try:
            if self.client.ping():
                logger.info("Redis Upstash: OK - CONNECTED")
                return True
            return False
        except Exception as e:
            logger.error(f"Redis Upstash: FAIL - {e}")
            return False
