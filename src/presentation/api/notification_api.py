from flask import Blueprint, request, jsonify
from src.domain.services.notification_service import NotificationService
from src.infrastructure.security.decorators import login_required, get_current_user
import logging

notification_api = Blueprint('notification_api', __name__)

@notification_api.route('/api/v2/notifications', methods=['GET'])
@login_required
def get_user_notifications():
    """API endpoint to retrieve role-based system notifications with search and archive options."""
    search = request.args.get('search')
    only_unread = request.args.get('only_unread', 'true').lower() == 'true'
    
    # Extract role from token header/claims (mocked or loaded)
    # We can check which role is currently simulated in headers
    role = request.headers.get('X-Role') or 'Viewer'
    
    notifs = NotificationService.query_notifications(role, search, only_unread)
    return jsonify({'success': True, 'notifications': notifs}), 200

@notification_api.route('/api/v2/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def read_notification(notif_id):
    """API endpoint to mark a specific notification as read."""
    result = NotificationService.mark_read(notif_id)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result), 200

@notification_api.route('/api/v2/notifications/<int:notif_id>/archive', methods=['POST'])
@login_required
def archive_notification(notif_id):
    """API endpoint to archive a specific notification alert."""
    result = NotificationService.archive_notif(notif_id)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result), 200

@notification_api.route('/api/v2/notifications/read-all', methods=['POST'])
@login_required
def read_all_notifications():
    """API endpoint to mark all notifications for the active role as read."""
    role = request.headers.get('X-Role') or 'Viewer'
    result = NotificationService.mark_all_read(role)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result), 200
