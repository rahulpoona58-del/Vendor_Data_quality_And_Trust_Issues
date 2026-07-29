import secrets
from flask import session, request, jsonify, render_template_string, redirect, url_for, flash
import functools

def generate_csrf_token() -> str:
    """Generates or retrieves a session-bound CSRF token."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def verify_csrf_token(token_to_check: str) -> bool:
    """Verifies a candidate CSRF token against the active session token."""
    session_token = session.get('csrf_token')
    if not session_token or not token_to_check:
        return False
    return secrets.compare_digest(session_token, token_to_check)

def csrf_protected(f):
    """Decorator enforcing CSRF token validation on state-modifying requests."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            # Skip CSRF check for stateless JWT Bearer token API calls
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                return f(*args, **kwargs)
                
            token = request.headers.get('X-CSRF-Token')
            if not token:
                data = request.get_json(silent=True) or {}
                token = data.get('csrf_token') or request.form.get('csrf_token')
                
            if not verify_csrf_token(token):
                if request.path.startswith('/api/'):
                    return jsonify({'success': False, 'message': 'CSRF token missing or invalid'}), 403
                flash("Security verification failed. Please try again.", "danger")
                return redirect(url_for('dashboard.dashboard_page'))
                
        return f(*args, **kwargs)
    return decorated

def add_security_headers(response):
    """Attaches standard security headers (XSS, Anti-Clickjacking, Nosniff) to HTTP responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response
