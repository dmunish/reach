"""
Redis caching layer for geocoding service.

Provides fast, distributed caching for:
- Directional query results
- Fuzzy name search results
- External geocoding API responses
- Hierarchical aggregation results
"""

from typing import Optional, Any, List, Dict
import redis.asyncio as redis
import json
import hashlib
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Async Redis cache with automatic serialization/deserialization.
    
    Features:
    - Automatic JSON serialization
    - TTL support for cache expiration
    - Batch operations for efficiency
    - Connection pooling
    - Graceful degradation (logs errors but doesn't crash)
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl_seconds: int = 3600,  # 1 hour default
    ):
        """
        Initialize Redis cache client.
        
        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number (0-15)
            password: Redis password (if auth enabled)
            default_ttl_seconds: Default TTL for cached items
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.default_ttl_seconds = default_ttl_seconds
        self._client: Optional[redis.Redis] = None
        
    async def connect(self):
        """Initialize Redis connection pool"""
        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,  # Automatically decode bytes to str
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
            # Test connection
            await self._client.ping()  # type: ignore[misc]
            logger.info(f"✅ Redis connected: {self.host}:{self.port} (db={self.db})")
        except Exception as e:
            logger.warning(f"⚠️  Redis connection failed: {e}. Cache disabled.")
            self._client = None
    
    async def disconnect(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis connection closed")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
    
    def _make_key(self, namespace: str, identifier: str) -> str:
        """
        Create namespaced cache key.
        
        Args:
            namespace: Category (e.g., 'directional', 'fuzzy', 'external')
            identifier: Unique identifier (will be hashed if too long)
        
        Returns:
            Formatted cache key
        """
        # Hash long identifiers for consistent key length
        if len(identifier) > 100:
            identifier = hashlib.md5(identifier.encode()).hexdigest()
        
        return f"geocode:{namespace}:{identifier}"
    
    async def get(self, namespace: str, identifier: str) -> Optional[Any]:
        """
        Get cached value.
        
        Args:
            namespace: Cache namespace
            identifier: Cache key identifier
            
        Returns:
            Cached value (deserialized from JSON) or None if not found
        """
        if not self._client:
            return None
        
        try:
            key = self._make_key(namespace, identifier)
            value = await self._client.get(key)
            
            if value:
                logger.debug(f"✅ Cache HIT: {namespace}:{identifier[:50]}")
                return json.loads(value)
            
            logger.debug(f"❌ Cache MISS: {namespace}:{identifier[:50]}")
            return None
        except Exception as e:
            logger.warning(f"Redis GET error: {e}")
            return None
    
    async def set(
        self,
        namespace: str,
        identifier: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Set cached value with optional TTL.
        
        Args:
            namespace: Cache namespace
            identifier: Cache key identifier
            value: Value to cache (will be JSON serialized)
            ttl_seconds: Time-to-live in seconds (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False
        
        try:
            key = self._make_key(namespace, identifier)
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
            
            # Serialize to JSON
            serialized = json.dumps(value)
            
            # Set with TTL
            await self._client.setex(key, ttl, serialized)
            logger.debug(f"💾 Cache SET: {namespace}:{identifier[:50]} (TTL={ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"Redis SET error: {e}")
            return False
    
    async def delete(self, namespace: str, identifier: str) -> bool:
        """
        Delete cached value.
        
        Args:
            namespace: Cache namespace
            identifier: Cache key identifier
            
        Returns:
            True if deleted, False otherwise
        """
        if not self._client:
            return False
        
        try:
            key = self._make_key(namespace, identifier)
            result = await self._client.delete(key)
            logger.debug(f"🗑️  Cache DELETE: {namespace}:{identifier[:50]}")
            return bool(result)
        except Exception as e:
            logger.warning(f"Redis DELETE error: {e}")
            return False
    
    async def get_many(
        self,
        namespace: str,
        identifiers: List[str]
    ) -> Dict[str, Any]:
        """
        Get multiple cached values in one batch operation.
        
        Args:
            namespace: Cache namespace
            identifiers: List of cache key identifiers
            
        Returns:
            Dict mapping identifier -> cached value (only for found items)
        """
        if not self._client or not identifiers:
            return {}
        
        try:
            keys = [self._make_key(namespace, ident) for ident in identifiers]
            values = await self._client.mget(keys)
            
            result = {}
            for ident, value in zip(identifiers, values):
                if value:
                    result[ident] = json.loads(value)
            
            logger.debug(f"📦 Cache MGET: {namespace} ({len(result)}/{len(identifiers)} hits)")
            return result
        except Exception as e:
            logger.warning(f"Redis MGET error: {e}")
            return {}
    
    async def set_many(
        self,
        namespace: str,
        items: Dict[str, Any],
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Set multiple cached values in one batch operation.
        
        Args:
            namespace: Cache namespace
            items: Dict mapping identifier -> value
            ttl_seconds: Time-to-live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self._client or not items:
            return False
        
        try:
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
            
            # Use pipeline for atomic batch operation
            async with self._client.pipeline() as pipe:
                for identifier, value in items.items():
                    key = self._make_key(namespace, identifier)
                    serialized = json.dumps(value)
                    pipe.setex(key, ttl, serialized)
                
                await pipe.execute()
            
            logger.debug(f"💾 Cache MSET: {namespace} ({len(items)} items, TTL={ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"Redis MSET error: {e}")
            return False
    
    async def clear_namespace(self, namespace: str) -> int:
        """
        Clear all keys in a namespace.
        
        Args:
            namespace: Cache namespace to clear
            
        Returns:
            Number of keys deleted
        """
        if not self._client:
            return 0
        
        try:
            pattern = f"geocode:{namespace}:*"
            
            # Scan for keys matching pattern (cursor-based for safety)
            deleted = 0
            cursor = 0
            while True:
                cursor, keys = await self._client.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted += await self._client.delete(*keys)
                if cursor == 0:
                    break
            
            logger.info(f"🧹 Cache CLEAR: {namespace} ({deleted} keys)")
            return deleted
        except Exception as e:
            logger.warning(f"Redis CLEAR error: {e}")
            return 0
    
    async def is_connected(self) -> bool:
        """Check if Redis is connected and responsive"""
        if not self._client:
            return False
        
        try:
            await self._client.ping()  # type: ignore[misc]
            return True
        except Exception:
            return False


# Global cache instance (initialized in dependencies)
_cache_instance: Optional[RedisCache] = None


def get_redis_cache() -> Optional[RedisCache]:
    """Get global Redis cache instance"""
    return _cache_instance


def set_redis_cache(cache: RedisCache):
    """Set global Redis cache instance"""
    global _cache_instance
    _cache_instance = cache
