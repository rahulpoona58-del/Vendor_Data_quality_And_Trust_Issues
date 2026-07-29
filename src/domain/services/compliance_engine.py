from datetime import datetime, timedelta
from src.infrastructure.database.models import Vendor, VendorDocument, VendorComplianceStatus, ComplianceLog, ComplianceNotification, db
import logging

class ComplianceEngine:
    """Enterprise Compliance Engine computing status scores, checking document expiries, and logging timelines."""
    
    REQUIRED_DOCS = {
        'GST Certificate': 20,
        'PAN Card': 15,
        'Company Registration Certificate': 15,
        'ISO Certificates': 10,
        'Vendor Contracts': 15,
        'NDA Documents': 15,
        'Insurance Documents': 10
    }
    
    @staticmethod
    def evaluate_compliance(vendor_id: int) -> dict:
        """Calculates compliance score, checks file expiries, generates alert warnings, and commits history logs."""
        try:
            vendor = Vendor.query.get(vendor_id)
            if not vendor:
                return {'success': False, 'message': 'Vendor not found'}
                
            docs = VendorDocument.query.filter_by(vendor_id=vendor.id, is_deleted=False).all()
            
            # Map existing documents by type
            doc_map = {}
            for d in docs:
                # Store the newest version/highest ID for each type
                if d.document_type not in doc_map or d.id > doc_map[d.document_type].id:
                    doc_map[d.document_type] = d
                    
            compliance_score = 0.0
            log_entries = []
            now = datetime.utcnow()
            
            # 1. Evaluate Checklist scoring
            checklist_results = {}
            for doc_type, points in ComplianceEngine.REQUIRED_DOCS.items():
                d = doc_map.get(doc_type)
                if not d:
                    checklist_results[doc_type] = {'status': 'Missing', 'points': 0}
                elif d.verification_status == 'Rejected':
                    checklist_results[doc_type] = {'status': 'Rejected', 'points': 0}
                elif d.expiry_date and d.expiry_date < now:
                    checklist_results[doc_type] = {'status': 'Expired', 'points': round(points * 0.3, 1)}
                    compliance_score += points * 0.3
                    
                    # Expiry notification
                    ComplianceEngine._trigger_notification(
                        vendor_id=vendor.id,
                        doc_id=d.id,
                        title=f"{doc_type} Expired",
                        message=f"The uploaded {doc_type} expired on {d.expiry_date.strftime('%Y-%m-%d')}.",
                        alert_type='Critical'
                    )
                elif d.verification_status == 'Pending':
                    checklist_results[doc_type] = {'status': 'Pending Verification', 'points': round(points * 0.6, 1)}
                    compliance_score += points * 0.6
                else: # Verified & Active
                    checklist_results[doc_type] = {'status': 'Verified', 'points': points}
                    compliance_score += points
                    
                    # Check if expiring soon
                    if d.expiry_date:
                        days_left = (d.expiry_date - now).days
                        if 0 < days_left <= 30:
                            ComplianceEngine._trigger_notification(
                                vendor_id=vendor.id,
                                doc_id=d.id,
                                title=f"{doc_type} Expiring Soon",
                                message=f"The uploaded {doc_type} will expire in {days_left} days.",
                                alert_type='Warning'
                            )
                            
            # Round score
            compliance_score = round(compliance_score, 1)
            
            # 2. Determine Approval status
            # Check fraud flags
            from src.infrastructure.database.models import FraudCheck
            fraud = FraudCheck.query.filter_by(vendor_id=vendor.id).first()
            fraud_score = fraud.fraud_score if fraud else 0.0
            
            approval_status = 'Pending Approval'
            status_reason = "Requirements scanning initialized."
            
            if compliance_score >= 80.0 and fraud_score < 40.0:
                approval_status = 'Approved'
                status_reason = f"Compliance criteria met ({compliance_score} Pts) with low fraud risk."
            elif fraud_score >= 70.0:
                approval_status = 'Suspended'
                status_reason = f"Suspended due to high-risk fraud flag ({fraud_score} Score)."
            elif compliance_score < 50.0:
                approval_status = 'Pending Approval'
                status_reason = "Profile completeness below minimum 50% threshold."
                
            # 3. Update Vendor Compliance record
            comp_status = VendorComplianceStatus.query.filter_by(vendor_id=vendor.id).first()
            if not comp_status:
                comp_status = VendorComplianceStatus(
                    vendor_id=vendor.id,
                    compliance_score=compliance_score,
                    approval_status=approval_status,
                    audited_by='System Engine'
                )
                db.session.add(comp_status)
            else:
                comp_status.compliance_score = compliance_score
                comp_status.approval_status = approval_status
                comp_status.last_audited_at = now

            # Evaluate custom business rules for Compliance group
            from src.domain.services.business_rules_engine import BusinessRulesEngine
            rule_actions = BusinessRulesEngine.evaluate_rules(vendor.id, 'Compliance')
            for action_item in rule_actions:
                action = action_item.get('action', {})
                act_name = action.get('action')
                if act_name == 'reject_vendor':
                    comp_status.approval_status = 'Rejected'
                    status_reason = f"Rejected by business rule '{action_item['rule_name']}': {action.get('reason', '')}"
                elif act_name == 'suspend_vendor':
                    comp_status.approval_status = 'Suspended'
                    status_reason = f"Suspended by business rule '{action_item['rule_name']}': {action.get('reason', '')}"
                elif act_name == 'adjust_compliance_score':
                    try:
                        adjustment = float(action.get('param', 0))
                        comp_status.compliance_score = max(0.0, min(100.0, comp_status.compliance_score + adjustment))
                        compliance_score = comp_status.compliance_score
                    except ValueError:
                        pass

            # Log event to timeline
            log_record = ComplianceLog(
                vendor_id=vendor.id,
                compliance_score=compliance_score,
                status=comp_status.approval_status,
                description=status_reason
            )
            db.session.add(log_record)
            db.session.commit()
            
            # Log timeline activity
            from src.domain.services.timeline_service import TimelineService
            TimelineService.log_activity(
                vendor_id=vendor.id,
                activity_type='Compliance Updated',
                description=f"Compliance check run: score updated to {compliance_score}% (Status: {approval_status})."
            )
            
            logging.info(f"Vendor compliance calculated: vendor_id={vendor.id} score={compliance_score} status={approval_status}")
            return {
                'success': True,
                'compliance_status': comp_status.to_dict(),
                'checklist': checklist_results,
                'log': log_record.to_dict()
            }
        except Exception as e:
            db.session.rollback()
            logging.error(f"Compliance engine evaluation failed: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def get_compliance_timeline(vendor_id: int, limit: int = 10) -> list:
        """Retrieves history of compliance status checks."""
        logs = ComplianceLog.query.filter_by(vendor_id=vendor_id)\
                                  .order_by(ComplianceLog.logged_at.desc())\
                                  .limit(limit).all()
        return [l.to_dict() for l in logs]

    @staticmethod
    def get_notifications(vendor_id: int) -> list:
        """Retrieves unread compliance notifications and alerts."""
        notifs = ComplianceNotification.query.filter_by(vendor_id=vendor_id, is_read=False)\
                                             .order_by(ComplianceNotification.created_at.desc()).all()
        return [n.to_dict() for n in notifs]

    @staticmethod
    def mark_notification_read(notif_id: int) -> dict:
        """Archives a notification alert."""
        try:
            n = ComplianceNotification.query.get(notif_id)
            if not n:
                return {'success': False, 'message': 'Notification not found'}
            n.is_read = True
            db.session.commit()
            return {'success': True}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}

    @staticmethod
    def set_approval_status(vendor_id: int, status: str, reviewer: str) -> dict:
        """Manual overwrite for auditor approval workflows."""
        try:
            comp_status = VendorComplianceStatus.query.filter_by(vendor_id=vendor_id).first()
            if not comp_status:
                return {'success': False, 'message': 'Compliance profile not found. Run scan first.'}
                
            if status not in {'Approved', 'Pending Approval', 'Rejected', 'Suspended'}:
                return {'success': False, 'message': 'Invalid approval status'}
                
            old_status = comp_status.approval_status
            comp_status.approval_status = status
            comp_status.audited_by = reviewer
            comp_status.last_audited_at = datetime.utcnow()
            
            # Log manual audit change
            log_record = ComplianceLog(
                vendor_id=vendor_id,
                compliance_score=comp_status.compliance_score,
                status=status,
                description=f"Manual status update to '{status}' by reviewer {reviewer}."
            )
            db.session.add(log_record)
            db.session.commit()
            
            # Log timeline activity
            from src.domain.services.timeline_service import TimelineService
            act_type = 'Approval' if status == 'Approved' else ('Rejection' if status == 'Rejected' else 'Compliance Updated')
            TimelineService.log_activity(
                vendor_id=vendor_id,
                activity_type=act_type,
                description=f"Vendor Approval Status set to '{status}' by auditor {reviewer}.",
                performed_by=reviewer
            )
            
            # System Audit Log
            from src.domain.services.audit_service import AuditService
            AuditService.log_audit(
                performed_by=reviewer,
                ip_address='127.0.0.1',
                action_type="Override Approval Status",
                module_name="Compliance",
                old_value={"status": old_status},
                new_value={"status": status},
                reason=f"Auditor review override: {status}",
                vendor_id=vendor_id
            )
            
            # Trigger System Notification
            from src.domain.services.notification_service import NotificationService
            NotificationService.create_notification(
                vendor_id=vendor_id,
                title=f"Vendor status: {status}",
                message=f"Auditor {reviewer} manually changed vendor status to '{status}'.",
                priority="High",
                category="System",
                target_roles=["Admin", "Manager", "Viewer"]
            )
            
            return {'success': True, 'compliance_status': comp_status.to_dict()}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}

    @staticmethod
    def _trigger_notification(vendor_id: int, doc_id: int, title: str, message: str, alert_type: str):
        """Creates notification entry, preventing duplicate unread alerts."""
        existing = ComplianceNotification.query.filter_by(
            vendor_id=vendor_id,
            document_id=doc_id,
            title=title,
            is_read=False
        ).first()
        
        if not existing:
            new_notif = ComplianceNotification(
                vendor_id=vendor_id,
                document_id=doc_id,
                title=title,
                message=message,
                alert_type=alert_type
            )
            db.session.add(new_notif)
            
            # Register in centralized SystemNotification center
            from src.domain.services.notification_service import NotificationService
            priority = "Critical" if alert_type == "Critical" else "Medium"
            NotificationService.create_notification(
                vendor_id=vendor_id,
                title=title,
                message=message,
                priority=priority,
                category="Compliance",
                target_roles=["Admin", "Data Steward"]
            )
