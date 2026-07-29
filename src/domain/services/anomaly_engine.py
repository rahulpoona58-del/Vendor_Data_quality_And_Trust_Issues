import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import IsolationForest
from src.infrastructure.database.models import Vendor, VendorDocument, SystemAuditLog, VendorAnomaly, db
from src.domain.services.knowledge_graph import KnowledgeGraphService
import logging

class AnomalyDetectionEngine:
    """Hybrid Anomaly Detection Engine combining Isolation Forest, Robust MAD Z-scores, and Category Peer-group analysis."""
    
    @staticmethod
    def execute_scan() -> dict:
        """Runs the hybrid anomaly detection pipeline across the entire vendor cohort, populating the anomalies table."""
        try:
            # 1. Retrieve all vendors
            vendors = Vendor.query.all()
            if not vendors:
                return {'success': False, 'message': 'No vendor profiles found to scan.'}
                
            # Retrieve global relation graph stats once to avoid N database queries in loop
            global_graph = KnowledgeGraphService.get_graph_data()
            global_elements = global_graph.get('elements', {}) if global_graph.get('success') else {}
            global_edges = global_elements.get('edges', [])
            
            # Map each vendor ID to its shared nodes count in memory
            vendor_shares = {}
            for e in global_edges:
                src = e['data']['source']
                tgt = e['data']['target']
                if src.startswith('v-'):
                    vendor_shares[src] = vendor_shares.get(src, 0) + 1
                if tgt.startswith('v-'):
                    vendor_shares[tgt] = vendor_shares.get(tgt, 0) + 1
                
            # Compile feature vectors for all vendors
            data_list = []
            for v in vendors:
                # Count documents
                doc_count = len(v.documents.all()) if hasattr(v.documents, 'all') else len(v.documents or [])
                
                # Count update logs
                update_count = len(v.audit_logs.all()) if hasattr(v, 'audit_logs') and hasattr(v.audit_logs, 'all') else (len(v.audit_logs) if hasattr(v, 'audit_logs') and v.audit_logs else 0)
                
                # Retrieve relation graph stats from memory map
                shared_count = vendor_shares.get(f'v-{v.id}', 0)
                    
                data_list.append({
                    'id': v.id,
                    'name': v.name,
                    'category': v.category or 'General',
                    'trust_score': float(v.trust_score),
                    'quality_rating': float(v.quality_rating),
                    'risk_score': 100.0 - float(v.trust_score),
                    'doc_count': float(doc_count),
                    'update_count': float(update_count),
                    'shared_count': float(shared_count)
                })
                
            df = pd.DataFrame(data_list)
            
            # 2. Train Isolation Forest (ML Multi-dimensional Outliers)
            feature_cols = ['trust_score', 'quality_rating', 'risk_score', 'doc_count', 'update_count', 'shared_count']
            X = df[feature_cols].values
            
            # Use small contamination factor (e.g. 5%)
            clf = IsolationForest(contamination=0.05, random_state=42)
            clf.fit(X)
            
            raw_scores = clf.decision_function(X) # Anomalous are negative values
            predictions = clf.predict(X)          # -1 is anomalous, 1 is normal
            
            # Normalize anomaly score from 0 to 100
            # Decision function values are typically between -0.5 and 0.5.
            df['ml_score'] = np.clip((0.5 - raw_scores) * 80.0, 0, 100)
            df['is_ml_anomaly'] = predictions == -1
            
            # 3. Robust Statistical Median Absolute Deviation (MAD) Outliers
            # Standard MAD formulation: MAD = median(|x - median(x)|)
            # Modified Z-score = 0.6745 * (x - median(x)) / MAD
            mad_scores = {}
            for col in ['trust_score', 'quality_rating', 'doc_count', 'update_count']:
                med = df[col].median()
                mad = np.median(np.abs(df[col] - med))
                if mad == 0:
                    mad = df[col].std() or 1.0 # fallback
                df[f'{col}_mod_z'] = 0.6745 * (df[col] - med) / mad
                mad_scores[col] = {'median': med, 'mad': mad}
                
            # 4. Category Peer-group Deviation
            # Group by category, check if values deviate by > 2.5 std devs from the category mean
            peer_stats = {}
            for name, group in df.groupby('category'):
                peer_stats[name] = {
                    'trust_mean': group['trust_score'].mean(),
                    'trust_std': group['trust_score'].std() or 1.0,
                    'quality_mean': group['quality_rating'].mean(),
                    'quality_std': group['quality_rating'].std() or 1.0
                }
                
            # Clear old active anomalies to avoid duplicates
            VendorAnomaly.query.filter_by(status='Active').delete()
            
            anomalies_recorded = 0
            
            # 5. Evaluate and save anomalies
            for index, row in df.iterrows():
                vid = int(row['id'])
                vendor = Vendor.query.get(vid)
                
                # Rule-based flags checks
                rule_flags = []
                # E.g. GST matches duplicates or zero documents
                if row['doc_count'] == 0:
                    rule_flags.append("Missing Critical Compliance Documents")
                if row['shared_count'] > 1:
                    rule_flags.append(f"High Shared Identity Attributes count: {int(row['shared_count'])}")
                if float(vendor.trust_score) < 35.0:
                    rule_flags.append("Critical Trust Score Drop")
                    
                # Collect statistical MAD outliers
                stat_outliers = []
                for col in ['trust_score', 'quality_rating', 'doc_count', 'update_count']:
                    z = row[f'{col}_mod_z']
                    if np.abs(z) > 3.0:
                        direction = "high" if z > 0 else "low"
                        stat_outliers.append(f"{col.replace('_', ' ').capitalize()} modified Z-score is {z:.2f} ({direction} outlier)")
                        
                # Category peer deviations
                cat = row['category']
                stats = peer_stats.get(cat, {'trust_mean': 70.0, 'trust_std': 1.0, 'quality_mean': 4.0, 'quality_std': 1.0})
                trust_dev = (row['trust_score'] - stats['trust_mean']) / stats['trust_std']
                
                peer_devs = []
                if np.abs(trust_dev) > 2.5:
                    peer_devs.append(f"Trust Score deviates by {trust_dev:.2f} standard deviations from category '{cat}' average.")
                    
                # Determine overall anomaly flag:
                # If ML predicts anomaly OR has high Modified Z-scores OR has peer deviations OR has critical rules
                is_anomalous = row['is_ml_anomaly'] or len(stat_outliers) > 0 or len(peer_devs) > 0 or len(rule_flags) > 1
                
                if is_anomalous:
                    anomaly_score = float(row['ml_score'])
                    if len(rule_flags) > 0:
                        anomaly_score = max(anomaly_score, 65.0)
                    if len(stat_outliers) > 0:
                        anomaly_score = max(anomaly_score, 80.0)
                    if any("Critical" in r for r in rule_flags):
                        anomaly_score = max(anomaly_score, 90.0)
                        
                    severity = 'Low'
                    if anomaly_score >= 85:
                        severity = 'Critical'
                    elif anomaly_score >= 70:
                        severity = 'High'
                    elif anomaly_score >= 45:
                        severity = 'Medium'
                        
                    # Structure observed facts, rule findings, and ML predictions
                    observed_facts = {
                        'Trust Score': float(row['trust_score']),
                        'Quality Score': float(row['quality_rating']),
                        'Document Count': int(row['doc_count']),
                        'Update Frequency': int(row['update_count']),
                        'Shared Identifiers': int(row['shared_count']),
                        'Category Peer Average Trust': float(stats['trust_mean'])
                    }
                    
                    ml_predictions = {
                        'Isolation Forest Outlier Score': float(row['ml_score']),
                        'Multi-dimensional Anomaly Predicted': bool(row['is_ml_anomaly']),
                        'Modified Z-scores': {
                            'Trust Score Z': float(row['trust_score_mod_z']),
                            'Quality Rating Z': float(row['quality_rating_mod_z'])
                        }
                    }
                    
                    # Rationale pattern naming
                    pattern = "Multi-dimensional Behavior Outlier"
                    if len(stat_outliers) > 0 and len(rule_flags) > 0:
                        pattern = "High Risk Statistical Outlier"
                    elif len(peer_devs) > 0:
                        pattern = "Unusual Category Peer Deviation"
                    elif row['shared_count'] > 2:
                        pattern = "Shared Attributes Clustering"
                        
                    explanation = f"The vendor profile was flagged under pattern '{pattern}' because "
                    reasons_list = stat_outliers + peer_devs + rule_flags
                    explanation += "; ".join(reasons_list) + "."
                    
                    recommended_action = "Execute targeted KYC profile review."
                    if severity == 'Critical':
                        recommended_action = "IMMEDIATE RESOLUTION REQUIRED: Suspend transaction clearing and launch internal vendor ownership audit."
                    elif severity == 'High':
                        recommended_action = "WARNING: Request proof of compliance certificates and cross-reference bank identities."
                        
                    anomaly = VendorAnomaly(
                        vendor_id=vid,
                        anomaly_score=anomaly_score,
                        severity=severity,
                        pattern=pattern,
                        observed_facts=observed_facts,
                        rule_findings=rule_flags,
                        ml_predictions=ml_predictions,
                        explanation=explanation,
                        recommended_action=recommended_action,
                        status='Active'
                    )
                    db.session.add(anomaly)
                    anomalies_recorded += 1
                    
            db.session.commit()
            logging.info(f"Anomaly Detection scan complete. Recorded {anomalies_recorded} active anomaly alerts.")
            return {'success': True, 'anomalies_found': anomalies_recorded}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Anomaly detection execution failure: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def resolve_anomaly(anomaly_id: int, status: str, auditor: str) -> dict:
        """Updates status of a detected anomaly (e.g. Investigating, Resolved, False Positive)."""
        try:
            anomaly = VendorAnomaly.query.get(anomaly_id)
            if not anomaly:
                return {'success': False, 'message': 'Anomaly alert not found'}
                
            old_status = anomaly.status
            anomaly.status = status
            db.session.commit()
            
            # Record audit trace logs
            from src.domain.services.audit_service import AuditService
            AuditService.log_audit(
                performed_by=auditor,
                ip_address='127.0.0.1',
                action_type='Resolve Anomaly Alert',
                module_name='Anomaly Engine',
                old_value={'status': old_status},
                new_value={'status': status},
                reason='Auditor manual review state override.',
                vendor_id=anomaly.vendor_id
            )
            return {'success': True, 'anomaly': anomaly.to_dict()}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error resolving anomaly alert {anomaly_id}: {str(e)}")
            return {'success': False, 'message': str(e)}
