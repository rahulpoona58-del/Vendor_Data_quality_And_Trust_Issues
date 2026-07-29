import pandas as pd
import os
from src.infrastructure.database.models import User, Vendor, ScoringRule, db
from src.infrastructure.security.cryptography import hash_password
import logging

def seed_database(csv_path: str):
    """Auto-seeds user roles, vendor profiles, and default trust scoring weights if empty."""
    try:
        # 1. Seed Default Users
        if User.query.count() == 0:
            default_users = [
                ('admin@system.local', 'admin123', 'Admin'),
                ('steward@system.local', 'steward123', 'Data Steward'),
                ('auditor@system.local', 'auditor123', 'Auditor'),
                ('manager@system.local', 'manager123', 'Manager'),
                ('viewer@system.local', 'viewer123', 'Viewer')
            ]
            for email, password, role in default_users:
                hashed = hash_password(password)
                user = User(email=email, password_hash=hashed, role=role)
                db.session.add(user)
            db.session.commit()
            logging.info("Default roles and users seeded successfully!")
            
        # 2. Seed Vendors from CSV
        if Vendor.query.count() == 0:
            if not os.path.exists(csv_path):
                logging.warning(f"CSV database file not found at {csv_path}. Skipping vendor seed.")
                return
                
            logging.info(f"Seeding vendors from CSV: {csv_path}")
            df = pd.read_csv(csv_path)
            
            from trust_score import calculate_trust_score, get_trust_level
            
            for _, row in df.iterrows():
                vid = int(row['vendor_id'])
                t_score = float(calculate_trust_score(row))
                t_level = get_trust_level(t_score)
                q_rating = float(row.get('quality_rating', 4.0))
                
                vendor = Vendor(
                    id=vid,
                    name=str(row['vendor_name']),
                    category='IT & Services' if vid % 3 == 0 else ('Logistics' if vid % 2 == 0 else 'Consulting'),
                    status='Active' if vid % 10 != 0 else 'Inactive',
                    trust_score=round(t_score, 1),
                    trust_level=t_level,
                    quality_rating=q_rating,
                    address=f"Delhi Sector {vid % 20 + 1}, New Delhi" if vid % 3 == 0 else (f"Mumbai Hub {vid % 15 + 1}, Maharashtra" if vid % 2 == 0 else f"Bangalore Tech Park {vid % 10 + 1}, Karnataka"),
                    phone=f"+91 98765 {vid:05d}",
                    email=f"contact@{(str(row['vendor_name'])).lower().replace(' ', '').replace(',', '')}.com",
                    gst_number=f"07AAAC{vid:05d}A1Z1",
                    pan_number=f"AAAC{vid:05d}A",
                    bank_account=f"918273645{vid:03d}"
                )
                db.session.add(vendor)
            db.session.commit()
            logging.info(f"Seeded {len(df)} vendors into the database successfully!")
            
        # 3. Seed Default Trust & Risk Scoring Rules
        if ScoringRule.query.count() == 0:
            default_rules = [
                ('delivery_weight', 0.4, 'Delivery', 'Multiplier for on-time delivery percentage (e.g. 0.4 * Delivery%)'),
                ('quality_weight', 6.0, 'Quality', 'Multiplier for 1-5 quality rating scale (e.g. 6.0 * QualityRating)'),
                ('defect_penalty_rate', 2.0, 'Quality', 'Points deducted per 1% of defect rate'),
                ('response_penalty_rate', 0.5, 'Delivery', 'Points deducted per 1 hour of response time delay'),
                ('gst_verified_bonus', 15.0, 'Compliance', 'Bonus points awarded for verified GST certification'),
                ('pan_verified_bonus', 10.0, 'Compliance', 'Bonus points awarded for verified PAN card'),
                ('missing_document_penalty', 15.0, 'Compliance', 'Penalty deducted if required compliance files are missing'),
                ('duplicate_warning_penalty', 20.0, 'Security', 'Penalty deducted if high duplicate match is flagged')
            ]
            for key, val, cat, desc in default_rules:
                rule = ScoringRule(rule_key=key, rule_value=val, category=cat, description=desc, is_active=True)
                db.session.add(rule)
            db.session.commit()
            logging.info("Default scoring rules seeded successfully!")
            
        # 4. Seed Blacklisted Vendors
        from src.infrastructure.database.models import BlacklistedVendor
        if BlacklistedVendor.query.count() == 0:
            blacklisted = [
                BlacklistedVendor(name="Shell Corp India", gst_number="27SHELL1234A1Z1", pan_number="SHELL1234A", reason="Identified as shell corporation by regulatory authority"),
                BlacklistedVendor(name="Fraudulent Supplier Ltd", gst_number="27FRAUD9999B1Z2", pan_number="FRAUD9999B", reason="Blacklisted due to duplicate bank account fraud attempts")
            ]
            for b in blacklisted:
                db.session.add(b)
            db.session.commit()
            logging.info("Default blacklisted vendors seeded successfully!")
            
        # 5. Seed Configurable Business Rules
        from src.infrastructure.database.models import BusinessRule
        if BusinessRule.query.count() == 0:
            rules = [
                BusinessRule(
                    name="Reject Vendor on Missing Tax IDs",
                    description="Automatically sets vendor status to Rejected if both GST and PAN compliance certificates are missing.",
                    rule_group="Compliance",
                    priority=1,
                    version=1,
                    is_enabled=True,
                    conditions_json={
                        "operator": "AND",
                        "rules": [
                            {"fact": "gst_missing", "comparator": "eq", "value": True},
                            {"fact": "pan_missing", "comparator": "eq", "value": True}
                        ]
                    },
                    actions_json={
                        "action": "reject_vendor",
                        "reason": "Mandatory tax proofs (GST & PAN) missing from active registrations."
                    }
                ),
                BusinessRule(
                    name="Elevated Risk on Active Fraud Flags",
                    description="Flags critical priority alerts if fraud check is actively warning overlap anomalies.",
                    rule_group="Fraud",
                    priority=2,
                    version=1,
                    is_enabled=True,
                    conditions_json={
                        "fact": "has_fraud_alert",
                        "comparator": "eq",
                        "value": True
                    },
                    actions_json={
                        "action": "flag_critical",
                        "reason": "Active fraud indicators detected during scheduled network integrity scans."
                    }
                )
            ]
            for r in rules:
                db.session.add(r)
            db.session.commit()
            logging.info("Default business rules seeded successfully!")
            
            # 6. Seed Compliance Profiles for all vendors
            from src.infrastructure.database.models import VendorComplianceStatus
            if VendorComplianceStatus.query.count() == 0:
                vendors_list = Vendor.query.all()
                for v in vendors_list:
                    comp = VendorComplianceStatus(
                        vendor_id=v.id,
                        compliance_score=85.0 - (v.id % 20),
                        approval_status='Approved' if (v.id % 10 != 0) else 'Pending Approval',
                        audited_by='System-Seeder'
                    )
                    db.session.add(comp)
                db.session.commit()
                logging.info("Default compliance status profiles seeded successfully!")
            
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error seeding database: {str(e)}")
