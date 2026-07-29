from flask import Blueprint, request, jsonify, session
from src.infrastructure.database.models import User, db
from src.infrastructure.security.cryptography import hash_password, verify_password, generate_tokens, decode_token, revoke_token
from src.infrastructure.validation.validators import validate_request
from src.config import get_config
import logging

from src.infrastructure.security.rate_limiter import rate_limit

auth_api = Blueprint('auth_api', __name__)

@auth_api.route('/api/v2/auth/register', methods=['POST'])
@validate_request(required_fields=['email', 'password'])
def register():
    """Endpoint to register a new user with role-based permissions."""
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'Viewer')
    
    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required'}), 400
        
    if role not in {'Admin', 'Manager', 'Auditor', 'Analyst', 'Data Steward', 'Viewer'}:
        return jsonify({'success': False, 'message': 'Invalid role specified'}), 400
        
    try:
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'success': False, 'message': 'User already registered'}), 400
            
        hashed = hash_password(password)
        new_user = User(email=email, password_hash=hashed, role=role)
        
        db.session.add(new_user)
        db.session.commit()
        
        logging.info(f"User registered: {email} with role {role}")
        return jsonify({'success': True, 'user': new_user.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"Registration failure: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@auth_api.route('/api/v2/auth/login', methods=['POST'])
@validate_request(required_fields=['email', 'password'])
def login():
    """Endpoint to authenticate a user and establish session/JWT access and refresh tokens."""
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    
    from src.infrastructure.logging.logger import log_auth_event
    if not email or not password:
        log_auth_event("LOGIN_ATTEMPT", email or "N/A", False, details="Missing required email or password")
        return jsonify({'success': False, 'message': 'Email and password are required'}), 400
        
    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(user.password_hash, password):
        log_auth_event("LOGIN_ATTEMPT", email, False, details="Invalid credentials supplied")
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
    # Populate Session variables (for browser-based authentication)
    session['user_id'] = user.id
    session['user_email'] = user.email
    session['user_role'] = user.role
    
    # Generate JWT Token Pair (Access & Refresh tokens)
    config = get_config()
    tokens = generate_tokens(user.id, user.role, config.SECRET_KEY)
    
    # Audit trail login
    from src.domain.services.audit_service import AuditService
    AuditService.log_audit(
        performed_by=email,
        ip_address=request.remote_addr,
        action_type="User Login",
        module_name="Auth",
        old_value=None,
        new_value={"role": user.role},
        reason="System Authentication"
    )
    
    log_auth_event("LOGIN_ATTEMPT", email, True, details=f"Role: {user.role}")
    return jsonify({
        'success': True,
        'token': tokens['access_token'],
        'access_token': tokens['access_token'],
        'refresh_token': tokens['refresh_token'],
        'expires_in': tokens['expires_in'],
        'user': user.to_dict()
    })

@auth_api.route('/api/v2/auth/refresh', methods=['POST'])
def refresh():
    """Endpoint to exchange a valid Refresh Token for a brand-new Access & Refresh token pair."""
    data = request.get_json() or {}
    refresh_token = data.get('refresh_token')
    
    if not refresh_token:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            refresh_token = auth_header.split(" ")[1]
            
    if not refresh_token:
        return jsonify({'success': False, 'message': 'Refresh token is required'}), 400
        
    config = get_config()
    res = decode_token(refresh_token, config.SECRET_KEY, expected_type='refresh')
    if not res.get('success'):
        return jsonify({'success': False, 'message': res.get('message', 'Invalid refresh token')}), 401
        
    user_id = res['user_id']
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User profile not found'}), 404
        
    # Rotate refresh token: revoke old refresh token
    revoke_token(refresh_token, config.SECRET_KEY)
    
    # Issue new token pair
    new_tokens = generate_tokens(user.id, user.role, config.SECRET_KEY)
    return jsonify({
        'success': True,
        'token': new_tokens['access_token'],
        'access_token': new_tokens['access_token'],
        'refresh_token': new_tokens['refresh_token'],
        'expires_in': new_tokens['expires_in']
    }), 200

@auth_api.route('/api/v2/auth/logout', methods=['POST', 'GET'])
def logout():
    """Endpoint to terminate user sessions and revoke JWT tokens."""
    email = session.get('user_email', 'unknown')
    session.clear()
    
    config = get_config()
    
    # Revoke Access Token if passed in Authorization header
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(" ")[1]
        revoke_token(token, config.SECRET_KEY)
        
    # Revoke Refresh Token if passed in body
    data = request.get_json() or {}
    r_token = data.get('refresh_token')
    if r_token:
        revoke_token(r_token, config.SECRET_KEY)
        
    logging.info(f"User logged out and tokens revoked: {email}")
    return jsonify({'success': True, 'message': 'Successfully logged out'})
