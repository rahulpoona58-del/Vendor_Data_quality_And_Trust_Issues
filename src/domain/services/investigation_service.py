from datetime import datetime
from src.infrastructure.database.models import Vendor, VendorDocument, FraudCheck, VendorComplianceStatus, SystemAuditLog, DataCleaningSuggestion, VendorAnomaly, InvestigationCase, db
from src.domain.services.health_engine import HealthEngine
from src.domain.services.reputation_engine import ReputationIntelligenceEngine
from src.domain.services.knowledge_graph import KnowledgeGraphService
import logging

class InvestigationService:
    """Enterprise service managing vendor investigation case files and AI-assisted review pipelines."""
    
    @staticmethod
    def open_case(vendor_id: int, priority: str = 'Medium', assigned_to: str = None) -> dict:
        """Opens a new investigation case files entry for a vendor."""
        try:
            vendor = Vendor.query.get(vendor_id)
            if not vendor:
                return {'success': False, 'message': 'Vendor profile not found'}
                
            # Check if an open case already exists
            existing = InvestigationCase.query.filter_by(vendor_id=vendor_id, status='Open').first()
            if existing:
                return {'success': True, 'case': existing.to_dict(), 'message': 'Active investigation case already exists.'}
                
            case_num = f"CASE-{int(datetime.utcnow().timestamp())}-{vendor_id}"
            
            case = InvestigationCase(
                vendor_id=vendor_id,
                case_number=case_num,
                priority=priority,
                status='Open',
                assigned_to=assigned_to,
                evidence_notes=[],
                linked_vendors=[]
            )
            
            # Generate initial AI sandboxed assist parameters
            ai_data = InvestigationService.generate_ai_analysis(vendor_id)
            case.ai_summary = ai_data['ai_summary']
            case.ai_suggestions = ai_data['ai_suggestions']
            
            db.session.add(case)
            db.session.commit()
            
            # Record audit trail entry
            from src.domain.services.audit_service import AuditService
            AuditService.log_audit(
                performed_by=assigned_to or 'System',
                ip_address='127.0.0.1',
                action_type='Open Investigation Case',
                module_name='Investigation Workspace',
                old_value=None,
                new_value=case_num,
                reason="Flagged suspicious parameters for formal case file audit.",
                vendor_id=vendor_id
            )
            
            return {'success': True, 'case': case.to_dict()}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error opening investigation case: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def add_evidence_note(case_id: int, note_text: str, author: str) -> dict:
        """Appends a new verified investigator evidence note to the case folder."""
        try:
            case = InvestigationCase.query.get(case_id)
            if not case:
                return {'success': False, 'message': 'Investigation case file not found'}
                
            notes = list(case.evidence_notes or [])
            notes.append({
                'author': author,
                'timestamp': datetime.utcnow().isoformat(),
                'text': note_text
            })
            case.evidence_notes = notes
            db.session.commit()
            
            return {'success': True, 'case': case.to_dict()}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding case evidence note: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def link_related_vendor(case_id: int, target_vendor_id: int, author: str) -> dict:
        """Links a secondary suspect or related vendor to the active case folder."""
        try:
            case = InvestigationCase.query.get(case_id)
            if not case:
                return {'success': False, 'message': 'Case file not found'}
                
            target = Vendor.query.get(target_vendor_id)
            if not target:
                return {'success': False, 'message': 'Target vendor to link not found'}
                
            links = list(case.linked_vendors or [])
            if target_vendor_id not in links:
                links.append(target_vendor_id)
                case.linked_vendors = links
                db.session.commit()
                
            return {'success': True, 'case': case.to_dict()}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error linking vendor to case: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def update_case_workflow(case_id: int, status: str, priority: str, assigned_to: str, auditor: str) -> dict:
        """Updates case state, assignee metadata, and tracks changes to audit history."""
        try:
            case = InvestigationCase.query.get(case_id)
            if not case:
                return {'success': False, 'message': 'Case file not found'}
                
            old_status = case.status
            case.status = status
            case.priority = priority
            case.assigned_to = assigned_to
            
            if status in {'Resolved', 'Dismissed'}:
                case.resolved_at = datetime.utcnow()
                
            db.session.commit()
            
            # Log audit
            from src.domain.services.audit_service import AuditService
            AuditService.log_audit(
                performed_by=auditor,
                ip_address='127.0.0.1',
                action_type='Update Case Workflow',
                module_name='Investigation Workspace',
                old_value=old_status,
                new_value=status,
                reason=f"Workflow transition to status={status}, priority={priority}.",
                vendor_id=case.vendor_id
            )
            
            return {'success': True, 'case': case.to_dict()}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating case workflow status: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def generate_ai_analysis(vendor_id: int) -> dict:
        """Consolidates facts across the codebase to compile sandboxed AI summary logs without declaring fraud."""
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return {'ai_summary': 'No vendor record.', 'ai_suggestions': []}
            
        # 1. Fetch compliance
        comp_profile = VendorComplianceStatus.query.filter_by(vendor_id=vendor_id).first()
        comp_score = comp_profile.compliance_score if comp_profile else 70.0
        
        # 2. Fetch anomalies
        anomalies_count = VendorAnomaly.query.filter_by(vendor_id=vendor_id, status='Active').count()
        
        # 3. Fetch relationships
        relations_resp = KnowledgeGraphService.get_graph_data(vendor_id=vendor_id)
        linked_assets_count = 0
        if relations_resp.get('success'):
            nodes = relations_resp['elements'].get('nodes', [])
            linked_assets_count = len([n for n in nodes if n['data'].get('type') != 'vendor'])
            
        # 4. Compile explainable evidence summary
        summary = (
            f"EVIDENCE SUMMARY:\n"
            f"- Vendor Compliance score is currently at {comp_score}%.\n"
            f"- Active Anomaly Detection Engine alerts flagged: {anomalies_count} active items.\n"
            f"- Knowledge Graph overlaps: {linked_assets_count} assets shared with other vendor nodes.\n"
            f"- Registry trust rating sits at {vendor.trust_score} ({vendor.trust_level})."
        )
        
        # Next steps recommendations
        suggestions = [
            "Perform manual phone & email matching validation against state directories.",
            "Inspect verified GST Certificate registration dates and upload credentials.",
            "Verify directorship listings to ensure no conflict of interest or corporate sharing rings exist."
        ]
        
        return {
            'ai_summary': summary,
            'ai_suggestions': suggestions
        }
