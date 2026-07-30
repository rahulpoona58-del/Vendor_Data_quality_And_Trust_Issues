from datetime import datetime
from src.infrastructure.database.models import Vendor, VendorDocument, FraudCheck, VendorComplianceStatus, VendorAnomaly, DataCleaningSuggestion, InvestigationCase, db
from src.domain.services.knowledge_graph import KnowledgeGraphService
from src.domain.services.audit_service import AuditService
import logging

class BaseAgent:
    """Base class for agent actors containing permission checks, execution schemas, and audit logging."""
    def __init__(self, name: str, responsibility: str, required_roles: list, allowed_sources: list):
        self.name = name
        self.responsibility = responsibility
        self.required_roles = required_roles
        self.allowed_sources = allowed_sources

    def check_permissions(self, role: str) -> bool:
        """Verifies if the current user role is authorized to invoke this agent."""
        return role in self.required_roles

    def execute(self, params: dict, role: str) -> dict:
        """Wrapper ensuring permissions, schemas, auditing, and error boundaries."""
        if not self.check_permissions(role):
            AuditService.log_audit(
                performed_by='System-Orchestrator',
                ip_address='127.0.0.1',
                action_type=f"Unauthorized Invocation: {self.name}",
                module_name='Multi-Agent layer',
                reason=f"Role {role} is unauthorized to invoke agent {self.name}."
            )
            return {'success': False, 'error': f"Access Denied: Role '{role}' unauthorized."}

        # Audit start log
        logging.info(f"Agent '{self.name}' executing task. Input: {params}")
        
        try:
            result = self._run(params)
            
            # Audit success log
            AuditService.log_audit(
                performed_by='Agent-Workspace',
                ip_address='127.0.0.1',
                action_type=f"Execute {self.name}",
                module_name='Multi-Agent layer',
                reason=f"Successfully completed agent tasks for parameters: {params}.",
                vendor_id=params.get('vendor_id')
            )
            return {'success': True, 'agent': self.name, 'data': result}
        except Exception as e:
            logging.error(f"Agent {self.name} runtime error: {str(e)}")
            return {'success': False, 'agent': self.name, 'error': str(e)}

    def _run(self, params: dict) -> dict:
        raise NotImplementedError("Subclasses must implement _run")


class DataQualityAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Data Quality Agent",
            responsibility="Scans registry profiles for spelling mistakes, formatting errors, or data cleaning needs.",
            required_roles=['Admin', 'Auditor', 'Data Steward', 'Viewer'],
            allowed_sources=['vendors', 'data_cleaning_suggestions']
        )

    def _run(self, params: dict) -> dict:
        vendor_id = params.get('vendor_id')
        suggestions = DataCleaningSuggestion.query.filter_by(vendor_id=vendor_id).all()
        
        # Guardrail check against DB model to avoid hallucinated fields
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor ID {vendor_id} does not exist in registry database.")

        return {
            'dirty_fields': [s.field_name for s in suggestions if s.status == 'Pending'],
            'clean_suggestions_count': len(suggestions),
            'spelling_issues_flagged': any('spelling' in str(s.reason).lower() for s in suggestions)
        }


class TrustAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Trust Agent",
            responsibility="Analyzes trust score adjustments, negative factors, and baseline scoring overrides.",
            required_roles=['Admin', 'Auditor', 'Data Steward', 'Viewer'],
            allowed_sources=['vendors', 'vendor_trust_history']
        )

    def _run(self, params: dict) -> dict:
        vendor_id = params.get('vendor_id')
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor ID {vendor_id} does not exist.")

        from src.infrastructure.database.models import VendorTrustHistory
        history = VendorTrustHistory.query.filter_by(vendor_id=vendor_id).order_by(VendorTrustHistory.id.desc()).limit(5).all()

        return {
            'current_trust_score': vendor.trust_score,
            'trust_level': vendor.trust_level,
            'recent_history_scores': [h.trust_score for h in history],
            'reasons_negative': list(set([reason for h in history for reason in (h.reasons_negative or [])]))
        }


class RiskAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Risk Agent",
            responsibility="Monitors risk metrics, statistical outlier warnings, and anomaly engine flags.",
            required_roles=['Admin', 'Auditor', 'Data Steward', 'Viewer'],
            allowed_sources=['vendors', 'vendor_anomalies']
        )

    def _run(self, params: dict) -> dict:
        vendor_id = params.get('vendor_id')
        anomalies = VendorAnomaly.query.filter_by(vendor_id=vendor_id, status='Active').all()

        return {
            'active_anomalies_count': len(anomalies),
            'anomaly_patterns': [getattr(a, 'pattern_name', getattr(a, 'pattern', 'Unknown Pattern')) for a in anomalies],
            'max_anomaly_score': max([a.anomaly_score for a in anomalies]) if anomalies else 0.0
        }


class FraudAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Fraud Agent",
            responsibility="Scans database blacklists, shared identities overlap, and knowledge graph suspicious rings.",
            required_roles=['Admin', 'Auditor', 'Data Steward'],
            allowed_sources=['fraud_checks', 'knowledge_graph']
        )

    def _run(self, params: dict) -> dict:
        vendor_id = params.get('vendor_id')
        alerts = FraudCheck.query.filter_by(vendor_id=vendor_id).all()
        
        # Knowledge graph integration
        relations = KnowledgeGraphService.get_graph_data(vendor_id=vendor_id)
        shared_assets_found = False
        if relations.get('success'):
            nodes = relations['elements'].get('nodes', [])
            shared_assets_found = len([n for n in nodes if n['data'].get('type') != 'vendor']) > 0

        return {
            'fraud_alerts_count': len([a for a in alerts if a.status == 'Alert']),
            'flagged_patterns': [a.root_cause for a in alerts if a.status == 'Alert'],
            'shared_assets_overlap': shared_assets_found
        }


class ComplianceAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Compliance Agent",
            responsibility="Verifies compliance scores, expired certifications, and registry filings status.",
            required_roles=['Admin', 'Auditor', 'Data Steward', 'Viewer'],
            allowed_sources=['vendor_compliance_status']
        )

    def _run(self, params: dict) -> dict:
        vendor_id = params.get('vendor_id')
        profile = VendorComplianceStatus.query.filter_by(vendor_id=vendor_id).first()
        pending_docs_count = VendorDocument.query.filter_by(vendor_id=vendor_id, verification_status='Pending', is_deleted=False).count()

        return {
            'compliance_score': profile.compliance_score if profile else 100.0,
            'is_blacklisted': (profile.approval_status == 'Rejected') if profile else False,
            'pending_verifications_count': pending_docs_count
        }


class DocumentIntelligenceAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Document Intelligence Agent",
            responsibility="Validates OCR extractions completeness and document expiration ledgers.",
            required_roles=['Admin', 'Auditor', 'Data Steward', 'Viewer'],
            allowed_sources=['vendor_documents']
        )

    def _run(self, params: dict) -> dict:
        vendor_id = params.get('vendor_id')
        docs = VendorDocument.query.filter_by(vendor_id=vendor_id).all()
        now = datetime.utcnow()

        return {
            'total_documents': len(docs),
            'expired_count': len([d for d in docs if d.expiry_date and d.expiry_date < now]),
            'unverified_count': len([d for d in docs if d.verification_status != 'Verified'])
        }


class InvestigationAssistant(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Investigation Assistant",
            responsibility="Retrieves active case workflow priority, assignee metadata, and case notes.",
            required_roles=['Admin', 'Auditor', 'Data Steward'],
            allowed_sources=['investigation_cases']
        )

    def _run(self, params: dict) -> dict:
        vendor_id = params.get('vendor_id')
        case = InvestigationCase.query.filter_by(vendor_id=vendor_id, status='Open').first()

        return {
            'has_active_case': case is not None,
            'case_number': case.case_number if case else None,
            'priority': case.priority if case else None,
            'notes_count': len(case.evidence_notes) if case else 0
        }


class ReportingAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Reporting Agent",
            responsibility="Compiles factual summaries and formats markdown audit logs findings.",
            required_roles=['Admin', 'Auditor', 'Data Steward'],
            allowed_sources=[]
        )

    def _run(self, params: dict) -> dict:
        # Expects summarized dictionary compiled by Orchestrator
        findings = params.get('findings', {})
        vendor_name = params.get('vendor_name', 'Subject Vendor')
        
        report = (
            f"# MULTI-AGENT COMPREHENSIVE INVESTIGATION REPORT\n"
            f"**Vendor Name**: {vendor_name}\n"
            f"**Evaluation Date**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
            f"## Factual Evidence Summary\n"
            f"- **Trust profile**: Score sits at {findings.get('trust', {}).get('current_trust_score', 'N/A')} ({findings.get('trust', {}).get('trust_level', 'N/A')}).\n"
            f"- **Compliance filing**: Evaluated score is at {findings.get('compliance', {}).get('compliance_score', 'N/A')}%.\n"
            f"- **Quality suggestions**: Found {findings.get('quality', {}).get('clean_suggestions_count', 0)} recommendation entries.\n"
            f"- **Document status**: Total of {findings.get('documents', {}).get('total_documents', 0)} documents list ({findings.get('documents', {}).get('expired_count', 0)} expired).\n\n"
            f"## Risk & Fraud Identifiers\n"
            f"- **Active Anomaly Engine Alerts**: {findings.get('risk', {}).get('active_anomalies_count', 0)} items.\n"
            f"- **Flagged Fraud check patterns**: {findings.get('fraud', {}).get('flagged_patterns', [])}.\n"
            f"- **Knowledge Graph Overlay shared links**: {findings.get('fraud', {}).get('shared_assets_overlap', False)}.\n\n"
            f"## AI Advisory Next Investigation Steps\n"
            f"1. Perform corporate directorship registry validation audits.\n"
            f"2. Manually compare telephone contact metadata profiles."
        )

        return {
            'report_markdown': report,
            'risk_level_assessment': 'High' if (findings.get('risk', {}).get('active_anomalies_count', 0) > 0 or findings.get('fraud', {}).get('fraud_alerts_count', 0) > 0) else 'Normal'
        }


class AgentOrchestrator:
    """Controlled multi-agent orchestration manager executing multi-step diagnostic tasks."""
    
    def __init__(self):
        self.agents = {
            'quality': DataQualityAgent(),
            'trust': TrustAgent(),
            'risk': RiskAgent(),
            'fraud': FraudAgent(),
            'compliance': ComplianceAgent(),
            'documents': DocumentIntelligenceAgent(),
            'investigation': InvestigationAssistant(),
            'reporting': ReportingAgent()
        }

    def run_vendor_diagnostic(self, vendor_id: int, user_role: str) -> dict:
        """Executes multi-agent coordination task: 'Investigate why this vendor became high risk'."""
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return {'success': False, 'message': 'Vendor target profile not found.'}

        findings = {}
        errors = {}

        # 1. Invoke all diagnostics agents sequentially
        agent_keys = ['quality', 'trust', 'risk', 'fraud', 'compliance', 'documents', 'investigation']
        for key in agent_keys:
            agent = self.agents[key]
            res = agent.execute({'vendor_id': vendor_id}, user_role)
            if res.get('success'):
                findings[key] = res['data']
            else:
                errors[key] = res.get('error', 'Execution error')

        # 2. Invoke reporting agent to build the final evidence-based explainer markdown
        report_res = self.agents['reporting'].execute({
            'findings': findings,
            'vendor_name': vendor.name
        }, user_role)

        if not report_res.get('success'):
            return {
                'success': False,
                'message': 'Failed compiling report.',
                'errors': errors
            }

        return {
            'success': True,
            'vendor_id': vendor_id,
            'vendor_name': vendor.name,
            'findings': findings,
            'report': report_res['data']['report_markdown'],
            'risk_level': report_res['data']['risk_level_assessment'],
            'errors': errors
        }
