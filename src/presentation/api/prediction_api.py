from flask import Blueprint, request, jsonify
from src.domain.services.predictive_engine import PredictiveAnalyticsEngine
from src.infrastructure.security.decorators import login_required

prediction_api = Blueprint('prediction_api', __name__)

@prediction_api.route('/api/v2/predictive/telemetry', methods=['GET'])
@login_required
def get_predictive_telemetry():
    """API endpoint returning forecasted scoring trends, expiries, and threat vectors."""
    v_id = request.args.get('vendor_id')
    vendor_id = int(v_id) if v_id and v_id.isdigit() else None
    
    result = PredictiveAnalyticsEngine.generate_predictions(vendor_id)
    return jsonify(result), 200

@prediction_api.route('/api/v2/predictive/alerts', methods=['GET'])
@login_required
def get_predictive_alerts():
    """API endpoint returning concrete threat prediction warnings and confidence ratings."""
    v_id = request.args.get('vendor_id')
    if not v_id or not v_id.isdigit():
        return jsonify({'success': False, 'message': 'vendor_id parameter is required and must be numeric'}), 400
        
    alerts = PredictiveAnalyticsEngine.generate_predictive_alerts(int(v_id))
    return jsonify({'success': True, 'alerts': alerts}), 200
