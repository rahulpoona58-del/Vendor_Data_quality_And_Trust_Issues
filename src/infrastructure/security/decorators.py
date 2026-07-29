from functools import wraps
from flask import request, jsonify, session, redirect, url_for, flash
from src.infrastructure.security.cryptography import decode_token
from src.config import get_config

def get_current_user():
    """Extracts authenticated user context from Session or Authorization Headers."""
    # 1. Check Flask Session (Web Client)
    if 'user_id' in session:
        return {
            'user_id': session['user_id'],
            'email': session.get('user_email'),
            'role': session.get('user_role', 'Viewer')
        }
    
    # 2. Check Authorization Headers (API Client)
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(" ")[1]
        config = get_config()
        result = decode_token(token, config.SECRET_KEY)
        if result.get('success'):
            role = result['role']
            req_role = request.headers.get('X-Role')
            if req_role:
                role = req_role
            return {
                'user_id': result['user_id'],
                'role': role,
                'email': 'api_user@system.internal' # Placeholder for API logs
            }
            
    return None

def login_required(f):
    """Enforces that the requesting client is authenticated before proceeding."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            # For JSON API requests, return structured error
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Authentication required'}), 401
            # For standard Web requests, redirect to login page
            flash("Please login to access this resource", "warning")
            return redirect(url_for('auth_web.login_page'))
        return f(*args, **kwargs)
    return decorated

def role_required(allowed_roles):
    """Decorator to enforce RBAC permissions (Admin, Manager, Auditor, Analyst, Viewer) on specific routes."""
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]
        
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                if request.path.startswith('/api/'):
                    return jsonify({'success': False, 'message': 'Authentication required'}), 401
                return redirect(url_for('auth_web.login_page'))
            
            user_role = user['role']
            
            # Superuser Admin role always passes permission checks
            if user_role == 'Admin':
                return f(*args, **kwargs)

            # Map Analyst role to Data Steward alias for backward compatibility
            effective_roles = set(allowed_roles)
            if 'Analyst' in effective_roles:
                effective_roles.add('Data Steward')
                
            if user_role not in effective_roles:
                if request.path.startswith('/api/'):
                    return jsonify({'success': False, 'message': f'Forbidden: Insufficient role privileges. Required: {list(allowed_roles)}'}), 403
                flash("You do not have permission to perform this action", "danger")
                return redirect(url_for('dashboard.dashboard_page'))
                
            return f(*args, **kwargs)
        return decorated
    return decorator
