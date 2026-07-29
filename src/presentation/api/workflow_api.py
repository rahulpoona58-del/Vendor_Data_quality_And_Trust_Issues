from flask import Blueprint, jsonify, request
from src.domain.services.workflow_engine import WorkflowEngine
from src.infrastructure.security.decorators import login_required, get_current_user
from src.infrastructure.database.models import User
import logging

workflow_api = Blueprint('workflow_api', __name__)

@workflow_api.route('/api/v2/workflow/<int:vendor_id>', methods=['GET'])
@login_required
def get_workflow_details(vendor_id):
    """API endpoint to retrieve the current approval workflow details and history log."""
    try:
        wf_data = WorkflowEngine.get_or_create_workflow(vendor_id)
        if isinstance(wf_data, dict) and wf_data.get('success') is False:
            return jsonify(wf_data), 400
        return jsonify({'success': True, 'workflow': wf_data}), 200
    except Exception as e:
        logging.error(f"Error retrieving workflow details: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@workflow_api.route('/api/v2/workflow/<int:vendor_id>/action', methods=['POST'])
@login_required
def apply_workflow_action(vendor_id):
    """API endpoint to execute a stage transition (Submit, Approve, Reject, Escalate, etc.) with role checks."""
    try:
        data = request.get_json() or {}
        action = data.get('action')
        comment = data.get('comment', '')
        
        if not action:
            return jsonify({'success': False, 'message': 'Missing workflow action command.'}), 400
            
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
            
        # Retrieve user email as the actor name
        db_user = User.query.get(user['user_id'])
        actor_name = db_user.email if db_user else f"User_{user['user_id']}"
        actor_role = user['role']
        ip_addr = request.remote_addr or '127.0.0.1'
        
        res = WorkflowEngine.transition_stage(
            vendor_id=vendor_id,
            action=action,
            actor_name=actor_name,
            actor_role=actor_role,
            comment=comment,
            ip_address=ip_addr
        )
        
        if not res.get('success'):
            return jsonify(res), 400
            
        return jsonify(res), 200
        
    except Exception as e:
        logging.error(f"Error executing workflow transition: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@workflow_api.route('/api/v2/workflow/reminders', methods=['POST'])
@login_required
def trigger_workflow_reminders():
    """API endpoint to run automated review reminder checks on inactive review files."""
    try:
        data = request.get_json() or {}
        threshold = data.get('threshold_seconds', 3600)
        res = WorkflowEngine.send_review_reminders(threshold)
        return jsonify(res), 200
    except Exception as e:
        logging.error(f"Error running reminders: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@workflow_api.route('/api/v2/workflow/escalate', methods=['POST'])
@login_required
def trigger_workflow_escalations():
    """API endpoint to run automated escalation checks shifting overdue reviews to higher roles."""
    try:
        data = request.get_json() or {}
        threshold = data.get('threshold_seconds', 7200)
        res = WorkflowEngine.escalate_overdue_workflows(threshold)
        return jsonify(res), 200
    except Exception as e:
        logging.error(f"Error running escalations: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
