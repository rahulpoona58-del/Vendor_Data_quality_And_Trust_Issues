from flask import Blueprint, request, jsonify
from src.domain.services.reputation_engine import ReputationIntelligenceEngine
from src.infrastructure.database.models import VendorReputation, Vendor
from src.infrastructure.security.decorators import login_required, role_required
import logging

reputation_api = Blueprint('reputation_api', __name__)

@reputation_api.route('/api/v2/reputations/calculate', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward'])
def trigger_reputation_calculations():
    """Triggers reputation intelligence scores calculations across the entire cohort."""
    try:
        version = request.json.get('version', 'v1.0') if request.json else 'v1.0'
        result = ReputationIntelligenceEngine.calculate_cohort_reputations(version)
        if not result['success']:
            return jsonify(result), 400
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error triggering reputations calculation API: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@reputation_api.route('/api/v2/reputations', methods=['GET'])
@login_required
def get_reputations_ranking():
    """Retrieves ranked reputation profiles with filters and sorting."""
    try:
        tier = request.args.get('tier', 'All')
        sort_by = request.args.get('sort_by', 'score') # score, confidence
        order = request.args.get('order', 'desc')
        
        query = VendorReputation.query
        if tier != 'All':
            query = query.filter_by(reputation_tier=tier)
            
        reps = query.all()
        
        # Map to dict and sort
        data = [r.to_dict() for r in reps]
        
        reverse_sort = order == 'desc'
        if sort_by == 'score':
            data.sort(key=lambda x: x['reputation_score'], reverse=reverse_sort)
        elif sort_by == 'confidence':
            data.sort(key=lambda x: x['confidence_level'], reverse=reverse_sort)
            
        return jsonify({
            'success': True,
            'reputations': data
        }), 200
    except Exception as e:
        logging.error(f"Error retrieving reputations list: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@reputation_api.route('/api/v2/reputations/<int:vendor_id>', methods=['GET'])
@login_required
def get_vendor_reputation_details(vendor_id):
    """Retrieves detailed reputation intelligence, breakdowns, and trendlines."""
    try:
        rep = VendorReputation.query.filter_by(vendor_id=vendor_id).first()
        if not rep:
            # Calculate dynamically on fly if missing
            res = ReputationIntelligenceEngine.calculate_reputation(vendor_id)
            if not res['success']:
                return jsonify(res), 400
            return jsonify(res), 200
            
        return jsonify({
            'success': True,
            'reputation': rep.to_dict()
        }), 200
    except Exception as e:
        logging.error(f"Error fetching vendor reputation details: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@reputation_api.route('/api/v2/reputations/compare', methods=['GET'])
@login_required
def compare_vendors_reputations():
    """Compares reputation metrics side-by-side for a list of target vendor IDs."""
    try:
        ids_str = request.args.get('vendor_ids', '')
        if not ids_str:
            return jsonify({'success': False, 'message': 'vendor_ids comma-separated query parameter required'}), 400
            
        vids = [int(x.strip()) for x in ids_str.split(',') if x.strip().isdigit()]
        
        comparisons = []
        for vid in vids:
            rep = VendorReputation.query.filter_by(vendor_id=vid).first()
            if not rep:
                res = ReputationIntelligenceEngine.calculate_reputation(vid)
                if res['success']:
                    comparisons.append(res['reputation'])
            else:
                comparisons.append(rep.to_dict())
                
        return jsonify({
            'success': True,
            'comparisons': comparisons
        }), 200
    except Exception as e:
        logging.error(f"Error comparing vendor reputations: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
