from datetime import datetime
from src.infrastructure.database.models import Vendor, VendorDocument, SystemAuditLog, DataCleaningSuggestion, FraudCheck, VendorReputation, db
import logging

class ReputationIntelligenceEngine:
    """Calculates and stores explainable, versioned, non-arbitrary vendor reputation intelligence scores."""
    
    @staticmethod
    def calculate_reputation(vendor_id: int, version: str = 'v1.0') -> dict:
        """Calculates and records the reputation profile for a single vendor using evidence-based parameters."""
        try:
            vendor = Vendor.query.get(vendor_id)
            if not vendor:
                return {'success': False, 'message': 'Vendor not found'}
                
            # 1. Compliance Score (Orthogonal dimension)
            docs = VendorDocument.query.filter_by(vendor_id=vendor_id).all()
            if not docs:
                compliance_score = 65.0 # baseline benchmark
                compliance_evidence = "Default baseline applied (no compliance documents uploaded)."
            else:
                verified_count = sum(1 for d in docs if d.verification_status == 'Verified')
                compliance_score = (verified_count / len(docs)) * 100.0
                compliance_evidence = f"{verified_count} of {len(docs)} compliance documents fully verified."
                
            # 2. Operational Integrity (Orthogonal dimension)
            fraud_record = FraudCheck.query.filter_by(vendor_id=vendor_id).first()
            if not fraud_record:
                integrity_score = 80.0 # standard default
                integrity_evidence = "Standard monitoring status (no active fraud checks run)."
            else:
                # Deduct based on fraud score
                integrity_score = 100.0 - float(fraud_record.fraud_score)
                integrity_evidence = f"Integrity assessed from active fraud alert checks. Fraud threat score is {fraud_record.fraud_score}."
                
            # 3. Data Quality Score (Orthogonal dimension)
            clean_sugs = DataCleaningSuggestion.query.filter_by(vendor_id=vendor_id, status='Pending').all()
            quality_score = max(0.0, 100.0 - (len(clean_sugs) * 12.0))
            quality_evidence = f"{len(clean_sugs)} active formatting anomalies detected in profile registry."
            
            # 4. Historical Stability Score (Orthogonal dimension)
            overrides_count = SystemAuditLog.query.filter_by(vendor_id=vendor_id).count()
            stability_score = max(0.0, 100.0 - (overrides_count * 10.0))
            stability_evidence = f"{overrides_count} historic change logs recorded in the audit trail."
            
            # Prevent double-counting by combining orthogonal dimensions using versioned formula weights
            if version == 'v1.0':
                reputation_score = (
                    0.25 * compliance_score +
                    0.25 * integrity_score +
                    0.25 * quality_score +
                    0.25 * stability_score
                )
            else:
                # Fallback to v1.0
                reputation_score = (
                    0.25 * compliance_score +
                    0.25 * integrity_score +
                    0.25 * quality_score +
                    0.25 * stability_score
                )
                
            # Resolve Reputation Tier
            if reputation_score >= 85:
                tier = "Elite Partner"
            elif reputation_score >= 70:
                tier = "Trustworthy"
            elif reputation_score >= 50:
                tier = "Acceptable"
            elif reputation_score >= 35:
                tier = "Under Review"
            else:
                tier = "High Risk"
                
            # Determine Positive/Negative Factors
            pos_factors = []
            neg_factors = []
            recommendations = []
            
            if compliance_score >= 80:
                pos_factors.append("Excellent compliance credentials verification rate.")
            else:
                neg_factors.append("Unverified compliance document filings found.")
                recommendations.append("Upload missing KYC credentials and verify existing documents.")
                
            if integrity_score >= 80:
                pos_factors.append("Zero matching fraud or identity overlap indicators.")
            else:
                neg_factors.append("Potential identity sharing flags identified.")
                recommendations.append("Submit director identification documents to clear fraud alert logs.")
                
            if quality_score >= 90:
                pos_factors.append("Clean registry attributes formatting profile.")
            else:
                neg_factors.append("Spelling or casing typos in corporate registry details.")
                recommendations.append("Review and apply spelling and formatting suggestions inside the Cleaning tab.")
                
            if stability_score >= 80:
                pos_factors.append("Highly stable registration history (low changes frequency).")
            else:
                neg_factors.append("Frequent administrative overrides on master attributes.")
                
            # Calculate evidence confidence level
            confidence = 95.0
            if not docs: confidence -= 10.0
            if not fraud_record: confidence -= 10.0
            
            # Check if record already exists
            rep = VendorReputation.query.filter_by(vendor_id=vendor_id, formula_version=version).first()
            if not rep:
                rep = VendorReputation(
                    vendor_id=vendor_id,
                    reputation_score=reputation_score,
                    reputation_tier=tier,
                    formula_version=version,
                    score_breakdown={
                        'compliance': {'score': compliance_score, 'evidence': compliance_evidence},
                        'integrity': {'score': integrity_score, 'evidence': integrity_evidence},
                        'quality': {'score': quality_score, 'evidence': quality_evidence},
                        'stability': {'score': stability_score, 'evidence': stability_evidence}
                    },
                    positive_factors=pos_factors,
                    negative_factors=neg_factors,
                    recommendations=recommendations,
                    confidence_level=confidence
                )
                db.session.add(rep)
            else:
                rep.reputation_score = reputation_score
                rep.reputation_tier = tier
                rep.score_breakdown = {
                    'compliance': {'score': compliance_score, 'evidence': compliance_evidence},
                    'integrity': {'score': integrity_score, 'evidence': integrity_evidence},
                    'quality': {'score': quality_score, 'evidence': quality_evidence},
                    'stability': {'score': stability_score, 'evidence': stability_evidence}
                }
                rep.positive_factors = pos_factors
                rep.negative_factors = neg_factors
                rep.recommendations = recommendations
                rep.confidence_level = confidence
                
            db.session.commit()
            return {'success': True, 'reputation': rep.to_dict()}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error calculating vendor reputation: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def calculate_cohort_reputations(version: str = 'v1.0') -> dict:
        """Calculates reputation ratings for the entire vendor registry."""
        try:
            vendors = Vendor.query.all()
            completed = 0
            for v in vendors:
                res = ReputationIntelligenceEngine.calculate_reputation(v.id, version)
                if res['success']:
                    completed += 1
            return {'success': True, 'calculated_count': completed}
        except Exception as e:
            logging.error(f"Failed to calculate cohort reputations: {str(e)}")
            return {'success': False, 'message': str(e)}
