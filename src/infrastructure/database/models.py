from datetime import datetime
from src.infrastructure.database.connection import db

class User(db.Model):
    """User accounts and role-based permissions management."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='Viewer') # Admin, Data Steward, Auditor, Manager, Viewer
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat()
        }

class Vendor(db.Model):
    """Vendor master profiles."""
    __tablename__ = 'vendors'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=True, default='General')
    status = db.Column(db.String(50), nullable=False, default='Active') # Active, Inactive, Blocked
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Centralized Telemetry cache columns
    trust_score = db.Column(db.Float, nullable=False, default=70.0)
    trust_level = db.Column(db.String(50), nullable=False, default='Medium Trust')
    quality_rating = db.Column(db.Float, nullable=False, default=4.0)
    
    # Demographics and Tax profiles
    address = db.Column(db.String(255), nullable=True, default='')
    phone = db.Column(db.String(50), nullable=True, default='')
    email = db.Column(db.String(120), nullable=True, default='')
    gst_number = db.Column(db.String(50), nullable=True, default='')
    pan_number = db.Column(db.String(50), nullable=True, default='')
    bank_account = db.Column(db.String(100), nullable=True, default='')
    
    # Relationships (lazy loading enabled)
    documents = db.relationship('VendorDocument', backref='vendor', lazy='dynamic')
    
    @property
    def vendor_name(self):
        return self.name
        
    @vendor_name.setter
    def vendor_name(self, value):
        self.name = value
        
    def to_dict(self):
        return {
            'vendor_id': self.id,
            'vendor_name': self.name,
            'category': self.category,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'trust_score': self.trust_score,
            'trust_level': self.trust_level,
            'quality_rating': self.quality_rating,
            'address': self.address,
            'phone': self.phone,
            'email': self.email,
            'gst_number': self.gst_number,
            'pan_number': self.pan_number,
            'bank_account': self.bank_account
        }

class VendorDocument(db.Model):
    """Audit-compliant Vendor Document registry with versioning and soft-delete capabilities."""
    __tablename__ = 'vendor_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(100), nullable=False, index=True) # GST Certificate, PAN Card, etc.
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    uploaded_by = db.Column(db.String(120), nullable=False)
    verification_status = db.Column(db.String(50), nullable=False, default='Pending') # Pending, Verified, Rejected
    file_hash = db.Column(db.String(64), nullable=False) # SHA-256 Checksum
    file_size = db.Column(db.Integer, nullable=False) # Bytes
    mime_type = db.Column(db.String(100), nullable=False)
    storage_path = db.Column(db.String(512), nullable=False)
    
    # Soft Delete attributes
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'name': self.name,
            'document_type': self.document_type,
            'upload_date': self.upload_date.isoformat(),
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'version': self.version,
            'uploaded_by': self.uploaded_by,
            'verification_status': self.verification_status,
            'file_hash': self.file_hash,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'is_deleted': self.is_deleted,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None
        }

class OcrResult(db.Model):
    """Document Intelligence and OCR extraction records."""
    __tablename__ = 'ocr_results'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('vendor_documents.id'), nullable=False, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    
    # Extraction data structures (mapped to JSON)
    extracted_data = db.Column(db.JSON, nullable=False) # name, gst, pan, address, email, phone, bank_account, ifsc, cin, dates
    comparison_results = db.Column(db.JSON, nullable=False) # boolean match flags against vendor master records
    confidence_scores = db.Column(db.JSON, nullable=False) # float values 0.0 to 1.0
    corrected_data = db.Column(db.JSON, nullable=True) # manual corrections input by Data Stewards
    
    status = db.Column(db.String(50), nullable=False, default='Pending Review') # Pending Review, Verified, Corrected
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_by = db.Column(db.String(120), nullable=True)
    
    # Relationships
    document = db.relationship('VendorDocument', backref=db.backref('ocr_result', uselist=False), lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'document_id': self.document_id,
            'vendor_id': self.vendor_id,
            'extracted_data': self.extracted_data,
            'comparison_results': self.comparison_results,
            'confidence_scores': self.confidence_scores,
            'corrected_data': self.corrected_data,
            'status': self.status,
            'processed_at': self.processed_at.isoformat(),
            'reviewed_by': self.reviewed_by
        }

class DataCleaningSuggestion(db.Model):
    """AI-powered data cleansing suggestions and normalized outputs."""
    __tablename__ = 'data_cleaning_suggestions'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    field_name = db.Column(db.String(50), nullable=False) # name, email, phone, address, zip
    original_value = db.Column(db.Text, nullable=False)
    suggested_value = db.Column(db.Text, nullable=False)
    confidence = db.Column(db.Float, nullable=False) # 0.0 to 1.0
    reason = db.Column(db.String(255), nullable=False)
    
    status = db.Column(db.String(50), nullable=False, default='Pending') # Pending, Approved, Rejected, Applied
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    applied_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('cleaning_suggestions', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'field_name': self.field_name,
            'original_value': self.original_value,
            'suggested_value': self.suggested_value,
            'confidence': self.confidence,
            'reason': self.reason,
            'status': self.status,
            'detected_at': self.detected_at.isoformat(),
            'applied_at': self.applied_at.isoformat() if self.applied_at else None
        }

class ScoringRule(db.Model):
    """Scoring rules and configuration weights managed by administrators."""
    __tablename__ = 'scoring_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    rule_key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    rule_value = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False) # Delivery, Quality, Compliance, Security
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    description = db.Column(db.String(255), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'rule_key': self.rule_key,
            'rule_value': self.rule_value,
            'category': self.category,
            'is_active': self.is_active,
            'description': self.description
        }

class VendorTrustHistory(db.Model):
    """Historical ledger storing calculated trust scores, risk metrics, and reasons."""
    __tablename__ = 'vendor_trust_history'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    
    # Calculated Scores
    trust_score = db.Column(db.Float, nullable=False)
    risk_score = db.Column(db.Float, nullable=False)
    compliance_score = db.Column(db.Float, nullable=False)
    reliability_score = db.Column(db.Float, nullable=False)
    confidence_score = db.Column(db.Float, nullable=False)
    
    # Explainability Data (mapped to JSON)
    reasons_positive = db.Column(db.JSON, nullable=False) # List of positive strings
    reasons_negative = db.Column(db.JSON, nullable=False) # List of negative strings
    recommendations = db.Column(db.JSON, nullable=False) # List of remediation recommendations
    
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('trust_history', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'trust_score': self.trust_score,
            'risk_score': self.risk_score,
            'compliance_score': self.compliance_score,
            'reliability_score': self.reliability_score,
            'confidence_score': self.confidence_score,
            'reasons_positive': self.reasons_positive,
            'reasons_negative': self.reasons_negative,
            'recommendations': self.recommendations,
            'calculated_at': self.calculated_at.isoformat()
        }

class FraudCheck(db.Model):
    """System generated fraud check audit alerts."""
    __tablename__ = 'fraud_checks'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    
    # Fraud Score Indicators
    fraud_score = db.Column(db.Float, nullable=False, default=0.0) # 0 to 100
    risk_level = db.Column(db.String(50), nullable=False, default='Low') # High, Medium, Low
    confidence = db.Column(db.Float, nullable=False, default=1.0) # 0.0 to 1.0
    
    # Audit trail details
    root_cause = db.Column(db.String(255), nullable=False)
    recommended_action = db.Column(db.String(255), nullable=False)
    supporting_evidence = db.Column(db.JSON, nullable=False) # JSON list or details
    
    status = db.Column(db.String(50), nullable=False, default='Alert') # Alert, Investigating, Cleared
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('fraud_alerts', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'fraud_score': self.fraud_score,
            'risk_level': self.risk_level,
            'confidence': self.confidence,
            'root_cause': self.root_cause,
            'recommended_action': self.recommended_action,
            'supporting_evidence': self.supporting_evidence,
            'status': self.status,
            'checked_at': self.checked_at.isoformat()
        }

class BlacklistedVendor(db.Model):
    """Central registry of restricted business entities blocked from payment cycles."""
    __tablename__ = 'blacklisted_vendors'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    gst_number = db.Column(db.String(50), nullable=True, index=True)
    pan_number = db.Column(db.String(50), nullable=True, index=True)
    reason = db.Column(db.String(255), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'gst_number': self.gst_number,
            'pan_number': self.pan_number,
            'reason': self.reason,
            'added_at': self.added_at.isoformat()
        }

class VendorComplianceStatus(db.Model):
    """Compliance profiles tracking aggregate requirements scoring and approval status."""
    __tablename__ = 'vendor_compliance_status'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), unique=True, nullable=False, index=True)
    
    compliance_score = db.Column(db.Float, nullable=False, default=0.0) # 0 to 100
    approval_status = db.Column(db.String(50), nullable=False, default='Pending Approval') # Approved, Pending Approval, Rejected, Suspended
    
    last_audited_at = db.Column(db.DateTime, default=datetime.utcnow)
    audited_by = db.Column(db.String(120), nullable=True)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('compliance_status', uselist=False, lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'compliance_score': self.compliance_score,
            'approval_status': self.approval_status,
            'last_audited_at': self.last_audited_at.isoformat(),
            'audited_by': self.audited_by
        }

class ComplianceLog(db.Model):
    """Chronological timeline history of compliance events and audits."""
    __tablename__ = 'compliance_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    
    compliance_score = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('compliance_logs', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'compliance_score': self.compliance_score,
            'status': self.status,
            'description': self.description,
            'logged_at': self.logged_at.isoformat()
        }

class ComplianceNotification(db.Model):
    """Compliance warning alerts and expiry notifications for SLA files."""
    __tablename__ = 'compliance_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey('vendor_documents.id'), nullable=True, index=True)
    
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False) # Warning, Info, Critical
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('compliance_notifications', lazy=True))
    document = db.relationship('VendorDocument', backref=db.backref('notifications', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'document_id': self.document_id,
            'title': self.title,
            'message': self.message,
            'alert_type': self.alert_type,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat()
        }

class VendorActivity(db.Model):
    """System and manual audit log timeline entries tracking operational milestones."""
    __tablename__ = 'vendor_activities'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    
    activity_type = db.Column(db.String(50), nullable=False) # Created, Updated, Document Uploaded, Trust Score Changed, Risk Score Changed, Fraud Alert, Compliance Updated, Login Activity, Admin Actions, Approval, Rejection
    description = db.Column(db.String(255), nullable=False)
    performed_by = db.Column(db.String(120), nullable=False, default='System')
    metadata_json = db.Column(db.JSON, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('activities', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'activity_type': self.activity_type,
            'description': self.description,
            'performed_by': self.performed_by,
            'metadata_json': self.metadata_json,
            'created_at': self.created_at.isoformat()
        }

class SystemNotification(db.Model):
    """Real-time operational alerts directed to role-based system queues."""
    __tablename__ = 'system_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True, index=True)
    
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    priority = db.Column(db.String(50), nullable=False, default='Info') # Low, Medium, High, Critical
    category = db.Column(db.String(50), nullable=False) # Compliance, Fraud, System, Trust, Quality
    target_roles = db.Column(db.JSON, nullable=False) # List of roles: e.g. ["Admin", "Auditor"]
    
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('notifications', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'title': self.title,
            'message': self.message,
            'priority': self.priority,
            'category': self.category,
            'target_roles': self.target_roles,
            'is_read': self.is_read,
            'is_archived': self.is_archived,
            'created_at': self.created_at.isoformat()
        }

class AiRecommendation(db.Model):
    """AI analysis recommendations with one-click approval mechanisms."""
    __tablename__ = 'ai_recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    
    recommendation_type = db.Column(db.String(50), nullable=False) # Update Profile, Merge Duplicate, Verify Document, Improve Score, Compliance Improvement
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    
    # JSON dictionary parameters specifying changes to execute (e.g. field/value updates or entity references)
    proposed_action = db.Column(db.JSON, nullable=False)
    
    reason = db.Column(db.String(255), nullable=False)
    confidence = db.Column(db.Float, nullable=False, default=85.0) # 0 to 100 percentage
    business_impact = db.Column(db.String(150), nullable=False)
    estimated_score_improvement = db.Column(db.Float, nullable=False, default=5.0)
    
    status = db.Column(db.String(50), nullable=False, default='Pending') # Pending, Approved, Rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('ai_recommendations', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'recommendation_type': self.recommendation_type,
            'title': self.title,
            'description': self.description,
            'proposed_action': self.proposed_action,
            'reason': self.reason,
            'confidence': self.confidence,
            'business_impact': self.business_impact,
            'estimated_score_improvement': self.estimated_score_improvement,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }

class SystemAuditLog(db.Model):
    """System-wide trace registry auditing admin overrides and configuration changes."""
    __tablename__ = 'system_audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True, index=True)
    
    performed_by = db.Column(db.String(120), nullable=False)
    ip_address = db.Column(db.String(50), nullable=False)
    
    action_type = db.Column(db.String(100), nullable=False)
    module_name = db.Column(db.String(100), nullable=False)
    
    old_value = db.Column(db.JSON, nullable=True)
    new_value = db.Column(db.JSON, nullable=True)
    
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Lineage Tracing columns
    original_source = db.Column(db.String(100), nullable=True)
    import_source = db.Column(db.String(255), nullable=True)
    ai_suggested = db.Column(db.Boolean, nullable=True, default=False)
    human_approved = db.Column(db.Boolean, nullable=True, default=False)
    validation_result = db.Column(db.String(100), nullable=True)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('audit_logs', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'performed_by': self.performed_by,
            'ip_address': self.ip_address,
            'action_type': self.action_type,
            'module_name': self.module_name,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'reason': self.reason,
            'created_at': self.created_at.isoformat(),
            'original_source': self.original_source,
            'import_source': self.import_source,
            'ai_suggested': self.ai_suggested,
            'human_approved': self.human_approved,
            'validation_result': self.validation_result
        }

class VendorAnomaly(db.Model):
    """Stores multi-dimensional anomalies detected via ML predictions and robust statistics."""
    __tablename__ = 'vendor_anomalies'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    
    anomaly_score = db.Column(db.Float, nullable=False) # 0 to 100
    severity = db.Column(db.String(50), nullable=False) # Critical, High, Medium, Low
    pattern = db.Column(db.String(100), nullable=False)
    
    observed_facts = db.Column(db.JSON, nullable=False)
    rule_findings = db.Column(db.JSON, nullable=False)
    ml_predictions = db.Column(db.JSON, nullable=False)
    
    explanation = db.Column(db.Text, nullable=False)
    recommended_action = db.Column(db.Text, nullable=False)
    
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default='Active') # Active, Investigating, Resolved, False Positive
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('anomalies', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.name if self.vendor else '',
            'anomaly_score': self.anomaly_score,
            'severity': self.severity,
            'pattern': self.pattern,
            'observed_facts': self.observed_facts,
            'rule_findings': self.rule_findings,
            'ml_predictions': self.ml_predictions,
            'explanation': self.explanation,
            'recommended_action': self.recommended_action,
            'detected_at': self.detected_at.isoformat(),
            'status': self.status
        }

class VendorReputation(db.Model):
    """Tracks reproducible, versioned reputation intelligence metrics and scores."""
    __tablename__ = 'vendor_reputations'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    
    reputation_score = db.Column(db.Float, nullable=False) # 0 to 100
    reputation_tier = db.Column(db.String(50), nullable=False) # Elite, Trustworthy, Average, High Risk, Critical Risk
    formula_version = db.Column(db.String(20), nullable=False, default='v1.0')
    
    score_breakdown = db.Column(db.JSON, nullable=False)
    positive_factors = db.Column(db.JSON, nullable=False)
    negative_factors = db.Column(db.JSON, nullable=False)
    recommendations = db.Column(db.JSON, nullable=False)
    
    confidence_level = db.Column(db.Float, nullable=False, default=95.0) # 0 to 100
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('reputations', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.name if self.vendor else '',
            'reputation_score': self.reputation_score,
            'reputation_tier': self.reputation_tier,
            'formula_version': self.formula_version,
            'score_breakdown': self.score_breakdown,
            'positive_factors': self.positive_factors,
            'negative_factors': self.negative_factors,
            'recommendations': self.recommendations,
            'confidence_level': self.confidence_level,
            'created_at': self.created_at.isoformat()
        }

class BusinessRule(db.Model):
    """Dynamic, configurable logic blocks enabling administrators to adjust scoring/status workflows."""
    __tablename__ = 'business_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    rule_group = db.Column(db.String(50), nullable=False) # Compliance, Fraud, Trust, Quality, Risk
    
    priority = db.Column(db.Integer, default=1, nullable=False)
    version = db.Column(db.Integer, default=1, nullable=False)
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    
    # JSON logic structure for evaluation (e.g. operators and rule conditions)
    conditions_json = db.Column(db.JSON, nullable=False)
    
    # JSON logic structure specifying the action details (e.g. reject_vendor, adjust_trust_score)
    actions_json = db.Column(db.JSON, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'rule_group': self.rule_group,
            'priority': self.priority,
            'version': self.version,
            'is_enabled': self.is_enabled,
            'conditions_json': self.conditions_json,
            'actions_json': self.actions_json,
            'created_at': self.created_at.isoformat()
        }

class InvestigationCase(db.Model):
    """Represents a security and compliance investigation case file for suspicious vendors."""
    __tablename__ = 'investigation_cases'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    case_number = db.Column(db.String(50), unique=True, nullable=False)
    
    assigned_to = db.Column(db.String(120), nullable=True) # Investigator email
    priority = db.Column(db.String(20), default='Medium') # Low, Medium, High, Critical
    status = db.Column(db.String(30), default='Open') # Open, Under Investigation, Resolved, Dismissed
    
    evidence_notes = db.Column(db.JSON, nullable=False, default=list) # List of notes dictionaries
    linked_vendors = db.Column(db.JSON, nullable=False, default=list) # List of linked vendor ID integers
    
    ai_summary = db.Column(db.Text, nullable=True)
    ai_suggestions = db.Column(db.JSON, nullable=True) # list of next steps suggested by AI
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_details = db.Column(db.Text, nullable=True)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('investigations', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.name if self.vendor else '',
            'case_number': self.case_number,
            'assigned_to': self.assigned_to,
            'priority': self.priority,
            'status': self.status,
            'evidence_notes': self.evidence_notes,
            'linked_vendors': self.linked_vendors,
            'ai_summary': self.ai_summary,
            'ai_suggestions': self.ai_suggestions,
            'created_at': self.created_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_details': self.resolution_details
        }

class CopilotMessage(db.Model):
    """Copilot interactive chat logs for NLP session traceability."""
    __tablename__ = 'copilot_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    sender = db.Column(db.String(20), nullable=False) # user or copilot
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'sender': self.sender,
            'message': self.message,
            'created_at': self.created_at.isoformat()
        }

class ReportSchedule(db.Model):
    """Configuration for automated, recurring vendor telemetry exports."""
    __tablename__ = 'report_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(100), nullable=False) # e.g. Vendor Summary, Risk Report
    frequency = db.Column(db.String(50), nullable=False) # Daily, Weekly, Monthly
    export_format = db.Column(db.String(20), nullable=False) # PDF, Excel, CSV, HTML
    recipient_email = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_run = db.Column(db.DateTime, nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'report_type': self.report_type,
            'frequency': self.frequency,
            'export_format': self.export_format,
            'recipient_email': self.recipient_email,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None
        }

class GeneratedReport(db.Model):
    """Archival records of generated reports, matching export formats."""
    __tablename__ = 'generated_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(100), nullable=False)
    export_format = db.Column(db.String(20), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    generated_by = db.Column(db.String(120), nullable=False, default='System')
    status = db.Column(db.String(50), nullable=False, default='Completed') # Completed, Failed
    
    def to_dict(self):
        return {
            'id': self.id,
            'report_type': self.report_type,
            'export_format': self.export_format,
            'filename': self.filename,
            'created_at': self.created_at.isoformat(),
            'generated_by': self.generated_by,
            'status': self.status
        }

class VendorApprovalWorkflow(db.Model):
    """Workflow tracking multi-stage approval states for vendor profiles."""
    __tablename__ = 'vendor_approval_workflows'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, unique=True, index=True)
    current_stage = db.Column(db.String(50), nullable=False, default='Draft') # Draft, Submitted, Under Review, Approved, Rejected, Archived
    required_level = db.Column(db.Integer, nullable=False, default=1) # 1 = Level 1 (Steward), 2 = Level 2 (Manager)
    assigned_role = db.Column(db.String(50), nullable=False, default='Data Steward')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('approval_workflow', uselist=False, lazy=True))
    histories = db.relationship('VendorApprovalHistory', backref='workflow', cascade="all, delete-orphan", lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'current_stage': self.current_stage,
            'required_level': self.required_level,
            'assigned_role': self.assigned_role,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'histories': [h.to_dict() for h in self.histories]
        }

class VendorApprovalHistory(db.Model):
    """Transition journals recording approval steps, actor decisions, and comments."""
    __tablename__ = 'vendor_approval_histories'
    
    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('vendor_approval_workflows.id'), nullable=False, index=True)
    actor_name = db.Column(db.String(120), nullable=False)
    actor_role = db.Column(db.String(50), nullable=False)
    from_stage = db.Column(db.String(50), nullable=False)
    to_stage = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(50), nullable=False) # Submit, Approve, Reject, Escalate, Archive, Comment
    comment = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'workflow_id': self.workflow_id,
            'actor_name': self.actor_name,
            'actor_role': self.actor_role,
            'from_stage': self.from_stage,
            'to_stage': self.to_stage,
            'action': self.action,
            'comment': self.comment,
            'timestamp': self.timestamp.isoformat()
        }
