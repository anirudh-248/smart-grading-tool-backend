import redis.asyncio as redis
import logging
from env import env
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RedisClientManager:
    def __init__(self):
        self.client: Optional[redis.Redis] = None

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_fixed(30),
        retry=retry_if_exception_type((
            redis.ConnectionError,
            redis.AuthenticationError,
            redis.TimeoutError,
        )),
        before=lambda retry_state: logger.warning(
            "Retrying Redis connection attempt %d...", retry_state.attempt_number
        ),
        after=lambda retry_state: logger.error(
            "Failed to connect to Redis after %d attempts", retry_state.attempt_number
        ) if retry_state.outcome.failed else None
    )
    async def _connect_with_retry(self) -> redis.Redis:
        """
        Attempt to create and connect to a Redis instance with retry logic.
        """
        client = None
        try:
            client = redis.Redis(
                host=env.REDIS_HOST,
                port=int(env.REDIS_PORT),
                password=env.REDIS_PASSWORD,
                db=0,
                decode_responses=True
            )
            await client.ping()
            logger.info("Successfully connected to Redis")
            return client
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error("Failed to connect to Redis: %s", str(e))
            if client:
                await client.close()
            raise

    async def connect(self) -> bool:
        """
        Establishes connection with Redis server asynchronously.
        Returns True if connection is successful.
        """
        try:
            self.client = await self._connect_with_retry()
            return True
        except Exception:
            self.client = None
            return False

    async def disconnect(self):
        """Closes the Redis connection asynchronously."""
        if self.client:
            try:
                await self.client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error("Error closing Redis connection: %s", str(e))
            finally:
                self.client = None
        else:
            logger.info("No Redis connection to close")

    async def get_client(self) -> Optional[redis.Redis]:
        """Returns the Redis client instance asynchronously."""
        if self.client is None:
            await self.connect()
        return self.client

# Create singleton instance
redis_handler = RedisClientManager()
