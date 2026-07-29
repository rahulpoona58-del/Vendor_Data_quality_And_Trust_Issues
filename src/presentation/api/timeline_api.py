from flask import Blueprint, request, jsonify
from src.domain.services.timeline_service import TimelineService
from src.infrastructure.security.decorators import login_required
import logging

timeline_api = Blueprint('timeline_api', __name__)

@timeline_api.route('/api/v2/vendors/<int:vendor_id>/activities', methods=['GET'])
@login_required
def get_vendor_timeline(vendor_id):
    """API endpoint to query chronological vendor milestone log timelines with search/date filters."""
    search = request.args.get('search')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    activities = TimelineService.query_timeline(
        vendor_id=vendor_id,
        search=search,
        start_date=start_date,
        end_date=end_date
    )
    return jsonify({'success': True, 'activities': activities}), 200
