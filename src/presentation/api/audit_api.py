from flask import Blueprint, request, jsonify, render_template
from src.domain.services.audit_service import AuditService
from src.infrastructure.security.decorators import login_required, role_required
import logging

audit_api = Blueprint('audit_api', __name__)

@audit_api.route('/audit-viewer', methods=['GET'])
@login_required
@role_required(['Admin', 'Auditor'])
def audit_viewer_page():
    """Renders the interactive System Audit Log Viewer dashboard page."""
    return render_template('audit_viewer.html')

@audit_api.route('/api/v2/audit-logs', methods=['GET'])
@login_required
@role_required(['Admin', 'Auditor'])
def get_system_audit_logs():
    """API endpoint to query system-wide audit logs with filters. Access is restricted to Admin/Auditor."""
        
    search = request.args.get('search')
    module = request.args.get('module')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    vendor_id = request.args.get('vendor_id')
    page = request.args.get('page')
    per_page = request.args.get('per_page')
    
    if vendor_id and str(vendor_id).isdigit():
        vendor_id = int(vendor_id)
    else:
        vendor_id = None
    
    logs_res = AuditService.query_audit_logs(
        search=search,
        module=module,
        start_date=start_date,
        end_date=end_date,
        vendor_id=vendor_id,
        page=page,
        per_page=per_page
    )
    if isinstance(logs_res, dict):
        return jsonify({'success': True, **logs_res}), 200
    return jsonify({'success': True, 'logs': logs_res}), 200
