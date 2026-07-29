from datetime import datetime
from src.infrastructure.database.models import VendorActivity, db
import logging

class TimelineService:
    """Orchestrates system audit trails and logs chronological milestones."""
    
    @staticmethod
    def log_activity(vendor_id: int, activity_type: str, description: str, performed_by: str = 'System', metadata: dict = None):
        """Creates and commits a new activity record in the database."""
        try:
            act = VendorActivity(
                vendor_id=vendor_id,
                activity_type=activity_type,
                description=description,
                performed_by=performed_by,
                metadata_json=metadata
            )
            db.session.add(act)
            db.session.commit()
            logging.debug(f"Activity logged: {activity_type} for vendor {vendor_id}")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to log vendor timeline activity: {str(e)}")

    @staticmethod
    def query_timeline(vendor_id: int, search: str = None, start_date: str = None, end_date: str = None) -> list:
        """Queries timeline entries filtered by date bounds and description strings."""
        try:
            query = VendorActivity.query.filter_by(vendor_id=vendor_id)
            
            if search:
                query = query.filter(
                    (VendorActivity.description.ilike(f"%{search}%")) |
                    (VendorActivity.activity_type.ilike(f"%{search}%")) |
                    (VendorActivity.performed_by.ilike(f"%{search}%"))
                )
                
            if start_date:
                try:
                    s_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    query = query.filter(VendorActivity.created_at >= s_dt)
                except ValueError:
                    pass
                    
            if end_date:
                try:
                    e_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                    query = query.filter(VendorActivity.created_at < e_dt)
                except ValueError:
                    pass
                    
            activities = query.order_by(VendorActivity.created_at.desc()).all()
            return [a.to_dict() for a in activities]
        except Exception as e:
            logging.error(f"Error querying timeline logs: {str(e)}")
            return []
