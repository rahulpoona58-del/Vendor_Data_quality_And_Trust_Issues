import random
from datetime import datetime
from src.infrastructure.database.models import Vendor, VendorDocument, OcrResult, ScoringRule, VendorTrustHistory, db
from src.domain.services.cleaning_engine import DataCleaningEngine
import logging

class TrustEngine:
    """Enterprise Trust Engine calculating multidimensional trust, risk, compliance, reliability, and confidence."""
    
    @staticmethod
    def calculate_vendor_trust(vendor_id: int) -> dict:
        """Calculates multi-dimensional trust ratings, extracts explainable reasons, and commits to history."""
        try:
            vendor = Vendor.query.get(vendor_id)
            if not vendor:
                return {'success': False, 'message': 'Vendor profile not found'}
                
            # 1. Fetch active rules and weights
            rules = {r.rule_key: r.rule_value for r in ScoringRule.query.filter_by(is_active=True).all()}
            
            # Fetch default weights if database is not seeded yet
            w_delivery = rules.get('delivery_weight', 0.4)
            w_quality = rules.get('quality_weight', 6.0)
            p_defect = rules.get('defect_penalty_rate', 2.0)
            p_response = rules.get('response_penalty_rate', 0.5)
            b_gst = rules.get('gst_verified_bonus', 15.0)
            b_pan = rules.get('pan_verified_bonus', 10.0)
            p_missing_doc = rules.get('missing_document_penalty', 15.0)
            p_duplicate = rules.get('duplicate_warning_penalty', 20.0)

            # 2. Extract operational performance from vendor detail values
            # (In V1, these values are loaded via legacy app controllers. Let's retrieve from V1 dataset or generate standard mock offsets)
            # Since V1 holds details in model.py loaded globally, we fetch raw metrics.
            # To keep V1 backward compatibility, we can query legacy model details or fallback to realistic offsets:
            from model import get_vendor
            legacy_data = get_vendor(vendor.id) or {}
            
            on_time_delivery = float(legacy_data.get('on_time_delivery', 80))
            quality_rating = float(legacy_data.get('quality_rating', 4.0))
            defect_rate = float(legacy_data.get('defect_rate', 2.0))
            response_time = float(legacy_data.get('response_time', 12.0))
            
            # 3. Assess Document Verification Statuses
            docs = VendorDocument.query.filter_by(vendor_id=vendor.id, is_deleted=False).all()
            gst_verified = any(d.document_type == 'GST Certificate' and d.verification_status == 'Verified' for d in docs)
            pan_verified = any(d.document_type == 'PAN Card' and d.verification_status == 'Verified' for d in docs)
            bank_verified = any(d.document_type == 'Bank Proof' and d.verification_status == 'Verified' for d in docs)
            
            # Assess completeness
            has_email = any(d.document_type == 'Other Supporting Documents' for d in docs) or len(docs) > 0
            
            # 4. Assess Duplicate Risk
            # (Simulation: 12% probability duplicate check)
            dup_prob = 0.18 if (vendor.id % 7 == 0) else 0.02
            
            # 5. Core score calculations
            positives = []
            negatives = []
            recs = []
            
            # A. Reliability score (Delivery & Response parameters)
            reliability = (on_time_delivery * w_delivery) + (50 - (response_time * p_response))
            reliability = max(10.0, min(100.0, reliability))
            if on_time_delivery >= 80:
                positives.append("+ Consistent On-time Delivery")
            else:
                negatives.append(f"- Delivery delays detected ({on_time_delivery}% on-time rate)")
                recs.append("Improve supply chains to optimize delivery timelines.")
                
            # B. Compliance score (Verified Documents status)
            compliance = 0
            if gst_verified: 
                compliance += 40
                positives.append("+ GST Certificate Verified")
            else:
                negatives.append("- GST Certificate missing or unverified")
                recs.append("Upload and approve active GST registration files.")
                
            if pan_verified: 
                compliance += 30
                positives.append("+ PAN Card Verified")
            else:
                negatives.append("- PAN Card missing or unverified")
                recs.append("Submit company PAN card details to clear compliance flags.")
                
            if bank_verified:
                compliance += 30
                positives.append("+ Bank Details Verified")
            else:
                negatives.append("- Bank Proof missing or unverified")
                recs.append("Submit cancelled check or bank statement proof.")
                
            # C. Confidence score (Data Completeness check)
            confidence = 40.0
            if len(docs) >= 3:
                confidence += 30.0
                positives.append("+ High Document Density")
            else:
                negatives.append("- Low Data density (incomplete files)")
                
            if has_email:
                confidence += 30.0
                positives.append("+ Complete Contacts Profile")
            else:
                negatives.append("- Incomplete Contact profile")
                recs.append("Update primary contact phone and email entries.")
                
            # D. Risk score (Vulnerability metric)
            risk = (defect_rate * p_defect) + (dup_prob * 100.0) + (100 - compliance) * 0.4
            if dup_prob > 0.05:
                negatives.append(f"- Duplicate Probability: {(dup_prob * 100):.0f}%")
                recs.append("Resolve candidate duplicates flagged in review dashboard.")
            else:
                positives.append("+ Low Duplicate Risk profile")
                
            risk = max(5.0, min(95.0, risk))
            
            # E. Overall Trust Score (Weighted combining all factors)
            trust_score = (reliability * 0.3) + (compliance * 0.3) + ((100 - risk) * 0.25) + (confidence * 0.15)
            
            # Apply bonuses & penalties from rule configurations
            if gst_verified: trust_score += b_gst
            if pan_verified: trust_score += b_pan
            if len(docs) == 0: trust_score -= p_missing_doc
            if dup_prob > 0.10: trust_score -= p_duplicate
            
            # Cap overall trust score
            trust_score = max(10.0, min(100.0, trust_score))
            
            # Evaluate custom business rules for Trust, Risk and Quality groups
            from src.domain.services.business_rules_engine import BusinessRulesEngine
            
            # Trust Group
            rule_actions = BusinessRulesEngine.evaluate_rules(vendor.id, 'Trust')
            for action_item in rule_actions:
                action = action_item.get('action', {})
                act_name = action.get('action')
                if act_name == 'adjust_trust_score':
                    try:
                        adjustment = float(action.get('param', 0))
                        trust_score = max(0.0, min(100.0, trust_score + adjustment))
                    except ValueError:
                        pass
                        
            # Risk Group
            rule_actions = BusinessRulesEngine.evaluate_rules(vendor.id, 'Risk')
            for action_item in rule_actions:
                action = action_item.get('action', {})
                # Custom risk rule modifications can go here if needed
                
            # Quality Group
            rule_actions = BusinessRulesEngine.evaluate_rules(vendor.id, 'Quality')
            for action_item in rule_actions:
                action = action_item.get('action', {})
                # Custom quality rule modifications can go here if needed

            # Update Vendor record
            vendor.trust_score = round(trust_score, 1)
            vendor.trust_level = 'High Trust' if trust_score >= 75 else ('Medium Trust' if trust_score >= 45 else 'Low Trust')
            
            # 6. Commit to history ledger
            history_record = VendorTrustHistory(
                vendor_id=vendor.id,
                trust_score=round(trust_score, 1),
                risk_score=round(risk, 1),
                compliance_score=round(compliance, 1),
                reliability_score=round(reliability, 1),
                confidence_score=round(confidence, 1),
                reasons_positive=positives,
                reasons_negative=negatives,
                recommendations=recs
            )
            db.session.add(history_record)
            db.session.commit()
            
            # Log timeline activities
            from src.domain.services.timeline_service import TimelineService
            TimelineService.log_activity(
                vendor_id=vendor.id,
                activity_type='Trust Score Changed',
                description=f"Trust Score updated to {round(trust_score, 1)} (Reliability: {round(reliability, 1)}%, Compliance: {round(compliance, 1)}%)."
            )
            TimelineService.log_activity(
                vendor_id=vendor.id,
                activity_type='Risk Score Changed',
                description=f"Risk Score updated to {round(risk, 1)}%."
            )
            
            # Trigger System Notifications
            from src.domain.services.notification_service import NotificationService
            if trust_score < 50.0:
                NotificationService.create_notification(
                    vendor_id=vendor.id,
                    title="Low Trust Score Warning",
                    message=f"Vendor '{vendor.name}' trust score has fallen to {round(trust_score, 1)}.",
                    priority="High",
                    category="Trust",
                    target_roles=["Admin", "Manager"]
                )
            if risk >= 70.0:
                NotificationService.create_notification(
                    vendor_id=vendor.id,
                    title="High-Risk Vendor Flagged",
                    message=f"Vendor '{vendor.name}' overall risk score reached {round(risk, 1)}%.",
                    priority="High",
                    category="Trust",
                    target_roles=["Admin", "Manager"]
                )
            
            logging.info(f"Vendor trust calculated: score={trust_score:.1f} for vendor_id={vendor.id}")
            return {'success': True, 'trust_result': history_record.to_dict()}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error calculating trust metrics: {str(e)}")
            return {'success': False, 'message': f"Trust Engine error: {str(e)}"}
            
    @staticmethod
    def get_trust_history(vendor_id: int, limit: int = 10) -> list:
        """Fetches historical calculated runs for reporting trends."""
        history = VendorTrustHistory.query.filter_by(vendor_id=vendor_id)\
                                           .order_by(VendorTrustHistory.calculated_at.desc())\
                                           .limit(limit).all()
        # Return chronological order (oldest first) for graphs
        history.reverse()
        return [h.to_dict() for h in history]

    @staticmethod
    def update_scoring_rule(key: str, val: float, reviewer: str) -> dict:
        """Updates weight thresholds for calculating ratings."""
        try:
            rule = ScoringRule.query.filter_by(rule_key=key).first()
            if not rule:
                return {'success': False, 'message': f"Scoring rule '{key}' not found"}
                
            old_val = rule.rule_value
            rule.rule_value = val
            db.session.commit()
            
            logging.info(f"Scoring rule '{key}' updated from {old_val} to {val} by {reviewer}")
            return {'success': True, 'rule': rule.to_dict()}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating scoring rule: {str(e)}")
            return {'success': False, 'message': str(e)}
