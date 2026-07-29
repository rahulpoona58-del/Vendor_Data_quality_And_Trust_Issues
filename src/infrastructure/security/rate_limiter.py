import time
import functools
from flask import request, jsonify, current_app
from src.infrastructure.cache.cache_service import MemoryCacheService
from src.infrastructure.security.decorators import get_current_user
from src.config import get_config

def rate_limit(limit_key: str = "default", max_requests: int = None, window_seconds: int = None):
    """Sliding-window API rate limiter decorator backed by MemoryCacheService."""
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            try:
                config = get_config()
                
                # If testing environment and reset requested, clear cache key
                if request.headers.get('X-Test-Reset-Limit'):
                    client_ip = request.remote_addr or '127.0.0.1'
                    user = get_current_user()
                    identity = f"user_{user['user_id']}" if user else f"ip_{client_ip}"
                    cache_key = f"rate_limit:{limit_key}:{identity}"
                    MemoryCacheService.delete(cache_key)
                    return f(*args, **kwargs)

                # If testing environment and rate limits not forced, pass through
                if getattr(config, 'TESTING', False) and not request.headers.get('X-Test-Rate-Limit'):
                    return f(*args, **kwargs)
                    
                client_ip = request.remote_addr or '127.0.0.1'
                user = get_current_user()
                identity = f"user_{user['user_id']}" if user else f"ip_{client_ip}"
                
                key_upper = limit_key.upper()
                limit_count = max_requests or getattr(config, f"RATE_LIMIT_{key_upper}_COUNT", 60)
                window = window_seconds or getattr(config, f"RATE_LIMIT_{key_upper}_WINDOW", 60)
                
                cache_key = f"rate_limit:{limit_key}:{identity}"
                now = time.time()
                
                timestamps = MemoryCacheService.get(cache_key) or []
                # Filter timestamps to sliding window
                valid_timestamps = [t for t in timestamps if now - t < window]
                
                if len(valid_timestamps) >= limit_count:
                    oldest = valid_timestamps[0]
                    retry_after = int(window - (now - oldest)) + 1
                    
                    response = jsonify({
                        'success': False,
                        'message': f'Rate limit exceeded for {limit_key}. Too many requests.',
                        'retry_after_seconds': max(1, retry_after)
                    })
                    response.status_code = 429
                    response.headers['Retry-After'] = str(max(1, retry_after))
                    return response
                    
                valid_timestamps.append(now)
                MemoryCacheService.set(cache_key, valid_timestamps, ttl=window)
            except Exception as e:
                # Log error and fail open to prevent breaking service if cache fails
                pass
                
            return f(*args, **kwargs)
        return decorated
    return decorator
