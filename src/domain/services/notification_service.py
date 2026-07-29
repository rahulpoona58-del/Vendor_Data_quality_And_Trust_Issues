from datetime import datetime
from src.infrastructure.database.models import SystemNotification, db
import logging

class NotificationService:
    """Central orchestrator for role-based notifications, real-time alerts, and email notifications."""
    
    @staticmethod
    def create_notification(vendor_id: int, title: str, message: str, priority: str, category: str, target_roles: list) -> SystemNotification:
        """Saves a notification to the database and logs a mock email payload."""
        try:
            notif = SystemNotification(
                vendor_id=vendor_id,
                title=title,
                message=message,
                priority=priority,
                category=category,
                target_roles=target_roles
            )
            db.session.add(notif)
            db.session.commit()
            
            # Simulated Email Notification (Email placeholder logging)
            logging.info(
                f"[EMAIL TRANSMISSION MOCK] To: notifications@system.local "
                f"Subject: [{priority.upper()}] {title} "
                f"Body: {message} (Target Roles: {', '.join(target_roles)})"
            )
            
            return notif
        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to create notification alert: {str(e)}")
            return None

    @staticmethod
    def query_notifications(role: str, search: str = None, only_unread: bool = True) -> list:
        """Queries notifications directed to a specific role, supporting unread filters and search queries."""
        try:
            # We fetch all notifications
            query = SystemNotification.query.filter(SystemNotification.is_archived == False)
            
            if only_unread:
                query = query.filter(SystemNotification.is_read == False)
                
            if search:
                query = query.filter(
                    (SystemNotification.title.ilike(f"%{search}%")) |
                    (SystemNotification.message.ilike(f"%{search}%"))
                )
                
            all_notifs = query.order_by(SystemNotification.created_at.desc()).all()
            
            # Filter in Python to check if role exists in target_roles JSON array
            role_notifs = []
            for n in all_notifs:
                if role in n.target_roles or '*' in n.target_roles:
                    role_notifs.append(n.to_dict())
            return role_notifs
        except Exception as e:
            logging.error(f"Error querying notifications: {str(e)}")
            return []

    @staticmethod
    def mark_read(notif_id: int) -> dict:
        """Marks notification as read."""
        try:
            n = SystemNotification.query.get(notif_id)
            if not n:
                return {'success': False, 'message': 'Notification not found'}
            n.is_read = True
            db.session.commit()
            return {'success': True}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}

    @staticmethod
    def archive_notif(notif_id: int) -> dict:
        """Archives notification, hiding it from view."""
        try:
            n = SystemNotification.query.get(notif_id)
            if not n:
                return {'success': False, 'message': 'Notification not found'}
            n.is_archived = True
            db.session.commit()
            return {'success': True}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}

    @staticmethod
    def mark_all_read(role: str) -> dict:
        """Marks all active notifications for a role as read."""
        try:
            # Fetch unread notifications
            notifs = SystemNotification.query.filter_by(is_read=False, is_archived=False).all()
            updated_count = 0
            for n in notifs:
                if role in n.target_roles or '*' in n.target_roles:
                    n.is_read = True
                    updated_count += 1
            db.session.commit()
            return {'success': True, 'count': updated_count}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}
