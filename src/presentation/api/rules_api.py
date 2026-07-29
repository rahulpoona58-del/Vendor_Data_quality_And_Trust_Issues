from flask import Blueprint, request, jsonify
from src.infrastructure.database.models import BusinessRule, db
from src.domain.services.business_rules_engine import BusinessRulesEngine
from src.infrastructure.security.decorators import login_required, role_required, get_current_user
import logging

rules_api = Blueprint('rules_api', __name__)

@rules_api.route('/api/v2/rules', methods=['GET'])
@login_required
def get_rules():
    """API endpoint to retrieve all registered configurable business rules."""
    rules = BusinessRule.query.order_by(BusinessRule.priority.asc()).all()
    return jsonify({'success': True, 'rules': [r.to_dict() for r in rules]}), 200

@rules_api.route('/api/v2/rules', methods=['POST'])
@login_required
@role_required(['Admin', 'Manager'])
def create_rule():
    """API endpoint to create a new business rule with JSON conditions/actions."""
        
    data = request.get_json() or {}
    name = data.get('name')
    rule_group = data.get('rule_group')
    conditions = data.get('conditions_json')
    actions = data.get('actions_json')
    priority = data.get('priority', 1)
    
    if not name or not rule_group or not conditions or not actions:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
    try:
        new_rule = BusinessRule(
            name=name,
            description=data.get('description', ''),
            rule_group=rule_group,
            priority=priority,
            conditions_json=conditions,
            actions_json=actions
        )
        db.session.add(new_rule)
        db.session.commit()
        
        # System Audit Log
        from src.domain.services.audit_service import AuditService
        AuditService.log_audit(
            performed_by="admin@system.local",
            ip_address=request.remote_addr,
            action_type="Create Business Rule",
            module_name="Rules",
            old_value=None,
            new_value=new_rule.to_dict(),
            reason=f"Created business rule: {name}"
        )
        
        return jsonify({'success': True, 'rule': new_rule.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@rules_api.route('/api/v2/rules/<int:rule_id>/toggle', methods=['POST'])
@login_required
def toggle_rule(rule_id):
    """API endpoint to enable or disable a business rule."""
    role = request.headers.get('X-Role') or 'Viewer'
    if role != 'Admin':
        return jsonify({'success': False, 'message': 'Insufficient role permissions'}), 403
        
    try:
        rule = BusinessRule.query.get(rule_id)
        if not rule:
            return jsonify({'success': False, 'message': 'Rule not found'}), 404
            
        old_val = rule.is_enabled
        rule.is_enabled = not rule.is_enabled
        db.session.commit()
        
        # Audit Log
        from src.domain.services.audit_service import AuditService
        AuditService.log_audit(
            performed_by="admin@system.local",
            ip_address=request.remote_addr,
            action_type="Toggle Business Rule",
            module_name="Rules",
            old_value={"is_enabled": old_val},
            new_value={"is_enabled": rule.is_enabled},
            reason=f"Toggled rule: {rule.name}"
        )
        
        return jsonify({'success': True, 'rule': rule.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@rules_api.route('/api/v2/rules/simulate', methods=['POST'])
@login_required
def simulate():
    """API endpoint to trigger rules engine mock simulation runs."""
    data = request.get_json() or {}
    vendor_id = data.get('vendor_id')
    rule_id = data.get('rule_id')
    
    if not vendor_id or not rule_id:
        return jsonify({'success': False, 'message': 'Missing vendor_id or rule_id'}), 400
        
    result = BusinessRulesEngine.simulate_rule(vendor_id, rule_id)
    return jsonify(result), 200

@rules_api.route('/api/v2/rules/<int:rule_id>', methods=['DELETE'])
@login_required
def delete_rule(rule_id):
    """API endpoint to delete a business rule."""
    role = request.headers.get('X-Role') or 'Viewer'
    if role != 'Admin':
        return jsonify({'success': False, 'message': 'Insufficient role permissions'}), 403
        
    try:
        rule = BusinessRule.query.get(rule_id)
        if not rule:
            return jsonify({'success': False, 'message': 'Rule not found'}), 404
            
        old_val = rule.to_dict()
        db.session.delete(rule)
        db.session.commit()
        
        # Audit Log
        from src.domain.services.audit_service import AuditService
        AuditService.log_audit(
            performed_by="admin@system.local",
            ip_address=request.remote_addr,
            action_type="Delete Business Rule",
            module_name="Rules",
            old_value=old_val,
            new_value=None,
            reason=f"Deleted rule: {old_val.get('name')}"
        )
        
        return jsonify({'success': True, 'message': 'Rule deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
