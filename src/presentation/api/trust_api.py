from flask import Blueprint, request, jsonify
from src.domain.services.trust_engine import TrustEngine
from src.infrastructure.database.models import ScoringRule
from src.infrastructure.security.decorators import login_required, role_required, get_current_user
import logging

trust_api = Blueprint('trust_api', __name__)

@trust_api.route('/api/v2/vendors/<int:vendor_id>/trust/recalculate', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward', 'Manager', 'Auditor'])
def recalculate_trust(vendor_id):
    """API endpoint to run a complete Trust and Risk assessment scan on a vendor."""
    result = TrustEngine.calculate_vendor_trust(vendor_id)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result), 200

@trust_api.route('/api/v2/vendors/<int:vendor_id>/trust/history', methods=['GET'])
@login_required
def get_vendor_trust_history(vendor_id):
    """API endpoint to retrieve the historical trust logs for trend mapping."""
    limit = request.args.get('limit', 10, type=int)
    history = TrustEngine.get_trust_history(vendor_id, limit=limit)
    return jsonify({'success': True, 'history': history})

@trust_api.route('/api/v2/trust/rules', methods=['GET'])
@login_required
def list_scoring_rules():
    """API endpoint to retrieve all operational scoring weights and thresholds."""
    rules = ScoringRule.query.all()
    return jsonify({'success': True, 'rules': [r.to_dict() for r in rules]})

@trust_api.route('/api/v2/trust/rules', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward'])
def modify_scoring_rule():
    """API endpoint to modify specific rule weights dynamically."""
    data = request.get_json() or {}
    key = data.get('rule_key')
    val = data.get('rule_value')
    
    if not key or val is None:
        return jsonify({'success': False, 'message': 'rule_key and rule_value parameters are required'}), 400
        
    try:
        val_float = float(val)
    except ValueError:
        return jsonify({'success': False, 'message': 'rule_value parameter must be a numeric value'}), 400
        
    user = get_current_user()
    result = TrustEngine.update_scoring_rule(key, val_float, user['email'])
    if not result['success']:
        return jsonify(result), 400
        
    return jsonify(result)
