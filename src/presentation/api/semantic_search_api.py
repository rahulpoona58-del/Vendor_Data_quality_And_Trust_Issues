from flask import Blueprint, request, jsonify
from src.domain.services.semantic_search import SemanticSearchEngine
from src.infrastructure.security.decorators import login_required
import logging

semantic_search_api = Blueprint('semantic_search_api', __name__)

@semantic_search_api.route('/api/v2/search/semantic', methods=['GET'])
@login_required
def execute_semantic_search_route():
    """API endpoint evaluating TF-IDF text similarity matrices across all master tables."""
    try:
        query = request.args.get('query', '')
        result_type = request.args.get('type', 'All')
        
        if not query:
            return jsonify({'success': False, 'message': 'query parameter is required'}), 400
            
        result = SemanticSearchEngine.execute_semantic_search(query, result_type)
        if not result.get('success'):
            return jsonify(result), 400
            
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error serving semantic search API: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
