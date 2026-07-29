import time
import functools
import threading
import logging
from flask import request, jsonify

class MemoryCacheService:
    """In-memory thread-safe TTL cache service for high-performance API query optimization."""
    _cache = {}
    _lock = threading.RLock()

    @classmethod
    def get(cls, key: str):
        with cls._lock:
            if key in cls._cache:
                value, expiry = cls._cache[key]
                if time.time() < expiry:
                    return value
                else:
                    del cls._cache[key]
            return None

    MAX_CACHE_SIZE = 1000

    @classmethod
    def set(cls, key: str, value, ttl: int = 60):
        with cls._lock:
            # Enforce bounded memory size limits by evicting expired or oldest items
            if len(cls._cache) >= cls.MAX_CACHE_SIZE:
                now = time.time()
                expired = [k for k, (_, exp) in cls._cache.items() if now >= exp]
                for k in expired:
                    del cls._cache[k]
                # If still at limit, evict oldest 10% of entries to keep memory bounded
                if len(cls._cache) >= cls.MAX_CACHE_SIZE:
                    keys = list(cls._cache.keys())[:int(cls.MAX_CACHE_SIZE * 0.1)]
                    for k in keys:
                        del cls._cache[k]

            expiry = time.time() + ttl
            cls._cache[key] = (value, expiry)

    @classmethod
    def invalidate_prefix(cls, prefix: str):
        with cls._lock:
            keys_to_del = [k for k in cls._cache if k.startswith(prefix)]
            for k in keys_to_del:
                del cls._cache[k]

    @classmethod
    def invalidate_vendor(cls, vendor_id: int = None):
        """Invalidates vendor profiles, summaries, vendor lists, and dashboard telemetry caches."""
        with cls._lock:
            if vendor_id:
                cls.invalidate_prefix(f"vendor:{vendor_id}")
            cls.invalidate_prefix("vendor")
            cls.invalidate_prefix("dashboard")
            cls.invalidate_prefix("analytics")

    @classmethod
    def invalidate_dashboard(cls):
        """Invalidates all dashboard and analytics telemetry caches."""
        with cls._lock:
            cls.invalidate_prefix("dashboard")
            cls.invalidate_prefix("analytics")

    @classmethod
    def invalidate_rules(cls):
        """Invalidates business scoring rules caches."""
        with cls._lock:
            cls.invalidate_prefix("rules")
            cls.invalidate_prefix("dashboard")

    @classmethod
    def clear(cls):
        with cls._lock:
            cls._cache.clear()

def cache_response(ttl_seconds: int = 30, key_prefix: str = ""):
    """Decorator to cache Flask API response outputs for faster response times."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            # Construct a unique cache key based on route path and query parameters
            query_str = request.query_string.decode('utf-8')
            cache_key = f"{key_prefix or f.__name__}:{request.path}?{query_str}"
            
            cached_val = MemoryCacheService.get(cache_key)
            if cached_val is not None:
                return cached_val

            res = f(*args, **kwargs)
            
            # Only cache successful 200 JSON responses
            if isinstance(res, tuple) and len(res) == 2 and res[1] == 200:
                MemoryCacheService.set(cache_key, res, ttl=ttl_seconds)
            elif not isinstance(res, tuple):
                MemoryCacheService.set(cache_key, res, ttl=ttl_seconds)
                
            return res
        return wrapper
    return decorator
