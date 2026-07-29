import logging
from datetime import datetime, timedelta
from src.infrastructure.database.models import db, Vendor, VendorApprovalWorkflow, VendorApprovalHistory, SystemNotification
from src.domain.services.audit_service import AuditService
from src.domain.services.event_queue import EventQueue

class WorkflowEngine:
    """Approval Workflow Engine supporting multi-level role-based states, history, audit trails, and escalations."""
    
    @staticmethod
    def get_or_create_workflow(vendor_id: int) -> dict:
        """Retrieves or initializes a workflow tracking record for the specified vendor."""
        try:
            wf = VendorApprovalWorkflow.query.filter_by(vendor_id=vendor_id).first()
            if not wf:
                wf = VendorApprovalWorkflow(
                    vendor_id=vendor_id,
                    current_stage='Draft',
                    required_level=1,
                    assigned_role='Data Steward'
                )
                db.session.add(wf)
                db.session.commit()
                
                # Log initial history step
                history = VendorApprovalHistory(
                    workflow_id=wf.id,
                    actor_name='System',
                    actor_role='System',
                    from_stage='None',
                    to_stage='Draft',
                    action='Initialize',
                    comment='Approval workflow initialized.'
                )
                db.session.add(history)
                db.session.commit()
                
            return wf.to_dict()
        except Exception as e:
            logging.error(f"Error fetching/creating workflow: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def transition_stage(vendor_id: int, action: str, actor_name: str, actor_role: str, comment: str = None, ip_address: str = "127.0.0.1") -> dict:
        """Processes workflow transitions with role checks, escalations, audits, notifications, and telemetry triggers."""
        try:
            wf = VendorApprovalWorkflow.query.filter_by(vendor_id=vendor_id).first()
            if not wf:
                # Initialize first
                WorkflowEngine.get_or_create_workflow(vendor_id)
                wf = VendorApprovalWorkflow.query.filter_by(vendor_id=vendor_id).first()
                
            vendor = Vendor.query.get(vendor_id)
            if not vendor:
                return {'success': False, 'message': 'Vendor profile not found.'}
                
            from_stage = wf.current_stage
            to_stage = from_stage
            
            # Stage Transition Mapping & Security Validations
            if action == 'Submit':
                if from_stage not in ['Draft', 'Rejected']:
                    return {'success': False, 'message': f'Cannot submit workflow from stage: {from_stage}'}
                to_stage = 'Submitted'
                wf.required_level = 1
                if vendor.trust_score < 50.0:
                    wf.assigned_role = 'Admin'
                    comment = comment or "Auto-assigned to Admin due to high risk (trust score < 50)."
                else:
                    wf.assigned_role = 'Data Steward'
                    comment = comment or "Auto-assigned to Data Steward."
                
            elif action == 'StartReview':
                if from_stage != 'Submitted':
                    return {'success': False, 'message': f'Can only start review on submitted files. Current: {from_stage}'}
                if actor_role not in ['Data Steward', 'Admin']:
                    return {'success': False, 'message': 'Only a Data Steward or Admin can start reviews.'}
                to_stage = 'Under Review'
                
            elif action == 'Approve':
                if from_stage not in ['Submitted', 'Under Review']:
                    return {'success': False, 'message': f'Cannot approve from stage: {from_stage}'}
                
                # Role and Level Check
                if wf.required_level == 1:
                    if actor_role not in ['Data Steward', 'Admin']:
                        return {'success': False, 'message': 'Level 1 approval requires Data Steward or Admin role.'}
                    # Advance to level 2
                    wf.required_level = 2
                    wf.assigned_role = 'Manager'
                    to_stage = 'Under Review' # Level 2 review stage
                elif wf.required_level == 2:
                    if actor_role not in ['Manager', 'Admin']:
                        return {'success': False, 'message': 'Level 2 approval requires Manager or Admin role.'}
                    to_stage = 'Approved'
                    vendor.status = 'Active' # Automatically activate vendor on final approval
                    
            elif action == 'Reject':
                if from_stage not in ['Submitted', 'Under Review']:
                    return {'success': False, 'message': f'Cannot reject from stage: {from_stage}'}
                if actor_role not in ['Data Steward', 'Manager', 'Admin']:
                    return {'success': False, 'message': 'Unauthorized role for rejection actions.'}
                to_stage = 'Rejected'
                vendor.status = 'Inactive' # Automatically mark vendor inactive/rejected
                
            elif action == 'Escalate':
                if from_stage not in ['Submitted', 'Under Review']:
                    return {'success': False, 'message': 'Can only escalate active pending reviews.'}
                wf.assigned_role = 'Admin' # Escalate directly to Administrator
                # Keep in Under Review but marked for Admin
                to_stage = 'Under Review'
                
            elif action == 'Archive':
                if actor_role not in ['Admin', 'Manager']:
                    return {'success': False, 'message': 'Only Admins or Managers can archive workflows.'}
                to_stage = 'Archived'
                vendor.status = 'Blocked'
                
            else:
                return {'success': False, 'message': f'Unknown action command: {action}'}
                
            # Commit Stage Transitions
            wf.current_stage = to_stage
            wf.updated_at = datetime.utcnow()
            
            # Log History Transition Step
            history = VendorApprovalHistory(
                workflow_id=wf.id,
                actor_name=actor_name,
                actor_role=actor_role,
                from_stage=from_stage,
                to_stage=to_stage,
                action=action,
                comment=comment or f"Executed approval action: {action}"
            )
            db.session.add(history)
            
            # Record Central System Audit Log
            AuditService.log_audit(
                performed_by=actor_name,
                ip_address=ip_address,
                action_type=f"Workflow {action}",
                module_name="Workflow Engine",
                old_value={'stage': from_stage},
                new_value={'stage': to_stage},
                reason=comment or f"Workflow state change: {from_stage} -> {to_stage}",
                vendor_id=vendor_id
            )
            
            db.session.commit()
            
            # Trigger Real-Time Notification & Live Event updates
            notif_title = f"Workflow Update - {action}"
            notif_msg = f"Vendor '{vendor.name}' workflow moved to '{to_stage}' by {actor_name} ({actor_role})."
            
            notif = SystemNotification(
                vendor_id=vendor_id,
                title=notif_title,
                message=notif_msg,
                priority='Medium' if action != 'Reject' else 'High',
                category='System',
                target_roles=["Admin", "Manager", "Data Steward"]
            )
            db.session.add(notif)
            db.session.commit()
            
            return {
                'success': True,
                'current_stage': to_stage,
                'required_level': wf.required_level,
                'assigned_role': wf.assigned_role,
                'vendor_status': vendor.status
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Workflow transition error: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def send_review_reminders(threshold_seconds: int = 3600) -> dict:
        """Finds pending reviews that haven't transitioned for threshold_seconds and triggers reminders."""
        try:
            now = datetime.utcnow()
            limit_time = now - timedelta(seconds=threshold_seconds)
            
            pending_wfs = VendorApprovalWorkflow.query.filter(
                VendorApprovalWorkflow.current_stage.in_(['Submitted', 'Under Review']),
                VendorApprovalWorkflow.updated_at <= limit_time
            ).all()
            
            # Bulk fetch vendor profiles to eliminate N+1 queries
            v_ids = [wf.vendor_id for wf in pending_wfs if wf.vendor_id]
            vendors = Vendor.query.filter(Vendor.id.in_(v_ids)).all() if v_ids else []
            v_map = {v.id: v for v in vendors}
            
            sent_count = 0
            for wf in pending_wfs:
                vendor = v_map.get(wf.vendor_id)
                if not vendor:
                    continue
                    
                notif_msg = f"REMINDER: Vendor '{vendor.name}' requires review approval stage transition. Assigned Role: {wf.assigned_role}."
                
                # Log history transition step for the reminder
                history = VendorApprovalHistory(
                    workflow_id=wf.id,
                    actor_name='System',
                    actor_role='System',
                    from_stage=wf.current_stage,
                    to_stage=wf.current_stage,
                    action='Reminder',
                    comment=f"Sent review reminder to role: {wf.assigned_role}."
                )
                db.session.add(history)
                
                # Log audit log
                AuditService.log_audit(
                    performed_by='System',
                    ip_address='127.0.0.1',
                    action_type="Workflow Reminder",
                    module_name="Workflow Engine",
                    old_value={'stage': wf.current_stage},
                    new_value={'stage': wf.current_stage},
                    reason=f"Review reminder triggered: {notif_msg}",
                    vendor_id=wf.vendor_id
                )
                
                # Create notification
                notif = SystemNotification(
                    vendor_id=wf.vendor_id,
                    title="Review Reminder Alert",
                    message=notif_msg,
                    priority='High',
                    category='System',
                    target_roles=[wf.assigned_role]
                )
                db.session.add(notif)
                sent_count += 1
                
            db.session.commit()
            return {'success': True, 'reminders_sent': sent_count}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error sending review reminders: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def escalate_overdue_workflows(threshold_seconds: int = 7200) -> dict:
        """Finds workflows that haven't transitioned for threshold_seconds and escalates the assigned role."""
        try:
            now = datetime.utcnow()
            limit_time = now - timedelta(seconds=threshold_seconds)
            
            overdue_wfs = VendorApprovalWorkflow.query.filter(
                VendorApprovalWorkflow.current_stage.in_(['Submitted', 'Under Review']),
                VendorApprovalWorkflow.updated_at <= limit_time
            ).all()
            
            # Bulk fetch vendor profiles to eliminate N+1 queries
            ov_ids = [wf.vendor_id for wf in overdue_wfs if wf.vendor_id]
            o_vendors = Vendor.query.filter(Vendor.id.in_(ov_ids)).all() if ov_ids else []
            ov_map = {v.id: v for v in o_vendors}
            
            escalated_count = 0
            for wf in overdue_wfs:
                vendor = ov_map.get(wf.vendor_id)
                if not vendor:
                    continue
                    
                old_role = wf.assigned_role
                if old_role == 'Data Steward':
                    wf.assigned_role = 'Manager'
                    wf.required_level = 2
                elif old_role == 'Manager':
                    wf.assigned_role = 'Admin'
                else:
                    continue
                    
                wf.updated_at = now
                escalation_msg = f"Escalated assigned role from '{old_role}' to '{wf.assigned_role}' due to review delay."
                
                # Log history transition step
                history = VendorApprovalHistory(
                    workflow_id=wf.id,
                    actor_name='System',
                    actor_role='System',
                    from_stage=wf.current_stage,
                    to_stage=wf.current_stage,
                    action='Escalate',
                    comment=escalation_msg
                )
                db.session.add(history)
                
                # Log audit log
                AuditService.log_audit(
                    performed_by='System',
                    ip_address='127.0.0.1',
                    action_type="Workflow Escalation",
                    module_name="Workflow Engine",
                    old_value={'assigned_role': old_role},
                    new_value={'assigned_role': wf.assigned_role},
                    reason=escalation_msg,
                    vendor_id=wf.vendor_id
                )
                
                # Create notification
                notif = SystemNotification(
                    vendor_id=wf.vendor_id,
                    title="Workflow Escalated Alert",
                    message=f"Vendor '{vendor.name}' review has been escalated to '{wf.assigned_role}'.",
                    priority='High',
                    category='System',
                    target_roles=[wf.assigned_role]
                )
                db.session.add(notif)
                escalated_count += 1
                
            db.session.commit()
            return {'success': True, 'workflows_escalated': escalated_count}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error escalating overdue workflows: {str(e)}")
            return {'success': False, 'message': str(e)}
