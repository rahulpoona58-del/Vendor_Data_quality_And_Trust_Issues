from datetime import datetime
from src.infrastructure.database.models import AiRecommendation, Vendor, VendorDocument, OcrResult, DataCleaningSuggestion, db
from src.domain.services.timeline_service import TimelineService
from src.domain.services.notification_service import NotificationService
import logging
import json

class RecommendationEngine:
    """Orchestrates AI-driven vendor diagnostics and recommendation overrides."""
    
    @staticmethod
    def generate_recommendations(vendor_id: int) -> list:
        """Analyzes vendor data, trust score, fraud alerts, and expiries to construct AI recommendations."""
        try:
            vendor = Vendor.query.get(vendor_id)
            if not vendor:
                return []
            logging.info(f"GENERATE RECS FOR VENDOR {vendor_id}: name={vendor.name}, email='{vendor.email}', phone='{vendor.phone}', gst='{vendor.gst_number}'")
                
            # Clear existing pending recommendations for this vendor
            AiRecommendation.query.filter_by(vendor_id=vendor_id, status='Pending').delete()
            db.session.commit()
            
            recs = []
            
            # 1. Check Data Cleaning Suggestions (Spellings/capitalization)
            suggestions = DataCleaningSuggestion.query.filter_by(vendor_id=vendor_id, status='Pending').all()
            for sug in suggestions:
                # Map fields
                field = sug.field_name
                orig = sug.original_value
                sugg_val = sug.suggested_value
                
                title = f"Correct {field.replace('_', ' ').title()}"
                desc = f"Change original value '{orig}' to proposed normalized value '{sugg_val}'."
                
                recs.append(AiRecommendation(
                    vendor_id=vendor_id,
                    recommendation_type="Update Profile",
                    title=title,
                    description=desc,
                    proposed_action={"type": "update_field", "field": field, "value": sugg_val, "suggestion_id": sug.id},
                    reason=sug.reason,
                    confidence=sug.confidence * 100,
                    business_impact=f"Improves data quality verification checks for {field}.",
                    estimated_score_improvement=3.0,
                    status="Pending"
                ))

            # 2. Check Duplicates (Fraud overlaps)
            ocr = OcrResult.query.filter_by(vendor_id=vendor_id).first()
            if ocr:
                gst = (ocr.corrected_data or ocr.extracted_data).get('gst_number', '').strip()
                if gst:
                    # Look for other vendors sharing this GST
                    other_ocrs = OcrResult.query.filter(OcrResult.vendor_id != vendor_id).all()
                    for other in other_ocrs:
                        other_gst = (other.corrected_data or other.extracted_data).get('gst_number', '').strip()
                        if other_gst == gst:
                            other_vendor = Vendor.query.get(other.vendor_id)
                            if other_vendor:
                                recs.append(AiRecommendation(
                                    vendor_id=vendor_id,
                                    recommendation_type="Merge Duplicate",
                                    title=f"Merge Duplicate Vendor: {other_vendor.name}",
                                    description=f"Duplicate registration pattern matched. Merge Vendor ID {other_vendor.id} with this profile.",
                                    proposed_action={"type": "merge_vendors", "target_vendor_id": other_vendor.id},
                                    reason=f"Shared tax ID registration: GST {gst}.",
                                    confidence=99.0,
                                    business_impact="Folds duplicate transaction audit logs to clean records.",
                                    estimated_score_improvement=10.0,
                                    status="Pending"
                                ))
                                break

            # 3. Check Pending Compliance Documents
            docs = VendorDocument.query.filter_by(vendor_id=vendor_id, is_deleted=False).all()
            for doc in docs:
                if doc.verification_status == 'Pending':
                    recs.append(AiRecommendation(
                        vendor_id=vendor_id,
                        recommendation_type="Verify Document",
                        title=f"Verify Uploaded {doc.document_type}",
                        description=f"Auditor approval of {doc.name} (v{doc.version}) is outstanding.",
                        proposed_action={"type": "verify_document", "doc_id": doc.id},
                        reason="Completes required profile registration checklist.",
                        confidence=90.0,
                        business_impact="Avoids service holds or PO execution delays.",
                        estimated_score_improvement=5.0,
                        status="Pending"
                    ))

            # 4. Check Compliance Score improvement suggestions
            from src.infrastructure.database.models import VendorComplianceStatus
            comp = VendorComplianceStatus.query.filter_by(vendor_id=vendor_id).first()
            if comp and comp.compliance_score < 80.0:
                recs.append(AiRecommendation(
                    vendor_id=vendor_id,
                    recommendation_type="Compliance Improvement",
                    title="Upload Mandatory SLAs & Tax Proofs",
                    description="Fulfill incomplete profile check list: missing registration cert or bank proofs.",
                    proposed_action={"type": "prompt_action", "task": "Compliance uploads"},
                    reason="Compliance score is below recommended 80% threshold.",
                    confidence=85.0,
                    business_impact="Establishes auditor approval eligibility status.",
                    estimated_score_improvement=20.0,
                    status="Pending"
                ))

            # 5. Check Trust Score improvement suggestions
            from src.infrastructure.database.models import VendorTrustHistory
            trust = VendorTrustHistory.query.filter_by(vendor_id=vendor_id).order_by(VendorTrustHistory.calculated_at.desc()).first()
            if trust and trust.trust_score < 70.0:
                recs.append(AiRecommendation(
                    vendor_id=vendor_id,
                    recommendation_type="Improve Score",
                    title="Re-calculate Trust Index Profile Metrics",
                    description="Trigger overall scoring run to verify clean duplicate flags.",
                    proposed_action={"type": "prompt_action", "task": "Recalculate trust"},
                    reason="Trust Score is in high-risk Warning bounds.",
                    confidence=80.0,
                    business_impact="Maintains active vendor standing on dashboard widgets.",
                    estimated_score_improvement=15.0,
                    status="Pending"
                ))

            # 6. Check for missing profile fields
            missing_fields = []
            if not vendor.gst_number:
                missing_fields.append("GST registration number")
            if not vendor.pan_number:
                missing_fields.append("PAN card identity")
            if not vendor.bank_account:
                missing_fields.append("Bank account proof")
            if not vendor.email:
                missing_fields.append("Corporate email address")
            if not vendor.phone:
                missing_fields.append("Contact phone number")
                
            if missing_fields:
                recs.append(AiRecommendation(
                    vendor_id=vendor_id,
                    recommendation_type="Missing Fields Cleanup",
                    title="Complete Missing Profile Fields",
                    description=f"Profile is missing: {', '.join(missing_fields)}.",
                    proposed_action={"type": "prompt_action", "task": "fill_missing_fields", "fields": missing_fields},
                    reason="Completing mandatory metadata fields improves data quality index score and reduces compliance risk flags.",
                    confidence=95.0,
                    business_impact="Unlocks automated payment verification runs.",
                    estimated_score_improvement=len(missing_fields) * 4.0,
                    status="Pending"
                ))

            if recs:
                db.session.add_all(recs)
                db.session.commit()
                
            return [r.to_dict() for r in recs]
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error generating AI recommendations: {str(e)}")
            return []

    @staticmethod
    def apply_recommendation(rec_id: int, reviewer: str) -> dict:
        """One-click approval apply mechanism to execute recommendations dynamically."""
        try:
            rec = AiRecommendation.query.get(rec_id)
            if not rec or rec.status != 'Pending':
                return {'success': False, 'message': 'Recommendation not found or already processed'}
                
            action = rec.proposed_action
            action_type = action.get('type')
            
            if action_type == 'update_field':
                # Apply update to Vendor
                vendor = Vendor.query.get(rec.vendor_id)
                if not vendor:
                    return {'success': False, 'message': 'Vendor profile not found'}
                    
                field = action.get('field')
                val = action.get('value')
                
                # Check fields
                if field == 'vendor_name':
                    vendor.vendor_name = val
                elif field == 'email':
                    vendor.email = val
                elif field == 'phone':
                    vendor.phone = val
                elif field == 'address':
                    vendor.address = val
                
                # Mark spelling suggestion as approved
                sug_id = action.get('suggestion_id')
                if sug_id:
                    sug = DataCleaningSuggestion.query.get(sug_id)
                    if sug:
                        sug.status = 'Approved'
                        
                db.session.commit()
                
                # Log timeline activity
                TimelineService.log_activity(
                    vendor_id=rec.vendor_id,
                    activity_type='Vendor Updated',
                    description=f"Applied AI Recommendation: Updated {field} to '{val}'.",
                    performed_by=reviewer
                )

            elif action_type == 'verify_document':
                # Approve document status
                doc_id = action.get('doc_id')
                doc = VendorDocument.query.get(doc_id)
                if doc:
                    doc.verification_status = 'Verified'
                    db.session.commit()
                    
                    TimelineService.log_activity(
                        vendor_id=rec.vendor_id,
                        activity_type='Admin Actions',
                        description=f"Applied AI Recommendation: Verified Document '{doc.name}'.",
                        performed_by=reviewer
                    )

            elif action_type == 'merge_vendors':
                # Consolidate target duplicate vendor (mock delete)
                target_id = action.get('target_vendor_id')
                target = Vendor.query.get(target_id)
                if target:
                    db.session.delete(target)
                    db.session.commit()
                    
                    TimelineService.log_activity(
                        vendor_id=rec.vendor_id,
                        activity_type='Admin Actions',
                        description=f"Applied AI Recommendation: Merged duplicate Vendor ID {target_id} into this profile.",
                        performed_by=reviewer
                    )
            
            # Recalculate scores after execution
            from src.domain.services.trust_engine import TrustEngine
            from src.domain.services.compliance_engine import ComplianceEngine
            from src.domain.services.fraud_engine import FraudEngine
            
            ComplianceEngine.evaluate_compliance(rec.vendor_id)
            FraudEngine.execute_scan(rec.vendor_id)
            TrustEngine.calculate_vendor_trust(rec.vendor_id)
            
            rec.status = 'Approved'
            db.session.commit()
            
            # System Audit Log
            from src.domain.services.audit_service import AuditService
            AuditService.log_audit(
                performed_by=reviewer,
                ip_address='127.0.0.1',
                action_type="Approve Recommendation",
                module_name="Recommendation",
                old_value={"status": "Pending"},
                new_value={"status": "Approved", "action": rec.proposed_action},
                reason=f"Applied AI Recommendation: {rec.title}",
                vendor_id=rec.vendor_id
            )
            
            # Send Notification Alert
            NotificationService.create_notification(
                vendor_id=rec.vendor_id,
                title="Recommendation Applied",
                message=f"Applied AI Recommendation: {rec.title}.",
                priority="Low",
                category="System",
                target_roles=["Admin", "Manager"]
            )
            
            return {'success': True, 'recommendation': rec.to_dict()}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error applying recommendation {rec_id}: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def reject_recommendation(rec_id: int, reviewer: str) -> dict:
        """Dismisses/rejects AI suggestions."""
        try:
            rec = AiRecommendation.query.get(rec_id)
            if not rec or rec.status != 'Pending':
                return {'success': False, 'message': 'Recommendation not found or already processed'}
                
            rec.status = 'Rejected'
            
            # Mark data cleaning suggestion as rejected if linked
            action = rec.proposed_action
            if action.get('type') == 'update_field':
                sug_id = action.get('suggestion_id')
                if sug_id:
                    sug = DataCleaningSuggestion.query.get(sug_id)
                    if sug:
                        sug.status = 'Rejected'
                        
            db.session.commit()
            
            # Log timeline audit
            TimelineService.log_activity(
                vendor_id=rec.vendor_id,
                activity_type='Admin Actions',
                description=f"Rejected AI Recommendation suggestion: '{rec.title}'.",
                performed_by=reviewer
            )
            
            return {'success': True, 'recommendation': rec.to_dict()}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}
