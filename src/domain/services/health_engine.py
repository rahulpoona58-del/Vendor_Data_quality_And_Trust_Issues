from src.infrastructure.database.models import Vendor, VendorComplianceStatus, FraudCheck, VendorDocument, VendorActivity, VendorTrustHistory
import logging

class HealthEngine:
    """Combines Trust, Compliance, Fraud, Quality, and Document statistics into a single unified health index."""
    
    @staticmethod
    def calculate_health(vendor_id: int = None) -> dict:
        """Computes weighted Health Index for a single vendor or compiles registry category totals."""
        try:
            if vendor_id:
                return HealthEngine._calculate_single_vendor(vendor_id)
            else:
                return HealthEngine._calculate_registry_summary()
        except Exception as e:
            logging.error(f"Health index compilation failed: {str(e)}")
            return {'success': False, 'message': str(e)}
            
    @staticmethod
    def _calculate_single_vendor(vendor_id: int) -> dict:
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return {'success': False, 'message': 'Vendor profile not found'}
            
        # 1. Gather component metrics
        trust = vendor.trust_score
        quality_scaled = vendor.quality_rating * 20.0 # scale 5.0 to 100
        
        risk = max(5.0, 100.0 - vendor.trust_score) # fallback
        history_latest = VendorTrustHistory.query.filter_by(vendor_id=vendor_id).order_by(VendorTrustHistory.calculated_at.desc()).first()
        if history_latest:
            risk = history_latest.risk_score
            
        compliance = 85.0
        comp_status = VendorComplianceStatus.query.filter_by(vendor_id=vendor_id).first()
        if comp_status:
            compliance = comp_status.compliance_score
            
        fraud = 0.0
        fraud_status = FraudCheck.query.filter_by(vendor_id=vendor_id).first()
        if fraud_status:
            fraud = fraud_status.fraud_score
            
        # 2. Document completeness (assume 5 core documents required: GST, PAN, ISO, NDA, Insurance)
        doc_count = VendorDocument.query.filter_by(vendor_id=vendor_id, is_deleted=False).count()
        doc_completeness = min(100.0, (doc_count / 5.0) * 100.0)
        
        # 3. Activity index (Timeline event log volume)
        event_count = VendorActivity.query.filter_by(vendor_id=vendor_id).count()
        activity_index = min(100.0, event_count * 12.5) # 8 events = 100%
        
        # 4. Invert risk and fraud threat vectors
        inverted_risk = 100.0 - risk
        inverted_fraud = 100.0 - fraud
        
        # 5. Weighted score calculation
        # Trust: 20%, Compliance: 20%, Quality: 15%, Risk: 15%, Fraud: 15%, Docs: 10%, Activity: 5%
        health_score = (
            (trust * 0.20) +
            (compliance * 0.20) +
            (quality_scaled * 0.15) +
            (inverted_risk * 0.15) +
            (inverted_fraud * 0.15) +
            (doc_completeness * 0.10) +
            (activity_index * 0.05)
        )
        
        health_score = max(0.0, min(100.0, health_score))
        
        # 6. Resolve Health Category
        if health_score >= 90.0:
            category = "Excellent"
            color_class = "success"
        elif health_score >= 75.0:
            category = "Good"
            color_class = "info"
        elif health_score >= 55.0:
            category = "Average"
            color_class = "warning"
        elif health_score >= 35.0:
            category = "Poor"
            color_class = "danger"
        else:
            category = "Critical"
            color_class = "danger"
            
        return {
            'success': True,
            'vendor_id': vendor_id,
            'vendor_name': vendor.name,
            'health_score': round(health_score, 1),
            'category': category,
            'color_class': color_class,
            'breakdown': {
                'trust': round(trust, 1),
                'compliance': round(compliance, 1),
                'quality': round(quality_scaled, 1),
                'risk': round(risk, 1),
                'fraud': round(fraud, 1),
                'document_completeness': round(doc_completeness, 1),
                'activity_index': round(activity_index, 1)
            }
        }
        
    @staticmethod
    def _calculate_registry_summary() -> dict:
        vendors = Vendor.query.all()
        
        summary = {
            'Excellent': 0,
            'Good': 0,
            'Average': 0,
            'Poor': 0,
            'Critical': 0
        }
        
        total_score = 0.0
        count = len(vendors)
        
        for v in vendors:
            res = HealthEngine._calculate_single_vendor(v.id)
            if res.get('success'):
                cat = res['category']
                summary[cat] += 1
                total_score += res['health_score']
                
        avg_health = (total_score / count) if count > 0 else 0.0
        
        return {
            'success': True,
            'total_vendors': count,
            'average_health_score': round(avg_health, 1),
            'distribution': summary
        }
