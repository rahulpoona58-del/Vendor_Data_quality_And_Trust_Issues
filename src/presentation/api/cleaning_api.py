from flask import Blueprint, request, jsonify
from src.domain.services.cleaning_engine import DataCleaningEngine
from src.infrastructure.database.models import DataCleaningSuggestion
from src.infrastructure.security.decorators import login_required, role_required, get_current_user
import logging

cleaning_api = Blueprint('cleaning_api', __name__)

@cleaning_api.route('/api/v2/vendors/<int:vendor_id>/cleaning/scan', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward', 'Manager'])
def run_data_cleaning_scan(vendor_id):
    """API endpoint to trigger a data quality cleaning scan."""
    result = DataCleaningEngine.scan_vendor(vendor_id)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result), 200

@cleaning_api.route('/api/v2/vendors/<int:vendor_id>/cleaning/suggestions', methods=['GET'])
@login_required
def get_cleaning_suggestions(vendor_id):
    """API endpoint to retrieve pending cleansing recommendations."""
    status = request.args.get('status', 'Pending')
    sugs = DataCleaningSuggestion.query.filter_by(vendor_id=vendor_id, status=status).all()
    return jsonify({'success': True, 'suggestions': [s.to_dict() for s in sugs]})

@cleaning_api.route('/api/v2/cleaning/suggestions/<int:suggestion_id>/approve', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward'])
def approve_suggestion(suggestion_id):
    """API endpoint to approve and apply a data normalization suggestion."""
    result = DataCleaningEngine.apply_suggestion(suggestion_id)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result)

@cleaning_api.route('/api/v2/cleaning/suggestions/<int:suggestion_id>/reject', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward'])
def reject_suggestion(suggestion_id):
    """API endpoint to reject a data cleansing suggestion."""
    result = DataCleaningEngine.reject_suggestion(suggestion_id)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result)

@cleaning_api.route('/api/v2/vendors/<int:vendor_id>/cleaning/bulk-apply', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward'])
def bulk_apply_cleaning(vendor_id):
    """API endpoint to bulk-approve all active recommendations for a vendor."""
    result = DataCleaningEngine.bulk_apply_suggestions(vendor_id)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result)
