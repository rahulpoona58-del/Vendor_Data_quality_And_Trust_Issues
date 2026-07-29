from datetime import datetime, timedelta
from src.infrastructure.database.models import Vendor, VendorTrustHistory, VendorDocument, FraudCheck, VendorComplianceStatus
import logging

class PredictiveAnalyticsEngine:
    """Forecasting engine projecting future scoring trends, document expiries, and threat vectors."""
    
    @staticmethod
    def generate_predictions(vendor_id: int = None) -> dict:
        """Assembles predictive metrics (Trust, Risk, Quality, Compliance Expiry) based on database history."""
        try:
            now = datetime.utcnow()
            months_ahead = ["Month +1", "Month +2", "Month +3", "Month +4", "Month +5", "Month +6"]
            
            # Default fallback vectors
            avg_trust = 70.0
            avg_risk = 30.0
            avg_quality = 4.0
            compliance_fail_prob = 15.0
            fraud_prob = 5.0
            dup_prob = 2.0
            growth_projection = [10, 15, 20, 25, 28, 32]
            
            expiring_docs = []
            recommendations = []
            
            # Fetch specific vendor if ID supplied, otherwise compute system averages
            if vendor_id:
                vendor = Vendor.query.get(vendor_id)
                if not vendor:
                    return {'success': False, 'message': 'Vendor profile not found'}
                    
                avg_trust = vendor.trust_score
                avg_quality = vendor.quality_rating
                avg_risk = max(5.0, 100.0 - vendor.trust_score)
                
                # Check fraud
                fraud = FraudCheck.query.filter_by(vendor_id=vendor_id).first()
                if fraud:
                    fraud_prob = fraud.fraud_score
                    if fraud.status == 'Alert':
                        dup_prob = 65.0
                        
                # Check compliance
                comp = VendorComplianceStatus.query.filter_by(vendor_id=vendor_id).first()
                if comp:
                    compliance_fail_prob = 100.0 - comp.compliance_score
                    
                # Expiries in next 90 days
                limit_dt = now + timedelta(days=90)
                docs = VendorDocument.query.filter(
                    VendorDocument.vendor_id == vendor_id,
                    VendorDocument.expiry_date > now,
                    VendorDocument.expiry_date < limit_dt,
                    VendorDocument.is_deleted == False
                ).all()
                for d in docs:
                    days_left = (d.expiry_date - now).days
                    expiring_docs.append({
                        'doc_name': d.name,
                        'doc_type': d.document_type,
                        'days_left': days_left,
                        'date': d.expiry_date.strftime('%Y-%m-%d')
                    })
                    
                # Analyze historical trend trajectory
                history = VendorTrustHistory.query.filter_by(vendor_id=vendor_id)\
                                                   .order_by(VendorTrustHistory.calculated_at.desc())\
                                                   .limit(5).all()
                if len(history) >= 2:
                    # Simple linear trajectory projection
                    diff_trust = history[0].trust_score - history[-1].trust_score
                    slope_trust = diff_trust / len(history)
                    
                    diff_risk = history[0].risk_score - history[-1].risk_score
                    slope_risk = diff_risk / len(history)
                else:
                    slope_trust = 1.2 # steady improvement mock
                    slope_risk = -0.8
                    
            else:
                # System-wide metrics
                vendors = Vendor.query.all()
                total = len(vendors)
                if total > 0:
                    avg_trust = sum(v.trust_score for v in vendors) / total
                    avg_quality = sum(v.quality_rating for v in vendors) / total
                    avg_risk = sum(max(5.0, 100.0 - v.trust_score) for v in vendors) / total
                    
                active_frauds = FraudCheck.query.filter_by(status='Alert').count()
                if total > 0:
                    fraud_prob = (active_frauds / total) * 100.0
                    dup_prob = (len(FraudCheck.query.all()) / total) * 5.0
                    
                expired_docs_count = VendorDocument.query.filter(VendorDocument.expiry_date < now, VendorDocument.is_deleted == False).count()
                if total > 0:
                    compliance_fail_prob = (expired_docs_count / total) * 45.0
                    
                slope_trust = 0.8
                slope_risk = -0.5
                
            # Compute 6-month projected series
            trust_forecast = []
            risk_forecast = []
            quality_forecast = []
            
            for i in range(1, 7):
                projected_t = max(10.0, min(100.0, avg_trust + (slope_trust * i)))
                projected_r = max(5.0, min(95.0, avg_risk + (slope_risk * i)))
                projected_q = max(1.0, min(5.0, avg_quality + (0.05 * i)))
                
                trust_forecast.append(round(projected_t, 1))
                risk_forecast.append(round(projected_r, 1))
                quality_forecast.append(round(projected_q, 1))
                
            # Compile recommendations
            if compliance_fail_prob > 30.0:
                recommendations.append({
                    'threat': 'High Compliance Failure Risk',
                    'impact': 'Regulatory compliance score drop will flag profiles for automatic suspension.',
                    'action': 'Schedule automated reminder notifications for upcoming credential expiries.'
                })
            if fraud_prob > 25.0:
                recommendations.append({
                    'threat': 'Elevated Fraud Index Alert',
                    'impact': 'Matching bank details or location parameters could indicate coordinate spoofing.',
                    'action': 'Trigger manual duplicate reviews and audit bank account statement validations.'
                })
            if avg_trust < 60.0:
                recommendations.append({
                    'threat': 'Low Vendor Trust Trajectory',
                    'impact': 'Weak operational reliability scores impact active contract completions.',
                    'action': 'Apply spelling Normalization suggestions and complete pending audits.'
                })
                
            if not recommendations:
                recommendations.append({
                    'threat': 'Optimal Data Health',
                    'impact': 'Risk trajectory remains low across all registry quadrants.',
                    'action': 'Maintain quarterly document audits.'
                })

            return {
                'success': True,
                'vendor_id': vendor_id,
                'timeline': months_ahead,
                'forecasts': {
                    'trust': trust_forecast,
                    'risk': risk_forecast,
                    'quality': quality_forecast,
                    'growth': growth_projection
                },
                'probabilities': {
                    'compliance_failure': round(compliance_fail_prob, 1),
                    'fraud_probability': round(fraud_prob, 1),
                    'duplicate_probability': round(dup_prob, 1),
                    'confidence_score': 92.5 if vendor_id else 85.0
                },
                'expiring_documents': expiring_docs,
                'recommendations': recommendations
            }
        except Exception as e:
            logging.error(f"Error compiling predictive metrics: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def generate_predictive_alerts(vendor_id: int) -> list:
        """Runs predictive scans to identify expiring documents, compliance failures, trust decreases, or high-risk candidates."""
        try:
            vendor = Vendor.query.get(vendor_id)
            if not vendor:
                return []

            alerts = []
            now = datetime.utcnow()

            # 1. Expiring documents (next 90 days)
            limit_dt = now + timedelta(days=90)
            expiring_docs = VendorDocument.query.filter(
                VendorDocument.vendor_id == vendor_id,
                VendorDocument.expiry_date > now,
                VendorDocument.expiry_date < limit_dt,
                VendorDocument.is_deleted == False
            ).all()

            for d in expiring_docs:
                days_left = (d.expiry_date - now).days
                threat = "High" if days_left <= 30 else "Medium"
                alert_msg = f"Document '{d.name}' of type '{d.document_type}' is set to expire on {d.expiry_date.strftime('%Y-%m-%d')} ({days_left} days remaining)."
                
                alerts.append({
                    'vendor_id': vendor_id,
                    'vendor_name': vendor.name,
                    'alert_type': 'Expiring Documents',
                    'threat_level': threat,
                    'confidence': 98.0,
                    'explanation': alert_msg,
                    'projected_date': d.expiry_date.strftime('%Y-%m-%d'),
                    'business_impact': "Will trigger missing document compliance penalty (-15 points) and drop trust scores."
                })

            # Fetch compliance status
            comp = VendorComplianceStatus.query.filter_by(vendor_id=vendor_id).first()
            current_compliance = comp.compliance_score if comp else 85.0
            
            # Fetch trust score
            current_trust = vendor.trust_score

            # 2. Compliance failures (Impending doc expiry in 30 days or current compliance < 80)
            has_urgent_expiry = any((d.expiry_date - now).days <= 30 for d in expiring_docs)
            if has_urgent_expiry or current_compliance < 80.0:
                threat = "Critical" if (current_compliance < 70.0 or (has_urgent_expiry and current_compliance < 80.0)) else "High"
                explanation = f"impending compliance credentials expiration or current low compliance rating ({current_compliance:.1f}%) projects a profile audit failure."
                alerts.append({
                    'vendor_id': vendor_id,
                    'vendor_name': vendor.name,
                    'alert_type': 'Compliance Failure Risk',
                    'threat_level': threat,
                    'confidence': 90.0 if has_urgent_expiry else 75.0,
                    'explanation': f"Predicted compliance failure: {explanation}",
                    'projected_date': (now + timedelta(days=30)).strftime('%Y-%m-%d'),
                    'business_impact': "Suspends automated purchase order validations and flags registry compliance warnings."
                })

            # Fetch history to compute slope
            history = VendorTrustHistory.query.filter_by(vendor_id=vendor_id)\
                                               .order_by(VendorTrustHistory.calculated_at.desc())\
                                               .limit(5).all()
            if len(history) >= 2:
                diff_trust = history[0].trust_score - history[-1].trust_score
                slope_trust = diff_trust / len(history)
            else:
                slope_trust = 0.0

            # 3. Trust decrease
            # If slope is negative or expiring documents are detected
            if slope_trust < 0.0 or len(expiring_docs) > 0:
                threat = "High" if (slope_trust < -2.0 or current_trust < 60.0) else "Medium"
                explanation = f"Negative trust index slope ({slope_trust:.2f}/evaluation) or impending doc expiries project score declines in the coming weeks."
                alerts.append({
                    'vendor_id': vendor_id,
                    'vendor_name': vendor.name,
                    'alert_type': 'Trust Decrease Projection',
                    'threat_level': threat,
                    'confidence': 85.0 if slope_trust < 0.0 else 65.0,
                    'explanation': explanation,
                    'projected_date': (now + timedelta(days=60)).strftime('%Y-%m-%d'),
                    'business_impact': "May downgrade vendor rating tier and result in procurement limitations."
                })

            # 4. High risk vendors (trust score < 50 or fraud score > 50)
            fraud = FraudCheck.query.filter_by(vendor_id=vendor_id).first()
            fraud_score = fraud.fraud_score if fraud else 10.0
            
            if current_trust < 60.0 or fraud_score > 40.0:
                threat = "Critical" if (current_trust < 50.0 or fraud_score > 70.0) else "High"
                explanation = f"Vendor profile exhibits low baseline trust score ({current_trust:.1f}) and high fraud risk probability ({fraud_score:.1f}%)."
                alerts.append({
                    'vendor_id': vendor_id,
                    'vendor_name': vendor.name,
                    'alert_type': 'High Risk Threat',
                    'threat_level': threat,
                    'confidence': 92.0 if current_trust < 50.0 else 80.0,
                    'explanation': explanation,
                    'projected_date': None,
                    'business_impact': "Critical operational threat category. Capping order limits and placing contracts on hold."
                })

            # Integrate Notifications: for any alerts with High or Critical threat level
            from src.domain.services.notification_service import NotificationService
            for a in alerts:
                if a['threat_level'] in ['High', 'Critical']:
                    NotificationService.create_notification(
                        vendor_id=vendor_id,
                        title=f"Predictive Alert: {a['alert_type']}",
                        message=f"{a['explanation']} Confidence: {a['confidence']:.1f}%.",
                        priority="High" if a['threat_level'] == "Critical" else "Medium",
                        category="Compliance" if "Compliance" in a['alert_type'] else "Trust",
                        target_roles=["Admin", "Auditor", "Manager"]
                    )

            return alerts
        except Exception as e:
            logging.error(f"Error generating predictive alerts: {str(e)}")
            return []
