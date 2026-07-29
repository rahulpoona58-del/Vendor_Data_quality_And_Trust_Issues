from flask import Blueprint, jsonify, request
from src.infrastructure.database.models import Vendor, VendorAnomaly, FraudCheck, VendorComplianceStatus, SystemAuditLog, InvestigationCase
from src.infrastructure.security.decorators import login_required
from src.infrastructure.cache.cache_service import cache_response
import logging

command_center_api = Blueprint('command_center_api', __name__)

@command_center_api.route('/api/v2/command-center/telemetry', methods=['GET'])
@login_required
@cache_response(ttl_seconds=30, key_prefix="dashboard")
def get_command_center_telemetry():
    """Compiles factually grounded real-time system metrics for the Intelligence Command Center."""
    try:
        # Fetch actual DB statistics
        vendors = Vendor.query.all()
        anomalies = VendorAnomaly.query.filter_by(status='Active').all()
        fraud_checks = FraudCheck.query.all()
        compliance_profiles = VendorComplianceStatus.query.all()
        cases = InvestigationCase.query.all()
        audit_logs = SystemAuditLog.query.order_by(SystemAuditLog.created_at.desc()).limit(10).all()

        total_vendors = len(vendors)
        
        # Calculate factual averages
        avg_trust = 0.0
        avg_compliance = 0.0
        high_risk_count = 0
        critical_anomalies = len([a for a in anomalies if a.severity == 'Critical' or a.anomaly_score > 0.8])
        active_fraud_alerts = len([f for f in fraud_checks if f.status == 'Alert'])
        open_cases = len([c for c in cases if c.status in {'Open', 'Under Investigation'}])

        if total_vendors > 0:
            avg_trust = sum(v.trust_score for v in vendors) / total_vendors
            
        if compliance_profiles:
            avg_compliance = sum(c.compliance_score for c in compliance_profiles) / len(compliance_profiles)
            
        for v in vendors:
            if v.trust_score < 40 or v.trust_level == 'Low Trust':
                high_risk_count += 1

        # Format recent critical events timeline
        events = []
        for log in audit_logs:
            events.append({
                'id': log.id,
                'performed_by': log.performed_by,
                'action_type': log.action_type,
                'module_name': log.module_name,
                'reason': log.reason,
                'timestamp': log.created_at.isoformat()
            })

        # Compile list of active cases
        cases_list = []
        for c in cases[:10]:
            cases_list.append({
                'id': c.id,
                'case_number': c.case_number,
                'vendor_name': c.vendor.name if c.vendor else 'Unknown',
                'priority': c.priority,
                'status': c.status,
                'created_at': c.created_at.isoformat()
            })

        return jsonify({
            'success': True,
            'summary': {
                'total_vendors': total_vendors,
                'avg_trust': round(avg_trust, 1),
                'avg_compliance': round(avg_compliance, 1),
                'high_risk_vendors': high_risk_count,
                'critical_anomalies': critical_anomalies,
                'active_fraud_alerts': active_fraud_alerts,
                'open_investigations': open_cases
            },
            'recent_events': events,
            'active_cases': cases_list
        }), 200
    except Exception as e:
        logging.error(f"Error compiling command center telemetry: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
