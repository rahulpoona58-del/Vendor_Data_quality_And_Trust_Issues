from sqlalchemy import event
from sqlalchemy.orm.attributes import get_history
from src.infrastructure.database.models import Vendor, VendorDocument, FraudCheck, VendorTrustHistory, VendorComplianceStatus, SystemNotification
from src.domain.services.event_queue import EventQueue

def setup_event_listeners():
    """Binds ORM event hooks to the central EventQueue to broadcast real-time telemetry updates."""
    
    # 1. Document Upload
    @event.listens_for(VendorDocument, 'after_insert')
    def receive_doc_insert(mapper, connection, target):
        EventQueue.publish_event('Document Upload', {
            'id': target.id,
            'vendor_id': target.vendor_id,
            'document_name': target.name,
            'document_type': target.document_type,
            'verification_status': target.verification_status
        })

    # 2. Fraud Alerts
    @event.listens_for(FraudCheck, 'after_insert')
    @event.listens_for(FraudCheck, 'after_update')
    def receive_fraud_change(mapper, connection, target):
        EventQueue.publish_event('Fraud Alert', {
            'id': target.id,
            'vendor_id': target.vendor_id,
            'fraud_score': target.fraud_score,
            'risk_level': target.risk_level,
            'root_cause': target.root_cause,
            'status': target.status
        })

    # 3. Trust Score Changes & Risk Alerts
    @event.listens_for(VendorTrustHistory, 'after_insert')
    def receive_trust_history(mapper, connection, target):
        # Publish Trust Score Change
        EventQueue.publish_event('Trust Score Change', {
            'vendor_id': target.vendor_id,
            'trust_score': target.trust_score,
            'risk_score': target.risk_score,
            'compliance_score': target.compliance_score
        })
        
        # If trust score is low or risk score is high, publish a Risk Alert
        if target.trust_score < 50.0 or target.risk_score > 50.0:
            EventQueue.publish_event('Risk Alert', {
                'vendor_id': target.vendor_id,
                'trust_score': target.trust_score,
                'risk_score': target.risk_score,
                'risk_level': 'High Risk'
            })

    # 4. Compliance Changes
    @event.listens_for(VendorComplianceStatus, 'after_insert')
    @event.listens_for(VendorComplianceStatus, 'after_update')
    def receive_compliance_change(mapper, connection, target):
        EventQueue.publish_event('Compliance Change', {
            'vendor_id': target.vendor_id,
            'compliance_score': target.compliance_score,
            'approval_status': target.approval_status
        })

    # 5. Vendor Updates & Quality Score Changes
    @event.listens_for(Vendor, 'after_update')
    def receive_vendor_update(mapper, connection, target):
        # Check status change
        status_hist = get_history(target, 'status')
        if status_hist.has_changes():
            EventQueue.publish_event('Vendor Update', {
                'vendor_id': target.id,
                'name': target.name,
                'status': target.status,
                'category': target.category
            })
            
        # Check quality_rating change
        quality_hist = get_history(target, 'quality_rating')
        if quality_hist.has_changes():
            EventQueue.publish_event('Quality Score Change', {
                'vendor_id': target.id,
                'quality_rating': target.quality_rating
            })
            
        # Check trust_score change
        trust_hist = get_history(target, 'trust_score')
        if trust_hist.has_changes():
            EventQueue.publish_event('Trust Score Change', {
                'vendor_id': target.id,
                'trust_score': target.trust_score,
                'trust_level': target.trust_level
            })

    # 6. Live System Notifications
    @event.listens_for(SystemNotification, 'after_insert')
    def receive_system_notification(mapper, connection, target):
        EventQueue.publish_event('Live Notification', {
            'id': target.id,
            'vendor_id': target.vendor_id,
            'title': target.title,
            'message': target.message,
            'priority': target.priority,
            'category': target.category
        })
