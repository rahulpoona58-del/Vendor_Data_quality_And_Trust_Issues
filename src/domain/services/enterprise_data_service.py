from src.infrastructure.database.models import Vendor, VendorTrustHistory, FraudCheck, VendorComplianceStatus, VendorDocument, AuditLog, User, db
import logging

class EnterpriseDataService:
    """Unified Enterprise Data Service delivering consolidated real-time analytics across all 13 enterprise dashboards."""

    @staticmethod
    def get_unified_enterprise_telemetry() -> dict:
        """Calculates live aggregated metrics for Executive Dashboard, Vendor360, Trust, Risk, Fraud, Health, GIS, AI, & Reports."""
        try:
            vendors = Vendor.query.all()
            trust_history = VendorTrustHistory.query.all()
            fraud_checks = FraudCheck.query.all()
            compliance_profiles = VendorComplianceStatus.query.all()
            documents = VendorDocument.query.all()
            audit_logs = AuditLog.query.all()
            users = User.query.all()
            
            total_vendors = len(vendors)
            avg_trust = sum(v.trust_score for v in vendors) / total_vendors if total_vendors > 0 else 0.0
            avg_compliance = sum(c.compliance_score for c in compliance_profiles) / len(compliance_profiles) if compliance_profiles else 0.0
            active_frauds = sum(1 for f in fraud_checks if f.status == 'Alert')
            high_risk_vendors = sum(1 for v in vendors if v.trust_level == 'Low Trust' or v.trust_score < 40)
            
            # Category breakdown
            category_counts = {}
            for v in vendors:
                cat = v.category or 'General'
                category_counts[cat] = category_counts.get(cat, 0) + 1

            # GIS location coordinates
            gis_data = [
                {
                    'id': v.id,
                    'name': v.name,
                    'city': v.city or 'New Delhi',
                    'state': v.state or 'Delhi',
                    'trust_score': v.trust_score,
                    'trust_level': v.trust_level
                }
                for v in vendors
            ]

            return {
                'success': True,
                'kpis': {
                    'total_vendors': total_vendors,
                    'average_trust_score': round(avg_trust, 2),
                    'average_compliance_score': round(avg_compliance, 2),
                    'active_fraud_alerts': active_frauds,
                    'high_risk_vendor_count': high_risk_vendors,
                    'total_documents': len(documents),
                    'total_audit_logs': len(audit_logs),
                    'total_users': len(users)
                },
                'category_distribution': category_counts,
                'gis_data': gis_data
            }
        except Exception as e:
            logging.error(f"EnterpriseDataService error: {str(e)}")
            return {'success': False, 'message': str(e)}
