from src.infrastructure.database.models import Vendor, VendorDocument, FraudCheck, ScoringRule, VendorComplianceStatus, SystemAuditLog, DataCleaningSuggestion, db
from src.domain.services.health_engine import HealthEngine
from src.domain.services.reputation_engine import ReputationIntelligenceEngine
import logging

class SimulationEngine:
    """Isolated sandbox simulator for vendor risk, trust, compliance, and reputation scores."""
    
    @staticmethod
    def simulate_what_if(vendor_id: int, overrides: dict) -> dict:
        """Runs an in-memory recalculation of vendor scores under hypothetical changes, ensuring database isolation."""
        try:
            vendor = Vendor.query.get(vendor_id)
            if not vendor:
                return {'success': False, 'message': 'Vendor profile not found'}
                
            # --- 1. GATHER BEFORE STATE (CURRENT PRODUCTION DATA) ---
            # Fetch actual current metrics
            current_trust = vendor.trust_score
            current_quality = vendor.quality_rating
            current_risk = 100.0 - current_trust
            
            # Fetch current compliance status
            comp_status = VendorComplianceStatus.query.filter_by(vendor_id=vendor_id).first()
            current_compliance = comp_status.compliance_score if comp_status else 70.0
            
            # Fetch health status
            health_res = HealthEngine.calculate_health(vendor_id)
            current_health = health_res.get('health_score', 50.0) if health_res.get('success') else 50.0
            current_health_category = health_res.get('category', 'Average')
            
            # Fetch reputation status
            rep_res = ReputationIntelligenceEngine.calculate_reputation(vendor_id)
            if rep_res.get('success'):
                current_reputation = rep_res['reputation']['reputation_score']
                current_reputation_tier = rep_res['reputation']['reputation_tier']
            else:
                current_reputation = 50.0
                current_reputation_tier = 'Acceptable'
                
            # --- 2. RUN SIMULATION CALCULATIONS (IN-MEMORY OVERRIDES) ---
            # Fetch rules & weights
            rules = {r.rule_key: r.rule_value for r in ScoringRule.query.filter_by(is_active=True).all()}
            w_delivery = rules.get('delivery_weight', 0.4)
            w_quality = rules.get('quality_weight', 6.0)
            p_defect = rules.get('defect_penalty_rate', 2.0)
            p_response = rules.get('response_penalty_rate', 0.5)
            b_gst = rules.get('gst_verified_bonus', 15.0)
            b_pan = rules.get('pan_verified_bonus', 10.0)
            p_missing_doc = rules.get('missing_document_penalty', 15.0)
            p_duplicate = rules.get('duplicate_warning_penalty', 20.0)
            
            # Retrieve legacy performance parameters
            from model import get_vendor
            legacy_data = get_vendor(vendor.id) or {}
            on_time_delivery = float(legacy_data.get('on_time_delivery', 80))
            raw_quality_rating = float(legacy_data.get('quality_rating', 4.0))
            defect_rate = float(legacy_data.get('defect_rate', 2.0))
            response_time = float(legacy_data.get('response_time', 12.0))
            
            # Simulate Quality Overrides
            simulated_quality_rating = raw_quality_rating
            if 'quality_rating' in overrides:
                simulated_quality_rating = float(overrides['quality_rating'])
                # If quality is improved, reduce defect rate proportionally
                if simulated_quality_rating >= 4.5:
                    defect_rate = max(0.5, defect_rate - 1.5)
                elif simulated_quality_rating <= 2.5:
                    defect_rate = defect_rate + 2.0
            
            # Retrieve actual documents
            docs = VendorDocument.query.filter_by(vendor_id=vendor_id, is_deleted=False).all()
            doc_types = [d.document_type for d in docs]
            
            # Document verification status overrides
            gst_verified = any(d.document_type == 'GST Certificate' and d.verification_status == 'Verified' for d in docs)
            pan_verified = any(d.document_type == 'PAN Card' and d.verification_status == 'Verified' for d in docs)
            bank_verified = any(d.document_type == 'Bank Proof' and d.verification_status == 'Verified' for d in docs)
            
            # Apply overrides for verification status
            if 'gst_verified' in overrides:
                gst_verified = bool(overrides['gst_verified'])
            if 'pan_verified' in overrides:
                pan_verified = bool(overrides['pan_verified'])
            if 'bank_verified' in overrides:
                bank_verified = bool(overrides['bank_verified'])
                
            if overrides.get('compliance_docs_expired', False):
                gst_verified = False
                pan_verified = False
                bank_verified = False
                
            if overrides.get('documents_verified', False):
                gst_verified = True
                pan_verified = True
                bank_verified = True
                
            # Simulate duplicate risk override
            dup_prob = 0.18 if (vendor.id % 7 == 0) else 0.02
            if 'duplicate_relationship' in overrides:
                dup_prob = 0.65 if overrides['duplicate_relationship'] else 0.01
                
            # Simulate contact completeness (Missing fields corrected)
            has_email = any(d.document_type == 'Other Supporting Documents' for d in docs) or len(docs) > 0
            if overrides.get('missing_fields_corrected', False):
                has_email = True
                
            # A. Simulated Reliability
            sim_reliability = (on_time_delivery * w_delivery) + (50 - (response_time * p_response))
            sim_reliability = max(10.0, min(100.0, sim_reliability))
            
            # B. Simulated Compliance
            sim_compliance = 0
            if gst_verified: sim_compliance += 40
            if pan_verified: sim_compliance += 30
            if bank_verified: sim_compliance += 30
            
            # C. Simulated Confidence
            sim_confidence = 40.0
            doc_count = len(docs)
            if overrides.get('compliance_docs_expired', False):
                doc_count = max(0, doc_count - 2)
            if doc_count >= 3:
                sim_confidence += 30.0
            if has_email:
                sim_confidence += 30.0
                
            # D. Simulated Risk
            sim_risk = (defect_rate * p_defect) + (dup_prob * 100.0) + (100.0 - sim_compliance) * 0.4
            sim_risk = max(5.0, min(95.0, sim_risk))
            
            # E. Simulated Trust Score
            sim_trust = (sim_reliability * 0.3) + (sim_compliance * 0.3) + ((100.0 - sim_risk) * 0.25) + (sim_confidence * 0.15)
            
            if gst_verified: sim_trust += b_gst
            if pan_verified: sim_trust += b_pan
            if doc_count == 0: sim_trust -= p_missing_doc
            if dup_prob > 0.10: sim_trust -= p_duplicate
            
            sim_trust = max(10.0, min(100.0, sim_trust))
            
            # F. Simulated Fraud
            fraud_record = FraudCheck.query.filter_by(vendor_id=vendor_id).first()
            sim_fraud = fraud_record.fraud_score if fraud_record else 10.0
            if overrides.get('fraud_evidence_added', False):
                sim_fraud = min(100.0, max(sim_fraud + 30.0, 99.0))
                
            # G. Simulated Health Index
            quality_scaled = simulated_quality_rating * 20.0
            doc_completeness = min(100.0, (doc_count / 5.0) * 100.0)
            activity_index = min(100.0, 3 * 12.5) # baseline proxy
            
            inverted_risk = 100.0 - sim_risk
            inverted_fraud = 100.0 - sim_fraud
            
            sim_health = (
                (sim_trust * 0.20) +
                (sim_compliance * 0.20) +
                (quality_scaled * 0.15) +
                (inverted_risk * 0.15) +
                (inverted_fraud * 0.15) +
                (doc_completeness * 0.10) +
                (activity_index * 0.05)
            )
            sim_health = max(0.0, min(100.0, sim_health))
            
            if sim_health >= 90.0:
                sim_health_cat = "Excellent"
            elif sim_health >= 75.0:
                sim_health_cat = "Good"
            elif sim_health >= 55.0:
                sim_health_cat = "Average"
            elif sim_health >= 35.0:
                sim_health_cat = "Poor"
            else:
                sim_health_cat = "Critical"
                
            # H. Simulated Reputation Score
            # Data quality score override simulation
            clean_sugs_count = 1
            if overrides.get('missing_fields_corrected', False):
                clean_sugs_count = 0
            sim_quality_score = max(0.0, 100.0 - (clean_sugs_count * 12.0))
            
            # Stability score
            stability_score = 90.0 # standard baseline proxy
            
            sim_reputation = (
                0.25 * sim_compliance +
                0.25 * (100.0 - sim_fraud) +
                0.25 * sim_quality_score +
                0.25 * stability_score
            )
            
            if sim_reputation >= 85:
                sim_reputation_tier = "Elite Partner"
            elif sim_reputation >= 70:
                sim_reputation_tier = "Trustworthy"
            elif sim_reputation >= 50:
                sim_reputation_tier = "Acceptable"
            elif sim_reputation >= 35:
                sim_reputation_tier = "Under Review"
            else:
                sim_reputation_tier = "High Risk"
                
            # Explain rules triggered
            rules_triggered = []
            if sim_trust < 50.0:
                rules_triggered.append("Alert: Overall Trust score falls below standard compliance threshold.")
            if sim_risk > 70.0:
                rules_triggered.append("Alert: Critical Risk threshold reached (> 70.0%).")
            if dup_prob > 0.10:
                rules_triggered.append("Rule: Duplicate Warning Penalty applied (-20.0 Trust Score points).")
            if gst_verified:
                rules_triggered.append("Bonus: GST Certificate Verification verified (+15.0 bonus applied).")
            if pan_verified:
                rules_triggered.append("Bonus: PAN Card Verification verified (+10.0 bonus applied).")
            if doc_count == 0:
                rules_triggered.append("Penalty: Missing compliance documents penalty applied (-15.0 trust points).")
                
            # Business Impact Assessment
            if sim_trust < 40.0 or sim_risk > 75.0 or sim_reputation_tier == "High Risk":
                business_impact = "CRITICAL: Vendor moves to High Risk / Critical status. Automatic purchasing suspension will trigger. Active contracts placed under legal review."
                rec_action = "Action required: Complete immediate document audits. Submit missing regulatory filings to reset compliance standing."
            elif sim_trust < 60.0 or sim_reputation_tier == "Under Review":
                business_impact = "WARNING: Vendor reputation flagged under review. New orders capped at $15,000 threshold. Continuous monitoring enabled."
                rec_action = "Action required: Resolve pending spelling errors and contact field mismatches."
            else:
                business_impact = "STANDARD: Vendor remains in positive operational health standing. Procurement processes proceed automatically."
                rec_action = "Maintain standard compliance monitoring protocols."
                
            return {
                'success': True,
                'vendor_id': vendor_id,
                'vendor_name': vendor.name,
                'simulation_mode': 'SANDBOX_ISOLATED',
                'before': {
                    'trust_score': round(current_trust, 1),
                    'risk_score': round(current_risk, 1),
                    'quality_rating': round(current_quality, 1),
                    'compliance_score': round(current_compliance, 1),
                    'health_score': round(current_health, 1),
                    'health_category': current_health_category,
                    'reputation_score': round(current_reputation, 1),
                    'reputation_tier': current_reputation_tier
                },
                'after': {
                    'trust_score': round(sim_trust, 1),
                    'risk_score': round(sim_risk, 1),
                    'quality_rating': round(simulated_quality_rating, 1),
                    'compliance_score': round(sim_compliance, 1),
                    'health_score': round(sim_health, 1),
                    'health_category': sim_health_cat,
                    'reputation_score': round(sim_reputation, 1),
                    'reputation_tier': sim_reputation_tier
                },
                'affected_rules': rules_triggered,
                'business_impact': business_impact,
                'recommended_action': rec_action
            }
            
        except Exception as e:
            logging.error(f"What-if simulation run failed: {str(e)}")
            return {'success': False, 'message': f"Simulation error: {str(e)}"}
