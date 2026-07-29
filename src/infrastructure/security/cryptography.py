import jwt
import uuid
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from src.infrastructure.cache.cache_service import MemoryCacheService

# Secret key defaults to a standard configuration variable
JWT_SECRET = "jwt-secret-session-verification-key"

def hash_password(password: str) -> str:
    """Hashes a raw password string using Werkzeug's secure hash algorithm."""
    return generate_password_hash(password)

def verify_password(password_hash: str, password: str) -> bool:
    """Verifies a raw password against its secure hash representation."""
    return check_password_hash(password_hash, password)

def generate_tokens(user_id: int, role: str, secret_key: str, access_exp_minutes: int = 60, refresh_exp_days: int = 7) -> dict:
    """Generates a pair of access and refresh tokens with unique JTIs and session claims."""
    now = datetime.utcnow()
    
    access_jti = str(uuid.uuid4())
    access_payload = {
        'jti': access_jti,
        'sub': str(user_id),
        'role': role,
        'type': 'access',
        'iat': now,
        'exp': now + timedelta(minutes=access_exp_minutes)
    }
    
    refresh_jti = str(uuid.uuid4())
    refresh_payload = {
        'jti': refresh_jti,
        'sub': str(user_id),
        'role': role,
        'type': 'refresh',
        'iat': now,
        'exp': now + timedelta(days=refresh_exp_days)
    }
    
    access_token = jwt.encode(access_payload, secret_key, algorithm='HS256')
    refresh_token = jwt.encode(refresh_payload, secret_key, algorithm='HS256')
    
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_in': access_exp_minutes * 60
    }

def generate_token(user_id: int, role: str, secret_key: str, expires_in_minutes: int = 120) -> str:
    """Generates a secure JWT token for API client authentications (Backwards Compatible Wrapper)."""
    tokens = generate_tokens(user_id, role, secret_key, access_exp_minutes=expires_in_minutes)
    return tokens['access_token']

def revoke_token(jti_or_token: str, secret_key: str = None):
    """Blacklists a token or JTI so it cannot be used for subsequent requests."""
    if not jti_or_token:
        return
    jti = jti_or_token
    if "." in jti_or_token and secret_key:
        try:
            payload = jwt.decode(jti_or_token, secret_key, algorithms=['HS256'], options={"verify_exp": False})
            jti = payload.get('jti', jti_or_token)
        except Exception:
            pass
    MemoryCacheService.set(f"revoked_token:{jti}", True, ttl=86400 * 7)

def is_token_revoked(jti_or_token: str) -> bool:
    """Checks if a token JTI or signature has been revoked."""
    if not jti_or_token:
        return False
    return MemoryCacheService.get(f"revoked_token:{jti_or_token}") is True

def decode_token(token: str, secret_key: str, expected_type: str = None) -> dict:
    """Decodes, validates token signature, expiration, type claim, and revocation status."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        
        jti = payload.get('jti')
        if jti and is_token_revoked(jti):
            return {'success': False, 'message': 'Token has been revoked'}
            
        if is_token_revoked(token):
            return {'success': False, 'message': 'Token has been revoked'}

        t_type = payload.get('type')
        if expected_type and t_type and t_type != expected_type:
            return {'success': False, 'message': f'Invalid token type. Expected {expected_type}'}

        return {
            'success': True,
            'user_id': int(payload['sub']),
            'role': payload['role'],
            'jti': jti,
            'token_type': t_type or 'access'
        }
    except jwt.ExpiredSignatureError:
        return {'success': False, 'message': 'Token signature expired'}
    except jwt.InvalidTokenError:
        return {'success': False, 'message': 'Invalid token signature'}
