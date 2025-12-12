"""
Redis State Backend Implementation.

Provides Redis-based state persistence with connection pooling, TTL support,
namespacing via key prefixes, batch operations using pipelines, and retry logic.

Author: LocalZure Team
Date: 2025-12-12
"""

import asyncio
import json
import logging
import pickle
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

try:
    import redis.asyncio as redis
    from redis.asyncio.connection import ConnectionPool
    from redis.exceptions import (
        ConnectionError as RedisConnectionError,
        TimeoutError as RedisTimeoutError,
        RedisError,
    )
    REDIS_AVAILABLE = True
    RedisClient = redis.Redis
except ImportError:
    REDIS_AVAILABLE = False
    redis = None  # type: ignore
    ConnectionPool = None  # type: ignore
    RedisConnectionError = Exception  # type: ignore
    RedisTimeoutError = Exception  # type: ignore
    RedisError = Exception  # type: ignore
    RedisClient = None  # type: ignore

from .backend import StateBackend
from .exceptions import (
    StateBackendError,
    SerializationError,
    TransactionError,
)

logger = logging.getLogger(__name__)


class RedisBackend(StateBackend):
    """
    Redis-based state backend implementation.
    
    Features:
    - Connection pooling for efficiency
    - TTL support using Redis EXPIRE
    - Namespace isolation via key prefixes
    - Batch operations using Redis pipelines
    - Automatic retries with exponential backoff
    - JSON serialization for simple types, pickle for complex objects
    - SCAN-based list operations to avoid blocking
    
    Configuration:
        host: Redis server hostname (default: localhost)
        port: Redis server port (default: 6379)
        db: Redis database number (default: 0)
        password: Redis password (default: None)
        key_prefix: Global key prefix (default: "localzure:")
        max_connections: Connection pool size (default: 50)
        socket_timeout: Socket timeout in seconds (default: 5.0)
        socket_connect_timeout: Connection timeout (default: 5.0)
        retry_on_timeout: Retry on timeout (default: True)
        max_retries: Maximum retry attempts (default: 3)
        retry_delay: Initial retry delay (default: 0.1)
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        key_prefix: str = "localzure:",
        max_connections: int = 50,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        retry_on_timeout: bool = True,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ):
        """
        Initialize Redis backend.
        
        Args:
            host: Redis server hostname
            port: Redis server port
            db: Redis database number
            password: Redis password (None if no auth)
            key_prefix: Global prefix for all keys
            max_connections: Max connections in pool
            socket_timeout: Socket timeout in seconds
            socket_connect_timeout: Connection timeout in seconds
            retry_on_timeout: Whether to retry on timeout
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
        
        Raises:
            ImportError: If redis package not installed
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis package not installed. Install with: pip install redis[async]"
            )
        
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.key_prefix = key_prefix
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Create connection pool
        self.pool = ConnectionPool(
            host=host,
            port=port,
            db=db,
            password=password,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            retry_on_timeout=retry_on_timeout,
            decode_responses=False,  # We handle encoding/decoding ourselves
        )
        
        self._client: Optional[Any] = None  # redis.Redis when available
        self._transactions: Dict[str, List[tuple]] = {}  # tx_id -> operations
        
        logger.info(
            f"RedisBackend initialized: {host}:{port}/{db}, "
            f"prefix={key_prefix}, pool_size={max_connections}"
        )
    
    async def _get_client(self) -> Any:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.Redis(connection_pool=self.pool)  # type: ignore
            # Test connection
            try:
                await self._client.ping()
                logger.debug("Redis connection established")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise StateBackendError(f"Redis connection failed: {e}")
        
        return self._client
    
    def _make_key(self, namespace: str, key: str) -> str:
        """
        Create fully-qualified Redis key.
        
        Format: {prefix}{namespace}:{key}
        Example: localzure:cosmosdb:db:my-database
        
        Args:
            namespace: Service namespace
            key: Key within namespace
        
        Returns:
            Full Redis key with prefix
        """
        return f"{self.key_prefix}{namespace}:{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """
        Serialize value for Redis storage.
        
        Uses JSON for simple types (str, int, float, bool, None, dict, list),
        pickle for complex objects.
        
        Args:
            value: Value to serialize
        
        Returns:
            Serialized bytes
        
        Raises:
            SerializationError: If serialization fails
        """
        try:
            # Try JSON first for simple types
            if isinstance(value, (str, int, float, bool, type(None), dict, list)):
                json_str = json.dumps(value, separators=(',', ':'))
                return b'J' + json_str.encode('utf-8')
            else:
                # Use pickle for complex objects
                return b'P' + pickle.dumps(value)
        except Exception as e:
            raise SerializationError(f"Failed to serialize value: {e}")
    
    def _deserialize(self, data: bytes) -> Any:
        """
        Deserialize value from Redis.
        
        Args:
            data: Serialized bytes
        
        Returns:
            Deserialized value
        
        Raises:
            SerializationError: If deserialization fails
        """
        if not data:
            return None
        
        try:
            marker = data[0:1]
            payload = data[1:]
            
            if marker == b'J':
                # JSON format
                return json.loads(payload.decode('utf-8'))
            elif marker == b'P':
                # Pickle format
                return pickle.loads(payload)
            else:
                # Unknown format - try pickle as fallback
                return pickle.loads(data)
        except Exception as e:
            raise SerializationError(f"Failed to deserialize value: {e}")
    
    async def _retry_operation(self, operation, *args, **kwargs) -> Any:
        """
        Execute Redis operation with exponential backoff retry.
        
        Args:
            operation: Async callable to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Operation result
        
        Raises:
            StateBackendError: If all retries fail
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return await operation(*args, **kwargs)
            except (RedisConnectionError, RedisTimeoutError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"Redis operation failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Redis operation failed after {self.max_retries} attempts: {e}")
        
        raise StateBackendError(f"Redis operation failed after {self.max_retries} retries: {last_error}")
    
    async def get(
        self, namespace: str, key: str, default: Optional[Any] = None
    ) -> Optional[Any]:
        """
        Retrieve a value from Redis.
        
        Args:
            namespace: Service namespace
            key: Key within namespace
            default: Default value if key not found
        
        Returns:
            Stored value or default
        """
        client = await self._get_client()
        redis_key = self._make_key(namespace, key)
        
        async def _get():
            data = await client.get(redis_key)
            if data is None:
                return default
            return self._deserialize(data)
        
        return await self._retry_operation(_get)
    
    async def set(
        self, namespace: str, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """
        Store a value in Redis.
        
        Args:
            namespace: Service namespace
            key: Key within namespace
            value: Value to store
            ttl: Time-to-live in seconds (None = no expiration)
        """
        client = await self._get_client()
        redis_key = self._make_key(namespace, key)
        data = self._serialize(value)
        
        async def _set():
            if ttl is not None and ttl > 0:
                await client.setex(redis_key, ttl, data)
            else:
                await client.set(redis_key, data)
        
        await self._retry_operation(_set)
        logger.debug(f"Set key: {redis_key}, ttl={ttl}")
    
    async def delete(self, namespace: str, key: str) -> bool:
        """
        Delete a key from Redis.
        
        Args:
            namespace: Service namespace
            key: Key to delete
        
        Returns:
            True if key was deleted, False if didn't exist
        """
        client = await self._get_client()
        redis_key = self._make_key(namespace, key)
        
        async def _delete():
            result = await client.delete(redis_key)
            return result > 0
        
        deleted = await self._retry_operation(_delete)
        logger.debug(f"Delete key: {redis_key}, deleted={deleted}")
        return deleted
    
    async def list(
        self, namespace: str, pattern: Optional[str] = None
    ) -> List[str]:
        """
        List all keys in namespace matching pattern.
        
        Uses Redis SCAN to avoid blocking on large datasets.
        
        Args:
            namespace: Service namespace
            pattern: Glob pattern (e.g., "user:*")
        
        Returns:
            List of keys (without namespace prefix)
        """
        client = await self._get_client()
        
        # Build scan pattern
        if pattern:
            scan_pattern = f"{self.key_prefix}{namespace}:{pattern}"
        else:
            scan_pattern = f"{self.key_prefix}{namespace}:*"
        
        async def _scan():
            keys = []
            cursor = 0
            
            while True:
                cursor, batch = await client.scan(cursor, match=scan_pattern, count=100)
                
                # Strip prefix and namespace from keys
                prefix_len = len(f"{self.key_prefix}{namespace}:")
                for redis_key in batch:
                    # Decode if bytes
                    if isinstance(redis_key, bytes):
                        redis_key = redis_key.decode('utf-8')
                    
                    # Extract key without prefix
                    if redis_key.startswith(f"{self.key_prefix}{namespace}:"):
                        key = redis_key[prefix_len:]
                        keys.append(key)
                
                if cursor == 0:
                    break
            
            return keys
        
        return await self._retry_operation(_scan)
    
    async def batch_get(
        self, namespace: str, keys: List[str]
    ) -> Dict[str, Any]:
        """
        Get multiple values in a single operation.
        
        Uses Redis MGET for efficiency.
        
        Args:
            namespace: Service namespace
            keys: List of keys to retrieve
        
        Returns:
            Dict of key -> value (only includes existing keys)
        """
        if not keys:
            return {}
        
        client = await self._get_client()
        redis_keys = [self._make_key(namespace, k) for k in keys]
        
        async def _mget():
            values = await client.mget(redis_keys)
            
            result = {}
            for key, data in zip(keys, values):
                if data is not None:
                    result[key] = self._deserialize(data)
            
            return result
        
        return await self._retry_operation(_mget)
    
    async def batch_set(
        self, namespace: str, items: Dict[str, Any], ttl: Optional[int] = None
    ) -> None:
        """
        Set multiple values using Redis pipeline.
        
        Args:
            namespace: Service namespace
            items: Dict of key -> value
            ttl: Optional TTL for all items
        """
        if not items:
            return
        
        client = await self._get_client()
        
        async def _batch_set():
            async with client.pipeline(transaction=True) as pipe:
                for key, value in items.items():
                    redis_key = self._make_key(namespace, key)
                    data = self._serialize(value)
                    
                    if ttl is not None and ttl > 0:
                        pipe.setex(redis_key, ttl, data)
                    else:
                        pipe.set(redis_key, data)
                
                await pipe.execute()
        
        await self._retry_operation(_batch_set)
        logger.debug(f"Batch set {len(items)} keys in namespace {namespace}, ttl={ttl}")
    
    async def clear_namespace(self, namespace: str) -> int:
        """
        Delete all keys in a namespace.
        
        Args:
            namespace: Namespace to clear
        
        Returns:
            Number of keys deleted
        """
        keys = await self.list(namespace)
        
        if not keys:
            return 0
        
        client = await self._get_client()
        redis_keys = [self._make_key(namespace, k) for k in keys]
        
        async def _delete_all():
            return await client.delete(*redis_keys)
        
        count = await self._retry_operation(_delete_all)
        logger.info(f"Cleared namespace {namespace}: {count} keys deleted")
        return count
    
    async def exists(self, namespace: str, key: str) -> bool:
        """
        Check if a key exists.
        
        Args:
            namespace: Service namespace
            key: Key to check
        
        Returns:
            True if key exists
        """
        client = await self._get_client()
        redis_key = self._make_key(namespace, key)
        
        async def _exists():
            result = await client.exists(redis_key)
            return result > 0
        
        return await self._retry_operation(_exists)
    
    async def get_ttl(self, namespace: str, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key.
        
        Args:
            namespace: Service namespace
            key: Key to check
        
        Returns:
            TTL in seconds, None if no TTL or key doesn't exist
        """
        client = await self._get_client()
        redis_key = self._make_key(namespace, key)
        
        async def _ttl():
            ttl = await client.ttl(redis_key)
            # -2 = key doesn't exist
            # -1 = key exists but no TTL
            # >= 0 = TTL in seconds
            if ttl == -2:
                return None  # Key doesn't exist
            elif ttl == -1:
                return None  # No TTL set
            else:
                return ttl
        
        return await self._retry_operation(_ttl)
    
    async def set_ttl(self, namespace: str, key: str, ttl: int) -> bool:
        """
        Update TTL for an existing key.
        
        Args:
            namespace: Service namespace
            key: Key to update
            ttl: New TTL in seconds
        
        Returns:
            True if TTL was set, False if key doesn't exist
        """
        client = await self._get_client()
        redis_key = self._make_key(namespace, key)
        
        async def _expire():
            result = await client.expire(redis_key, ttl)
            return result > 0
        
        return await self._retry_operation(_expire)
    
    @asynccontextmanager
    async def transaction(self, namespace: str):
        """
        Context manager for transactional operations.
        
        Uses Redis MULTI/EXEC for atomic operations.
        
        Usage:
            async with backend.transaction("cosmosdb") as txn:
                await txn.set("db1", {...})
                await txn.set("db2", {...})
        
        Args:
            namespace: Service namespace
        
        Yields:
            Transaction context (same interface as backend)
        """
        tx_id = f"tx_{id(self)}_{asyncio.get_event_loop().time()}"
        self._transactions[tx_id] = []
        
        # Create transaction wrapper
        class TransactionContext:
            def __init__(self, backend, tx_id, namespace):
                self._backend = backend
                self._tx_id = tx_id
                self._namespace = namespace
            
            async def set(self, key: str, value: Any, ttl: Optional[int] = None):
                self._backend._transactions[self._tx_id].append(
                    ('set', self._namespace, key, value, ttl)
                )
            
            async def delete(self, key: str) -> bool:
                self._backend._transactions[self._tx_id].append(
                    ('delete', self._namespace, key)
                )
                return True  # Actual result determined at commit
        
        txn = TransactionContext(self, tx_id, namespace)
        
        try:
            yield txn
            
            # Commit transaction
            if self._transactions[tx_id]:
                client = await self._get_client()
                
                async with client.pipeline(transaction=True) as pipe:
                    for op in self._transactions[tx_id]:
                        if op[0] == 'set':
                            _, ns, key, value, ttl = op
                            redis_key = self._make_key(ns, key)
                            data = self._serialize(value)
                            
                            if ttl is not None and ttl > 0:
                                pipe.setex(redis_key, ttl, data)
                            else:
                                pipe.set(redis_key, data)
                        
                        elif op[0] == 'delete':
                            _, ns, key = op
                            redis_key = self._make_key(ns, key)
                            pipe.delete(redis_key)
                    
                    await pipe.execute()
                
                logger.debug(f"Transaction {tx_id} committed: {len(self._transactions[tx_id])} operations")
        
        except Exception as e:
            # Rollback (discard operations)
            logger.warning(f"Transaction {tx_id} rolled back: {e}")
            raise TransactionError(f"Transaction failed: {e}")
        
        finally:
            # Clean up transaction
            self._transactions.pop(tx_id, None)
    
    async def close(self):
        """Close Redis connection and cleanup resources."""
        if self._client:
            await self._client.close()
            self._client = None
        
        if self.pool:
            await self.pool.disconnect()
        
        logger.info("RedisBackend connection closed")
    
    async def ping(self) -> bool:
        """
        Test Redis connection.
        
        Returns:
            True if connection is healthy
        """
        try:
            client = await self._get_client()
            await client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    async def info(self) -> Dict[str, Any]:
        """
        Get Redis server info.
        
        Returns:
            Dict with server information
        """
        try:
            client = await self._get_client()
            info = await client.info()
            
            return {
                "connected": True,
                "host": self.host,
                "port": self.port,
                "db": self.db,
                "redis_version": info.get("redis_version"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "uptime_in_seconds": info.get("uptime_in_seconds"),
            }
        except Exception as e:
            logger.error(f"Failed to get Redis info: {e}")
            return {
                "connected": False,
                "error": str(e)
            }
