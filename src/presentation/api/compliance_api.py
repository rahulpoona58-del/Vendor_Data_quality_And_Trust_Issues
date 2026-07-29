from flask import Blueprint, request, jsonify
from src.domain.services.compliance_engine import ComplianceEngine
from src.infrastructure.security.decorators import login_required, role_required, get_current_user
import logging

compliance_api = Blueprint('compliance_api', __name__)

@compliance_api.route('/api/v2/vendors/<int:vendor_id>/compliance/scan', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward', 'Manager', 'Auditor'])
def run_compliance_audit(vendor_id):
    """API endpoint to trigger compliance requirement check scans on a vendor."""
    result = ComplianceEngine.evaluate_compliance(vendor_id)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result), 200

@compliance_api.route('/api/v2/vendors/<int:vendor_id>/compliance/timeline', methods=['GET'])
@login_required
def get_compliance_logs(vendor_id):
    """API endpoint to fetch the historical compliance timeline logs."""
    limit = request.args.get('limit', 10, type=int)
    logs = ComplianceEngine.get_compliance_timeline(vendor_id, limit=limit)
    return jsonify({'success': True, 'timeline': logs})

@compliance_api.route('/api/v2/vendors/<int:vendor_id>/compliance/notifications', methods=['GET'])
@login_required
def get_compliance_alerts(vendor_id):
    """API endpoint to retrieve unread alerts and notifications."""
    alerts = ComplianceEngine.get_notifications(vendor_id)
    return jsonify({'success': True, 'notifications': alerts})

@compliance_api.route('/api/v2/compliance/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_alert_read(notif_id):
    """API endpoint to archive a compliance warning notification."""
    result = ComplianceEngine.mark_notification_read(notif_id)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result), 200

@compliance_api.route('/api/v2/vendors/<int:vendor_id>/compliance/approve', methods=['POST'])
@login_required
@role_required(['Admin', 'Auditor'])
def override_approval_status(vendor_id):
    """API endpoint enabling manual status overrides (Approved, Suspended, Rejected)."""
    data = request.get_json() or {}
    status = data.get('status')
    
    if not status:
        return jsonify({'success': False, 'message': 'status parameter is required'}), 400
        
    user = get_current_user()
    result = ComplianceEngine.set_approval_status(vendor_id, status, user['email'])
    if not result['success']:
        return jsonify(result), 400
        
    return jsonify(result), 200
