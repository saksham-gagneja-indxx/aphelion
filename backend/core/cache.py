"""
Redis cache integration using Upstash.
"""

import redis
import os
from typing import Any, Optional
from backend.utils.logger import get_logger

logger = get_logger("cache")


class RedisCache:
    """Redis cache client for session and data caching."""

    def __init__(self):
        """Initialize Redis connection."""
        self.redis_url = os.getenv("REDIS_URL")
        self.rest_url = os.getenv("UPSTASH_REDIS_REST_URL")
        self.rest_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
        self.client = None

    def connect(self):
        """Connect to Redis."""
        if not self.redis_url and not (self.rest_url and self.rest_token):
            logger.warning("Redis not configured - caching disabled")
            return False

        try:
            if self.redis_url:
                # Direct connection
                self.client = redis.from_url(self.redis_url, decode_responses=True)
            else:
                # REST API connection (Upstash)
                import requests
                self.client = None  # Use REST API directly
                logger.info("Using Upstash Redis REST API")

            # Test connection
            if self.client:
                self.client.ping()
            else:
                self._test_rest_connection()

            logger.info("Redis cache connected")
            return True

        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            return False

    def _test_rest_connection(self):
        """Test REST API connection."""
        import requests
        headers = {"Authorization": f"Bearer {self.rest_token}"}
        response = requests.get(f"{self.rest_url}/ping", headers=headers)
        if response.status_code != 200:
            raise Exception(f"Redis REST API error: {response.text}")

    def set(self, key: str, value: Any, ex: int = 3600) -> bool:
        """Set key-value pair in cache."""
        if not self.client:
            return self._set_rest(key, value, ex)

        try:
            self.client.setex(key, ex, str(value))
            return True
        except Exception as e:
            logger.error(f"Cache set failed: {e}")
            return False

    def _set_rest(self, key: str, value: Any, ex: int = 3600) -> bool:
        """Set using REST API."""
        import requests
        import json

        headers = {
            "Authorization": f"Bearer {self.rest_token}",
            "Content-Type": "application/json",
        }

        data = {
            "commands": [["SETEX", key, str(ex), json.dumps(value)]]
        }

        try:
            response = requests.post(self.rest_url, json=data, headers=headers)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Cache set (REST) failed: {e}")
            return False

    def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        if not self.client:
            return self._get_rest(key)

        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            return None

    def _get_rest(self, key: str) -> Optional[str]:
        """Get using REST API."""
        import requests

        headers = {
            "Authorization": f"Bearer {self.rest_token}",
            "Content-Type": "application/json",
        }

        data = {"commands": [["GET", key]]}

        try:
            response = requests.post(self.rest_url, json=data, headers=headers)
            if response.status_code == 200:
                result = response.json()
                if result and result.get("result"):
                    return result["result"][0]
            return None
        except Exception as e:
            logger.error(f"Cache get (REST) failed: {e}")
            return None

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.client:
            return self._delete_rest(key)

        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete failed: {e}")
            return False

    def _delete_rest(self, key: str) -> bool:
        """Delete using REST API."""
        import requests

        headers = {
            "Authorization": f"Bearer {self.rest_token}",
            "Content-Type": "application/json",
        }

        data = {"commands": [["DEL", key]]}

        try:
            response = requests.post(self.rest_url, json=data, headers=headers)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Cache delete (REST) failed: {e}")
            return False

    def flush(self) -> bool:
        """Clear all cache."""
        if not self.client:
            return self._flush_rest()

        try:
            self.client.flushdb()
            return True
        except Exception as e:
            logger.error(f"Cache flush failed: {e}")
            return False

    def _flush_rest(self) -> bool:
        """Clear cache using REST API."""
        import requests

        headers = {
            "Authorization": f"Bearer {self.rest_token}",
            "Content-Type": "application/json",
        }

        data = {"commands": [["FLUSHDB"]]}

        try:
            response = requests.post(self.rest_url, json=data, headers=headers)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Cache flush (REST) failed: {e}")
            return False


# Global cache instance
_cache = None


def get_cache() -> RedisCache:
    """Get or create cache instance."""
    global _cache
    if _cache is None:
        _cache = RedisCache()
        _cache.connect()
    return _cache


def init_cache():
    """Initialize cache on startup."""
    cache = get_cache()
    if cache.client or cache.rest_url:
        logger.info("Cache initialized")
    else:
        logger.warning("Cache not available - operations will not be cached")
