from flask import Blueprint, request, jsonify
from src.domain.services.recommendation_engine import RecommendationEngine
from src.infrastructure.security.decorators import login_required
import logging

recommendation_api = Blueprint('recommendation_api', __name__)

@recommendation_api.route('/api/v2/vendors/<int:vendor_id>/recommendations', methods=['GET'])
@login_required
def get_vendor_recommendations(vendor_id):
    """API endpoint to analyze vendor files and list fresh AI recommendations."""
    # Regenerate fresh items
    recs = RecommendationEngine.generate_recommendations(vendor_id)
    return jsonify({'success': True, 'recommendations': recs}), 200

@recommendation_api.route('/api/v2/recommendations/<int:rec_id>/apply', methods=['POST'])
@login_required
def apply_rec(rec_id):
    """API endpoint to trigger one-click approval apply actions for recommendations."""
    role = request.headers.get('X-Role') or 'Viewer'
    
    # Restrict application to Admin/Auditor/Manager
    if role not in {'Admin', 'Auditor', 'Manager'}:
        return jsonify({'success': False, 'message': 'Insufficient role permissions'}), 403
        
    result = RecommendationEngine.apply_recommendation(rec_id, reviewer=f"{role.lower()}@system.local")
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result), 200

@recommendation_api.route('/api/v2/recommendations/<int:rec_id>/reject', methods=['POST'])
@login_required
def reject_rec(rec_id):
    """API endpoint to dismiss or reject recommendations."""
    role = request.headers.get('X-Role') or 'Viewer'
    
    if role not in {'Admin', 'Auditor', 'Manager'}:
        return jsonify({'success': False, 'message': 'Insufficient role permissions'}), 403
        
    result = RecommendationEngine.reject_recommendation(rec_id, reviewer=f"{role.lower()}@system.local")
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result), 200
