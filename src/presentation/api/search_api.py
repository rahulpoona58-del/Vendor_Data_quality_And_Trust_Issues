from flask import Blueprint, request, jsonify
from src.domain.services.search_engine import SmartSearchEngine
from src.infrastructure.security.decorators import login_required
from src.infrastructure.security.rate_limiter import rate_limit
from src.infrastructure.cache.cache_service import cache_response

search_api = Blueprint('search_api', __name__)

@search_api.route('/api/v2/search', methods=['GET'])
@login_required
@rate_limit('search')
@cache_response(ttl_seconds=15)
def smart_search():
    """API endpoint evaluating NLP patterns and keywords for smart search registries."""
    query = request.args.get('query', '')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    sort_by = request.args.get('sort_by')
    order = request.args.get('order', 'desc')
    category = request.args.get('category')
    trust_level = request.args.get('trust_level')
    
    result = SmartSearchEngine.execute_search(
        query=query,
        page=page,
        limit=limit,
        sort_by=sort_by,
        order=order,
        category=category,
        trust_level=trust_level
    )
    return jsonify(result), 200

@search_api.route('/api/v2/search/autocomplete', methods=['GET'])
@login_required
def autocomplete():
    """API endpoint returning search suggestions and dynamic prefix completion lists."""
    prefix = request.args.get('prefix', '')
    if not prefix:
        return jsonify({'success': True, 'suggestions': []}), 200
        
    suggestions = SmartSearchEngine.get_suggestions(prefix)
    return jsonify({'success': True, 'suggestions': suggestions}), 200

@search_api.route('/api/v2/vendors/<int:vendor_id>', methods=['GET'])
@login_required
def get_vendor_by_id(vendor_id):
    """API endpoint returning a single vendor's complete master telemetry details."""
    from src.infrastructure.database.models import Vendor
    v = Vendor.query.get(vendor_id)
    if not v:
        return jsonify({'success': False, 'message': 'Vendor profile not found'}), 404
    return jsonify({'success': True, 'vendor': v.to_dict()}), 200

@search_api.route('/api/v2/vendors/search', methods=['GET'])
@login_required
def vendors_list_search():
    """Exposes search route aligned with the client dashboard fetches."""
    query = request.args.get('query', '')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    sort_by = request.args.get('sort_by')
    order = request.args.get('order', 'desc')
    category = request.args.get('category')
    trust_level = request.args.get('trust_level')
    
    result = SmartSearchEngine.execute_search(
        query=query,
        page=page,
        limit=limit,
        sort_by=sort_by,
        order=order,
        category=category,
        trust_level=trust_level
    )
    return jsonify(result), 200
