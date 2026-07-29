from datetime import datetime, timedelta
from src.infrastructure.database.models import SystemAuditLog, db
import logging

class AuditService:
    """Orchestrates system-wide audit registries and transaction logging."""
    
    @staticmethod
    def log_audit(performed_by: str, ip_address: str, action_type: str, module_name: str, old_value: dict = None, new_value: dict = None, reason: str = None, vendor_id: int = None, original_source: str = None, import_source: str = None, ai_suggested: bool = False, human_approved: bool = False, validation_result: str = None):
        """Creates and commits an audit log registry entry."""
        try:
            log = SystemAuditLog(
                vendor_id=vendor_id,
                performed_by=performed_by,
                ip_address=ip_address or '127.0.0.1',
                action_type=action_type,
                module_name=module_name,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                original_source=original_source,
                import_source=import_source,
                ai_suggested=ai_suggested,
                human_approved=human_approved,
                validation_result=validation_result
            )
            db.session.add(log)
            db.session.commit()
            logging.info(f"Audit log recorded: {action_type} inside {module_name} by {performed_by}")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to record system audit log: {str(e)}")

    @staticmethod
    def query_audit_logs(search: str = None, module: str = None, start_date: str = None, end_date: str = None, vendor_id: int = None, page: int = None, per_page: int = None):
        """Fetches system audit logs matching criteria with optional pagination."""
        try:
            query = SystemAuditLog.query
            
            if vendor_id:
                query = query.filter_by(vendor_id=vendor_id)
                
            if module and module != 'All':
                query = query.filter_by(module_name=module)
                
            if search:
                safe_search = str(search).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                query = query.filter(
                    (SystemAuditLog.performed_by.ilike(f"%{safe_search}%")) |
                    (SystemAuditLog.action_type.ilike(f"%{safe_search}%")) |
                    (SystemAuditLog.reason.ilike(f"%{safe_search}%"))
                )
                
            if start_date:
                try:
                    s_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    query = query.filter(SystemAuditLog.created_at >= s_dt)
                except ValueError:
                    pass
                    
            if end_date:
                try:
                    e_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                    query = query.filter(SystemAuditLog.created_at < e_dt)
                except ValueError:
                    pass
                    
            query = query.order_by(SystemAuditLog.created_at.desc())
            
            if page is not None or per_page is not None:
                from src.domain.services.pagination_helper import paginate_query
                return paginate_query(query, page=page or 1, per_page=per_page or 20)
                
            logs = query.all()
            return [l.to_dict() for l in logs]
        except Exception as e:
            logging.error(f"Error querying system audit logs: {str(e)}")
            return [] if page is None else {'items': [], 'pagination': {'total': 0, 'page': 1, 'per_page': 20, 'pages': 1}}
