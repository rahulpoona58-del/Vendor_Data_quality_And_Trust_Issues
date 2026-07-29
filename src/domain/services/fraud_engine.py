from datetime import datetime
from src.infrastructure.database.models import Vendor, VendorDocument, OcrResult, FraudCheck, BlacklistedVendor, db
import logging

class FraudEngine:
    """Enterprise AI Fraud Detection Engine checking duplicates, blacklists, shell indicators, and SLA anomalies."""
    
    @staticmethod
    def execute_scan(vendor_id: int) -> dict:
        """Runs fraud analysis routines across database records, matching duplicates and blacklists."""
        try:
            vendor = Vendor.query.get(vendor_id)
            if not vendor:
                return {'success': False, 'message': 'Vendor not found'}
                
            # Fetch OCR results for the current vendor
            current_ocr = OcrResult.query.filter_by(vendor_id=vendor.id).first()
            current_data = current_ocr.corrected_data or current_ocr.extracted_data if current_ocr else {}
            
            # Fetch all other vendors and their OCR details
            other_ocrs = OcrResult.query.filter(OcrResult.vendor_id != vendor.id).all()
            
            flags = []
            evidence = {}
            fraud_score = 0.0
            
            # 1. Blacklist Check
            # Check company name, GST, and PAN
            gst = current_data.get('gst_number', '').strip()
            pan = current_data.get('pan_number', '').strip()
            
            blacklist_match = BlacklistedVendor.query.filter(
                (BlacklistedVendor.name.ilike(f"%{vendor.name}%")) |
                ((BlacklistedVendor.gst_number == gst) & (gst != '')) |
                ((BlacklistedVendor.pan_number == pan) & (pan != ''))
            ).first()
            
            if blacklist_match:
                flags.append("Official Blacklist Registry Match")
                evidence["blacklist"] = {
                    "matched_entity": blacklist_match.name,
                    "reason": blacklist_match.reason,
                    "added_at": blacklist_match.added_at.isoformat()
                }
                fraud_score = max(fraud_score, 100.0)
                
            # 2. Duplicate Tax Indicators (GST / PAN)
            gst_duplicates = []
            pan_duplicates = []
            for other in other_ocrs:
                other_data = other.corrected_data or other.extracted_data
                other_gst = other_data.get('gst_number', '').strip()
                other_pan = other_data.get('pan_number', '').strip()
                
                if gst and other_gst == gst:
                    gst_duplicates.append(other.vendor_id)
                if pan and other_pan == pan:
                    pan_duplicates.append(other.vendor_id)
                    
            if gst_duplicates:
                flags.append("Duplicate GST Number")
                evidence["duplicate_gst"] = {"matching_vendors": gst_duplicates, "gst_number": gst}
                fraud_score = max(fraud_score, 85.0)
            if pan_duplicates:
                flags.append("Duplicate PAN Number")
                evidence["duplicate_pan"] = {"matching_vendors": pan_duplicates, "pan_number": pan}
                fraud_score = max(fraud_score, 80.0)
                
            # 3. Shared Banking Parameters (IFSC + Account)
            bank_acc = current_data.get('bank_account', '').strip()
            ifsc = current_data.get('ifsc', '').strip()
            bank_duplicates = []
            
            for other in other_ocrs:
                other_data = other.corrected_data or other.extracted_data
                other_acc = other_data.get('bank_account', '').strip()
                other_ifsc = other_data.get('ifsc', '').strip()
                
                if bank_acc and other_acc == bank_acc:
                    bank_duplicates.append({
                        "vendor_id": other.vendor_id,
                        "ifsc_match": ifsc and other_ifsc == ifsc
                    })
                    
            if bank_duplicates:
                exact_bank_matches = [b['vendor_id'] for b in bank_duplicates if b['ifsc_match']]
                if exact_bank_matches:
                    flags.append("Shared Bank Account & IFSC combination")
                    evidence["shared_bank_account"] = {"matching_vendors": exact_bank_matches}
                    fraud_score = max(fraud_score, 90.0)
                else:
                    flags.append("Shared Bank Account Number")
                    evidence["shared_bank_account_partial"] = {"matching_vendors": [b['vendor_id'] for b in bank_duplicates]}
                    fraud_score = max(fraud_score, 75.0)
                    
            # 4. Shared Contacts (Phone / Email)
            phone = current_data.get('phone', '').strip()
            email = current_data.get('email', '').strip()
            phone_duplicates = []
            email_duplicates = []
            
            for other in other_ocrs:
                other_data = other.corrected_data or other.extracted_data
                other_phone = other_data.get('phone', '').strip()
                other_email = other_data.get('email', '').strip()
                
                if phone and other_phone == phone:
                    phone_duplicates.append(other.vendor_id)
                if email and other_email == email:
                    email_duplicates.append(other.vendor_id)
                    
            if phone_duplicates:
                flags.append("Shared Phone Number")
                evidence["shared_phone"] = {"matching_vendors": phone_duplicates, "phone": phone}
                fraud_score = max(fraud_score, 50.0)
            if email_duplicates:
                flags.append("Shared Email Address")
                evidence["shared_email"] = {"matching_vendors": email_duplicates, "email": email}
                fraud_score = max(fraud_score, 45.0)
                
            # 5. Shared Address
            address = current_data.get('address', '').strip()
            address_duplicates = []
            for other in other_ocrs:
                other_data = other.corrected_data or other.extracted_data
                other_addr = other_data.get('address', '').strip()
                if address and other_addr == address:
                    address_duplicates.append(other.vendor_id)
                    
            if address_duplicates:
                flags.append("Multiple Vendors Sharing Same Address")
                evidence["shared_address"] = {"matching_vendors": address_duplicates}
                # If shared with more than 2 other vendors, increase score (shell indicator)
                fraud_score = max(fraud_score, 60.0 if len(address_duplicates) > 2 else 40.0)
                
            # 6. Expired Compliance Documents
            docs = VendorDocument.query.filter_by(vendor_id=vendor.id, is_deleted=False).all()
            expired_docs = []
            for d in docs:
                if d.expiry_date and d.expiry_date < datetime.utcnow():
                    expired_docs.append(d.name)
            if expired_docs:
                flags.append("Expired Compliance Documents")
                evidence["expired_documents"] = {"expired_files": expired_docs}
                fraud_score = max(fraud_score, 30.0)
                
            # 7. Shell Company Indicators (High risk flags: missing documents + no bank details + matching address)
            if len(docs) == 0 and not bank_acc:
                flags.append("Shell Company Indicators")
                evidence["shell_indicators"] = ["Zero compliance document logs", "Missing verified bank account"]
                fraud_score = max(fraud_score, 65.0)

            # 8. Graph-Based Fraud Intelligence
            graph_patterns = FraudEngine.detect_graph_fraud_intelligence(vendor.id)
            if graph_patterns:
                evidence["graph_intelligence"] = graph_patterns
                for pat in graph_patterns:
                    flags.append(f"Graph: {pat['pattern']}")
                    # Elevate scores based on graph threat patterns
                    if pat['severity'] == 'Critical':
                        fraud_score = max(fraud_score, 95.0)
                    elif pat['severity'] == 'High':
                        fraud_score = max(fraud_score, 85.0)
                
            # Final risk level mapping
            risk_level = 'Low'
            if fraud_score >= 70:
                risk_level = 'High'
            elif fraud_score >= 35:
                risk_level = 'Medium'
                
            # Formulate action and root causes
            if not flags:
                root_cause = "No fraud indicators detected during system scan."
                recommended_action = "Maintain standard review schedules."
            else:
                root_cause = "Discovered: " + ", ".join(flags)
                if risk_level == 'High':
                    recommended_action = "IMMEDIATE ACTION REQUIRED: Suspend payment cycles and trigger manual director identification audits."
                elif risk_level == 'Medium':
                    recommended_action = "WARNING: Request compliance updates and verify bank registration codes."
                else:
                    recommended_action = "Review flagged file details."
                    
            # Check if alert already exists
            alert = FraudCheck.query.filter_by(vendor_id=vendor.id).first()
            if not alert:
                alert = FraudCheck(
                    vendor_id=vendor.id,
                    fraud_score=fraud_score,
                    risk_level=risk_level,
                    confidence=0.98 if blacklist_match or gst_duplicates else 0.85,
                    root_cause=root_cause,
                    recommended_action=recommended_action,
                    supporting_evidence=evidence,
                    status='Alert' if flags else 'Cleared'
                )
                db.session.add(alert)
            else:
                alert.fraud_score = fraud_score
                alert.risk_level = risk_level
                alert.confidence = 0.98 if blacklist_match or gst_duplicates else 0.85
                alert.root_cause = root_cause
                alert.recommended_action = recommended_action
                alert.supporting_evidence = evidence
                # Only reset status if it was not manually resolved
                if alert.status == 'Cleared' and flags:
                    alert.status = 'Alert'
                    
            # Evaluate custom business rules for Fraud group
            from src.domain.services.business_rules_engine import BusinessRulesEngine
            rule_actions = BusinessRulesEngine.evaluate_rules(vendor.id, 'Fraud')
            for action_item in rule_actions:
                action = action_item.get('action', {})
                act_name = action.get('action')
                if act_name == 'flag_critical':
                    alert.risk_level = 'Critical'
                    alert.fraud_score = max(alert.fraud_score, 90.0)
                    alert.status = 'Alert'
                    
            db.session.commit()
            
            # Log timeline activity
            if flags:
                from src.domain.services.timeline_service import TimelineService
                TimelineService.log_activity(
                    vendor_id=vendor.id,
                    activity_type='Fraud Alert',
                    description=f"Fraud Scan Alert triggered: {root_cause}"
                )
                
                # Trigger System Notifications
                from src.domain.services.notification_service import NotificationService
                
                if gst_duplicates:
                    NotificationService.create_notification(
                        vendor_id=vendor.id,
                        title="Duplicate GST Registered",
                        message=f"Vendor '{vendor.name}' shares the same GST ({gst}) with Vendor IDs: {', '.join(map(str, gst_duplicates))}.",
                        priority="Critical",
                        category="Fraud",
                        target_roles=["Admin", "Data Steward"]
                    )
                if pan_duplicates:
                    NotificationService.create_notification(
                        vendor_id=vendor.id,
                        title="Duplicate PAN Registered",
                        message=f"Vendor '{vendor.name}' shares the same PAN ({pan}) with Vendor IDs: {', '.join(map(str, pan_duplicates))}.",
                        priority="High",
                        category="Fraud",
                        target_roles=["Admin", "Data Steward"]
                    )
                if bank_duplicates:
                    NotificationService.create_notification(
                        vendor_id=vendor.id,
                        title="Shared Bank Account Overlap",
                        message=f"Vendor '{vendor.name}' shares bank account credentials with Vendor IDs: {', '.join(map(str, [b['vendor_id'] for b in bank_duplicates]))}.",
                        priority="Critical",
                        category="Fraud",
                        target_roles=["Admin", "Auditor"]
                    )
                if fraud_score >= 70.0:
                    NotificationService.create_notification(
                        vendor_id=vendor.id,
                        title="High-Risk Fraud Flagged",
                        message=f"Vendor '{vendor.name}' overall fraud score is Critical ({fraud_score}/100).",
                        priority="Critical",
                        category="Fraud",
                        target_roles=["Admin", "Auditor"]
                    )
                
            logging.info(f"Fraud check completed: vendor_id={vendor.id} score={fraud_score} status={alert.status}")
            return {'success': True, 'fraud_check': alert.to_dict()}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Fraud scan failure: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def resolve_alert(alert_id: int, status: str, reviewer: str) -> dict:
        """Allows admins to clear or audit flags manually."""
        try:
            alert = FraudCheck.query.get(alert_id)
            if not alert:
                return {'success': False, 'message': 'Alert record not found'}
                
            if status not in {'Alert', 'Investigating', 'Cleared'}:
                return {'success': False, 'message': 'Invalid status option'}
                
            old_status = alert.status
            alert.status = status
            db.session.commit()
            
            # Log timeline activity
            from src.domain.services.timeline_service import TimelineService
            TimelineService.log_activity(
                vendor_id=alert.vendor_id,
                activity_type='Admin Actions',
                description=f"Fraud Alert workflow status updated to '{status}' by {reviewer}.",
                performed_by=reviewer
            )
            
            # System Audit Log
            from src.domain.services.audit_service import AuditService
            AuditService.log_audit(
                performed_by=reviewer,
                ip_address='127.0.0.1',
                action_type="Resolve Fraud Alert",
                module_name="Fraud",
                old_value={"status": old_status},
                new_value={"status": status},
                reason="Auditor manual security flag override",
                vendor_id=alert.vendor_id
            )
            
            logging.info(f"Fraud alert id={alert.id} status updated to {status} by reviewer {reviewer}")
            return {'success': True, 'fraud_check': alert.to_dict()}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error resolving fraud alert {alert_id}: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def detect_graph_fraud_intelligence(vendor_id: int) -> list:
        """Analyzes graph nodes and edges to extract complex fraud ring patterns."""
        from src.domain.services.knowledge_graph import KnowledgeGraphService
        
        # Get graph data localized to this vendor
        graph_data = KnowledgeGraphService.get_graph_data(vendor_id=vendor_id)
        if not graph_data.get('success'):
            return []
            
        elements = graph_data.get('elements', {})
        nodes = elements.get('nodes', [])
        edges = elements.get('edges', [])
        
        patterns = []
        
        # Helper: find all neighbors of a node
        def get_connected_vendors(node_id):
            connected = []
            for e in edges:
                if e['data']['target'] == node_id and e['data']['source'].startswith('v-'):
                    connected.append(e['data']['source'])
                elif e['data']['source'] == node_id and e['data']['target'].startswith('v-'):
                    connected.append(e['data']['target'])
            return list(set(connected))

        # 1. Scan for Shared Bank Account Networks
        bank_nodes = [n for n in nodes if n['data']['type'] == 'bank']
        for b in bank_nodes:
            v_links = get_connected_vendors(b['data']['id'])
            if len(v_links) > 1:
                v_names = [next((n['data']['label'] for n in nodes if n['data']['id'] == vid), vid) for vid in v_links]
                patterns.append({
                    'pattern': 'Shared Bank-Account Network',
                    'affected_vendors': [{'id': int(vid.split('-')[1]), 'name': name} for vid, name in zip(v_links, v_names)],
                    'severity': 'Critical',
                    'confidence': 99,
                    'evidence': f"Shared Bank Account Node ({b['data']['label']}) linked to {len(v_links)} distinct vendors.",
                    'relationship_path': [v_links[0], b['data']['id'], v_links[1]],
                    'explanation': "The model detected that multiple vendors receive payouts to the exact same bank credentials. This is a strong indicator of a single entity operating dummy profiles.",
                    'recommendation': "Suspend payment disbursement immediately and perform KYC verification checks on bank accounts."
                })

        # 2. Scan for Suspicious Identical Addresses (Shell Clusters)
        addr_nodes = [n for n in nodes if n['data']['type'] == 'address']
        for a in addr_nodes:
            v_links = get_connected_vendors(a['data']['id'])
            if len(v_links) > 1:
                v_names = [next((n['data']['label'] for n in nodes if n['data']['id'] == vid), vid) for vid in v_links]
                patterns.append({
                    'pattern': 'Multiple Companies at Identical Addresses',
                    'affected_vendors': [{'id': int(vid.split('-')[1]), 'name': name} for vid, name in zip(v_links, v_names)],
                    'severity': 'High',
                    'confidence': 92,
                    'evidence': f"Shared Address Node ({a['data']['label']}) linked to {len(v_links)} distinct vendors.",
                    'relationship_path': [v_links[0], a['data']['id'], v_links[1]],
                    'explanation': "Multiple independent vendors are registered under the exact same address hash. This pattern is commonly associated with shell corporate clusters.",
                    'recommendation': "Perform physical site verification or request utility invoice utility bills to confirm physical operations."
                })

        # 3. Scan for Shared Ownership (Directors)
        dir_nodes = [n for n in nodes if n['data']['type'] == 'director']
        for d in dir_nodes:
            v_links = get_connected_vendors(d['data']['id'])
            if len(v_links) > 1:
                v_names = [next((n['data']['label'] for n in nodes if n['data']['id'] == vid), vid) for vid in v_links]
                patterns.append({
                    'pattern': 'Shared Ownership / Director Cluster',
                    'affected_vendors': [{'id': int(vid.split('-')[1]), 'name': name} for vid, name in zip(v_links, v_names)],
                    'severity': 'High',
                    'confidence': 95,
                    'evidence': f"Shared Board Director ({d['data']['label']}) manages {len(v_links)} distinct vendors.",
                    'relationship_path': [v_links[0], d['data']['id'], v_links[1]],
                    'explanation': "The director holds operational signing authority across multiple separate vendors. This raises potential conflict of interest concerns.",
                    'recommendation': "Validate ultimate beneficial ownership (UBO) filings and inspect pricing agreements between entities."
                })

        # 4. Scan for Vendor Rings & Circular sharing
        # If Vendor A shares Director X with Vendor B, and Vendor A shares Bank Y with Vendor B -> Circular asset sharing ring!
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                n1 = nodes[i]['data']
                n2 = nodes[j]['data']
                if n1['type'] == 'vendor' and n2['type'] == 'vendor':
                    v1_id = n1['id']
                    v2_id = n2['id']
                    # Find common neighbors
                    v1_neighbors = set()
                    v2_neighbors = set()
                    for e in edges:
                        if e['data']['source'] == v1_id: v1_neighbors.add(e['data']['target'])
                        if e['data']['target'] == v1_id: v1_neighbors.add(e['data']['source'])
                        if e['data']['source'] == v2_id: v2_neighbors.add(e['data']['target'])
                        if e['data']['target'] == v2_id: v2_neighbors.add(e['data']['source'])
                    
                    commons = v1_neighbors.intersection(v2_neighbors)
                    # If they share a director AND a bank or address -> Circular Ring!
                    common_types = {next((n['data']['type'] for n in nodes if n['data']['id'] == cid), '') for cid in commons}
                    if 'director' in common_types and ('bank' in common_types or 'address' in common_types):
                        patterns.append({
                            'pattern': 'Circular Asset & Ownership Ring',
                            'affected_vendors': [
                                {'id': int(v1_id.split('-')[1]), 'name': n1['label']},
                                {'id': int(v2_id.split('-')[1]), 'name': n2['label']}
                            ],
                            'severity': 'Critical',
                            'confidence': 98,
                            'evidence': f"Vendors share multiple entity vertices: {list(commons)}.",
                            'relationship_path': [v1_id, list(commons)[0], v2_id, list(commons)[1], v1_id],
                            'explanation': "The network graph detected a circular connection loop between these entities sharing both management directors and payment bank channels.",
                            'recommendation': "Halt bidding authorization and initiate audit checks on corporate registers."
                        })
                        
        return patterns
