from flask import Blueprint, request, jsonify
from src.domain.services.copilot_service import CopilotService
from src.infrastructure.security.decorators import login_required
from src.infrastructure.security.rate_limiter import rate_limit
import uuid

copilot_api = Blueprint('copilot_api', __name__)

@copilot_api.route('/api/v2/copilot/chat', methods=['POST'])
@login_required
@rate_limit('ai')
def chat():
    """API endpoint to process user natural language questions."""
    data = request.get_json() or {}
    message = data.get('message')
    session_id = data.get('session_id')
    
    if not message:
        return jsonify({'success': False, 'message': 'Message is required'}), 400
        
    if not session_id:
        session_id = str(uuid.uuid4())
        
    response_text = CopilotService.process_query(session_id, message)
    return jsonify({
        'success': True,
        'session_id': session_id,
        'response': response_text
    }), 200

@copilot_api.route('/api/v2/copilot/history', methods=['GET'])
@login_required
def get_chat_history():
    """API endpoint to retrieve chat message history logs."""
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({'success': False, 'message': 'session_id is required'}), 400
        
    history = CopilotService.get_history(session_id)
    return jsonify({'success': True, 'history': history}), 200
