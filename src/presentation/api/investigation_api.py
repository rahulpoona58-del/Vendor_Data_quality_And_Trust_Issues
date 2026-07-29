from flask import Blueprint, request, jsonify
from src.domain.services.investigation_service import InvestigationService
from src.infrastructure.database.models import InvestigationCase
from src.infrastructure.security.decorators import login_required, role_required, get_current_user
import logging

investigation_api = Blueprint('investigation_api', __name__)

@investigation_api.route('/api/v2/investigations/open', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward', 'Auditor'])
def open_investigation_case():
    """Opens a new investigation case folder for a suspicious vendor."""
    try:
        data = request.json or {}
        vendor_id = data.get('vendor_id')
        priority = data.get('priority', 'Medium')
        
        if not vendor_id:
            return jsonify({'success': False, 'message': 'vendor_id parameter is required'}), 400
            
        user = get_current_user()
        auditor = user.get('email', 'Auditor') if isinstance(user, dict) else 'Auditor'
        
        result = InvestigationService.open_case(int(vendor_id), priority, auditor)
        if not result.get('success'):
            return jsonify(result), 400
            
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error opening investigation case API: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@investigation_api.route('/api/v2/investigations', methods=['GET'])
@login_required
def list_investigation_cases():
    """Retrieves all registered investigation cases."""
    try:
        status = request.args.get('status')
        priority = request.args.get('priority')
        
        query = InvestigationCase.query
        if status:
            query = query.filter_by(status=status)
        if priority:
            query = query.filter_by(priority=priority)
            
        cases = query.all()
        return jsonify({
            'success': True,
            'cases': [c.to_dict() for c in cases]
        }), 200
    except Exception as e:
        logging.error(f"Error listing cases API: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@investigation_api.route('/api/v2/investigations/<int:case_id>', methods=['GET'])
@login_required
def get_case_by_id(case_id):
    """Retrieves a single investigation case record detail."""
    try:
        case = InvestigationCase.query.get(case_id)
        if not case:
            return jsonify({'success': False, 'message': 'Case file not found'}), 404
        return jsonify({'success': True, 'case': case.to_dict()}), 200
    except Exception as e:
        logging.error(f"Error fetching case details API: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@investigation_api.route('/api/v2/investigations/<int:case_id>/workflow', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward', 'Auditor'])
def update_case_workflow_status(case_id):
    """Transitions case states, priorities, or assignees."""
    try:
        data = request.json or {}
        status = data.get('status', 'Open')
        priority = data.get('priority', 'Medium')
        assigned_to = data.get('assigned_to')
        
        user = get_current_user()
        auditor = user.get('email', 'Auditor') if isinstance(user, dict) else 'Auditor'
        
        result = InvestigationService.update_case_workflow(
            case_id=case_id,
            status=status,
            priority=priority,
            assigned_to=assigned_to,
            auditor=auditor
        )
        if not result.get('success'):
            return jsonify(result), 400
            
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error updating case workflow API: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@investigation_api.route('/api/v2/investigations/<int:case_id>/note', methods=['POST'])
@login_required
def add_case_note(case_id):
    """Appends an evidence note to the case logs folder."""
    try:
        data = request.json or {}
        note_text = data.get('note_text')
        
        if not note_text:
            return jsonify({'success': False, 'message': 'note_text parameter is required'}), 400
            
        user = get_current_user()
        author = user.get('email', 'Auditor') if isinstance(user, dict) else 'Auditor'
        
        result = InvestigationService.add_evidence_note(case_id, note_text, author)
        if not result.get('success'):
            return jsonify(result), 400
            
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error adding note API: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@investigation_api.route('/api/v2/investigations/<int:case_id>/link', methods=['POST'])
@login_required
def link_vendor_to_case(case_id):
    """Links a secondary suspicious vendor to the case file."""
    try:
        data = request.json or {}
        target_vendor_id = data.get('target_vendor_id')
        
        if not target_vendor_id:
            return jsonify({'success': False, 'message': 'target_vendor_id parameter is required'}), 400
            
        user = get_current_user()
        author = user.get('email', 'Auditor') if isinstance(user, dict) else 'Auditor'
        
        result = InvestigationService.link_related_vendor(case_id, int(target_vendor_id), author)
        if not result.get('success'):
            return jsonify(result), 400
            
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error linking vendor API: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
