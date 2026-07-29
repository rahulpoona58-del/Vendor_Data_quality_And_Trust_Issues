import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src import create_app
from src.infrastructure.database.models import (
    db, User, Vendor, VendorDocument, FraudCheck, VendorAnomaly, SystemAuditLog
)
from werkzeug.security import generate_password_hash

DEMO_DB_PATH = BASE_DIR / 'instance' / 'vendors_demo.db'

def seed_demo_dataset():
    """Generates a realistic demo dataset with Vendors, Documents, Fraud Cases, Duplicates, and Anomalies."""
    print(f"--- Generating Demo Dataset [{DEMO_DB_PATH.name}] ---")

    # Force app database URI environment variable before create_app() is called
    DEMO_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    os.environ['DATABASE_URL'] = f"sqlite:///{DEMO_DB_PATH}"

    # Create app with isolated demo database
    app = create_app()

    with app.app_context():
        db.drop_all()
        db.create_all()

        print("[1/5] Seeding Users with 5 RBAC Roles...")
        users = [
            User(email="admin@demo.local", password_hash=generate_password_hash("Admin123!"), role="Admin"),
            User(email="manager@demo.local", password_hash=generate_password_hash("Manager123!"), role="Manager"),
            User(email="auditor@demo.local", password_hash=generate_password_hash("Auditor123!"), role="Auditor"),
            User(email="analyst@demo.local", password_hash=generate_password_hash("Analyst123!"), role="Analyst"),
            User(email="viewer@demo.local", password_hash=generate_password_hash("Viewer123!"), role="Viewer")
        ]
        db.session.add_all(users)
        db.session.commit()
        print("  -> Seeding 5 Users: PASSED")

        print("[2/5] Seeding Diverse Vendor Profiles & Duplicate Cases...")
        vendors_data = [
            # High Trust / Verified Vendors
            {
                "id": 101, "name": "Apex Cloud Solutions Pvt Ltd", "category": "IT & Cloud Services",
                "status": "Active", "trust_score": 94.5, "trust_level": "High Trust", "quality_rating": 4.9,
                "gstin": "07AAAC12345A1Z1", "pan_number": "AAAC12345A", "bank_account": "918273645001"
            },
            {
                "id": 102, "name": "Nexus Global Logistics", "category": "Logistics & Freight",
                "status": "Active", "trust_score": 88.0, "trust_level": "High Trust", "quality_rating": 4.6,
                "gstin": "27BBBCC67890B1Z2", "pan_number": "BBBCC6789B", "bank_account": "918273645002"
            },
            # Medium Trust / Compliance Issues
            {
                "id": 103, "name": "Vanguard Office Supplies", "category": "Facilities & Office",
                "status": "Active", "trust_score": 62.0, "trust_level": "Medium Trust", "quality_rating": 3.8,
                "gstin": "07CCCDD11223C1Z3", "pan_number": "CCCDD1122C", "bank_account": "918273645003"
            },
            # Duplicate Vendor (Identical GSTIN for Deduplication Demo)
            {
                "id": 104, "name": "Apex Cloud Systems (Duplicate Entity)", "category": "IT Services",
                "status": "Blocked", "trust_score": 25.0, "trust_level": "Critical Risk", "quality_rating": 2.1,
                "gstin": "07AAAC12345A1Z1", "pan_number": "AAAC12345A", "bank_account": "918273645001"
            },
            # High Risk / Fraud Case
            {
                "id": 105, "name": "Phantom Invoicing Enterprises", "category": "Consulting",
                "status": "Blocked", "trust_score": 15.0, "trust_level": "Critical Risk", "quality_rating": 1.2,
                "gstin": "99FAKEE99999F1Z9", "pan_number": "FAKEE9999F", "bank_account": "999000888777"
            }
        ]

        vendors = []
        for v in vendors_data:
            vendor = Vendor(
                id=v["id"],
                name=v["name"],
                category=v["category"],
                status=v["status"],
                trust_score=v["trust_score"],
                trust_level=v["trust_level"],
                quality_rating=v["quality_rating"],
                gst_number=v["gstin"],
                pan_number=v["pan_number"],
                bank_account=v["bank_account"],
                email=f"contact@{v['name'].lower().replace(' ', '').replace('(', '').replace(')', '')}.com",
                phone="+91 98765 00100"
            )
            vendors.append(vendor)
        db.session.add_all(vendors)
        db.session.commit()
        print("  -> Seeding 5 Vendors (including 1 Duplicate & 1 Fraud): PASSED")

        print("[3/5] Seeding Vendor Documents & Compliance Verification Records...")
        docs = [
            VendorDocument(
                vendor_id=101, name="GST_Certificate_Apex.pdf", document_type="GST Certificate",
                verification_status="Verified", file_hash=hashlib.sha256(b"apex_gst").hexdigest(),
                file_size=1024500, mime_type="application/pdf", storage_path="/uploads/docs/apex_gst.pdf",
                uploaded_by="admin@demo.local", expiry_date=datetime.now() + timedelta(days=365)
            ),
            VendorDocument(
                vendor_id=101, name="ISO_27001_Apex.pdf", document_type="ISO 27001 Certificate",
                verification_status="Verified", file_hash=hashlib.sha256(b"apex_iso").hexdigest(),
                file_size=2048100, mime_type="application/pdf", storage_path="/uploads/docs/apex_iso.pdf",
                uploaded_by="admin@demo.local", expiry_date=datetime.now() + timedelta(days=730)
            ),
            # Expired Document (Compliance Failure Demo)
            VendorDocument(
                vendor_id=103, name="GST_Certificate_Vanguard_Expired.pdf", document_type="GST Certificate",
                verification_status="Rejected", file_hash=hashlib.sha256(b"vanguard_exp").hexdigest(),
                file_size=850400, mime_type="application/pdf", storage_path="/uploads/docs/vanguard_gst.pdf",
                uploaded_by="manager@demo.local", expiry_date=datetime.now() - timedelta(days=90)
            )
        ]
        db.session.add_all(docs)
        db.session.commit()
        print("  -> Seeding Vendor Documents (including Verified & Expired): PASSED")

        print("[4/5] Seeding Fraud Check Audit Scans...")
        fraud_cases = [
            FraudCheck(
                vendor_id=101, fraud_score=5.0, risk_level="Low", confidence=0.98,
                root_cause="Routine Compliance Audit", recommended_action="No Action Needed",
                supporting_evidence=[], status="Cleared"
            ),
            FraudCheck(
                vendor_id=104, fraud_score=92.5, risk_level="High", confidence=0.99,
                root_cause="Duplicate GSTIN Registration", recommended_action="Block Transactions & Trigger Legal Audit",
                supporting_evidence=["Duplicate GSTIN 07AAAC12345A1Z1 registered on Vendor 101"], status="Alert"
            ),
            FraudCheck(
                vendor_id=105, fraud_score=98.0, risk_level="High", confidence=0.99,
                root_cause="Blacklisted Banking Details & Inaccessible Address", recommended_action="Immediate Vendor Termination",
                supporting_evidence=["Blacklisted Banking Routing Number", "Non-existent corporate address"], status="Alert"
            )
        ]
        db.session.add_all(fraud_cases)
        db.session.commit()
        print("  -> Seeding Fraud Check Audits: PASSED")

        print("[5/5] Seeding Machine Learning Anomalies...")
        anomalies = [
            VendorAnomaly(
                vendor_id=104, anomaly_score=95.0, severity="Critical",
                pattern="Shared Identity Clustering",
                observed_facts={"Duplicate GSTIN": "07AAAC12345A1Z1"},
                rule_findings=["Shared Tax GSTIN Attribute with Vendor 101"],
                ml_predictions={"Isolation Forest Score": -0.42},
                explanation="Vendor shares identical tax and banking credentials with active Vendor 101.",
                recommended_action="IMMEDIATE RESOLUTION: Block transactions and trigger legal audit.",
                status="Active"
            )
        ]
        db.session.add_all(anomalies)
        db.session.commit()
        print("  -> Seeding ML Anomaly Alerts: PASSED")

    # Restore original environment
    os.environ.pop('DATABASE_URL', None)

    print(f"\n[SUCCESS] DEMO DATASET GENERATED SUCCESSFULLY AT {DEMO_DB_PATH}!")

if __name__ == '__main__':
    seed_demo_dataset()
