from flask import Blueprint, request, jsonify
from src.domain.services.anomaly_engine import AnomalyDetectionEngine
from src.infrastructure.database.models import VendorAnomaly
from src.infrastructure.security.decorators import login_required, role_required, get_current_user
import logging

anomaly_api = Blueprint('anomaly_api', __name__)

@anomaly_api.route('/api/v2/anomalies/scan', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward'])
def trigger_anomaly_scan():
    """Triggers the hybrid anomaly detection pipeline across the vendor cohort."""
    try:
        result = AnomalyDetectionEngine.execute_scan()
        if not result['success']:
            return jsonify(result), 400
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error triggering anomaly scan API: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@anomaly_api.route('/api/v2/anomalies', methods=['GET'])
@login_required
def get_detected_anomalies():
    """Retrieves detected anomalies with optional severity and status filters."""
    try:
        status = request.args.get('status', 'Active')
        severity = request.args.get('severity', 'All')
        
        query = VendorAnomaly.query.filter_by(status=status)
        if severity != 'All':
            query = query.filter_by(severity=severity)
            
        anomalies = query.all()
        return jsonify({
            'success': True,
            'anomalies': [a.to_dict() for a in anomalies]
        }), 200
    except Exception as e:
        logging.error(f"Error fetching anomalies list: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@anomaly_api.route('/api/v2/anomalies/<int:anomaly_id>/resolve', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward'])
def resolve_anomaly_alert(anomaly_id):
    """Updates the operational status of a flagged anomaly alert."""
    try:
        data = request.json or {}
        status = data.get('status', 'Resolved')
        auditor_info = get_current_user()
        auditor = auditor_info.get('email', 'Auditor') if isinstance(auditor_info, dict) else 'Auditor'
        
        result = AnomalyDetectionEngine.resolve_anomaly(anomaly_id, status, auditor)
        if not result['success']:
            return jsonify(result), 400
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error resolving anomaly alert API: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
