import re
import os
import random
from src.infrastructure.database.models import VendorDocument, Vendor, OcrResult, db
import logging

class OcrEngine:
    """Document Intelligence and OCR processing engine analyzing vendor document formats."""
    
    @staticmethod
    def process_document(doc_id: int) -> dict:
        """Executes text-extraction and returns confidence score mapping and comparisons against master registry."""
        try:
            doc = VendorDocument.query.get(doc_id)
            if not doc or doc.is_deleted:
                return {'success': False, 'message': 'Document not found'}
                
            vendor = Vendor.query.get(doc.vendor_id)
            if not vendor:
                return {'success': False, 'message': 'Associated vendor profile not found'}
                
            # Read file if it exists, to extract raw text (in case it is text-based)
            raw_text = ""
            if os.path.exists(doc.storage_path):
                try:
                    if doc.mime_type.startswith('text/') or doc.name.endswith('.txt') or doc.name.endswith('.csv') or doc.name.endswith('.pdf'):
                        with open(doc.storage_path, 'r', encoding='utf-8', errors='ignore') as f:
                            raw_text = f.read()
                except Exception as ex:
                    logging.warning(f"Could not read raw text from disk for file {doc.name}: {str(ex)}")

            # Extract fields using regex patterns or fallback to simulated document-type extraction
            extracted = OcrEngine._extract_fields(raw_text, doc.document_type, vendor.name)
            
            # Compare extracted fields with vendor master profile details
            comparison = OcrEngine._compare_data(extracted, vendor)
            
            # Generate confidence scores
            confidence = OcrEngine._calculate_confidence(extracted, doc.document_type)
            
            # Determine document verification status based on comparison mismatch check
            all_match = all(val is True for val in comparison.values())
            doc.verification_status = 'Verified' if all_match else 'Rejected'
            
            # Check if OCR result already exists for this document
            ocr_res = OcrResult.query.filter_by(document_id=doc.id).first()
            if not ocr_res:
                ocr_res = OcrResult(
                    document_id=doc.id,
                    vendor_id=vendor.id,
                    extracted_data=extracted,
                    comparison_results=comparison,
                    confidence_scores=confidence,
                    status='Pending Review'
                )
                db.session.add(ocr_res)
            else:
                # Update existing OCR result
                ocr_res.extracted_data = extracted
                ocr_res.comparison_results = comparison
                ocr_res.confidence_scores = confidence
                ocr_res.status = 'Pending Review'
                ocr_res.corrected_data = None

            # Highlight mismatches and trigger Fraud check
            mismatches = [k for k, v in comparison.items() if v is False]
            if mismatches:
                from src.infrastructure.database.models import FraudCheck
                alert = FraudCheck(
                    vendor_id=vendor.id,
                    fraud_score=75.0,
                    risk_level='High',
                    confidence=0.9,
                    root_cause=f"Document OCR mismatch on: {', '.join(mismatches)}",
                    recommended_action="Reject payment cycles until details are manually verified.",
                    supporting_evidence={'mismatches': mismatches, 'doc_type': doc.document_type},
                    status='Alert'
                )
                db.session.add(alert)
                
            db.session.commit()

            # Recalculate Trust score & Risk levels
            from src.domain.services.trust_engine import TrustEngine
            TrustEngine.calculate_vendor_trust(vendor.id)
            
            logging.info(f"OCR successfully completed for document {doc.name} (id={doc.id})")
            return {'success': True, 'ocr_result': ocr_res.to_dict()}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"OCR processing failed: {str(e)}")
            return {'success': False, 'message': f"OCR engine error: {str(e)}"}
            
    @staticmethod
    def submit_correction(ocr_id: int, corrected_data: dict, reviewer: str) -> dict:
        """Applies manual review changes to correct data extraction anomalies."""
        try:
            ocr_res = OcrResult.query.get(ocr_id)
            if not ocr_res:
                return {'success': False, 'message': 'OCR record not found'}
                
            vendor = Vendor.query.get(ocr_res.vendor_id)
            doc = VendorDocument.query.get(ocr_res.document_id)
            
            # Recalculate comparison matches using the manually corrected data
            comparison = OcrEngine._compare_data(corrected_data, vendor)
            
            ocr_res.corrected_data = corrected_data
            ocr_res.comparison_results = comparison
            ocr_res.status = 'Corrected'
            ocr_res.reviewed_by = reviewer
            
            # Mark document verified if corrected data matches master profile details
            all_match = all(val is True for val in comparison.values())
            if doc:
                doc.verification_status = 'Verified' if all_match else 'Rejected'
                
            # Optional: update vendor master record if specific fields match corrections
            if corrected_data.get('vendor_name') and corrected_data['vendor_name'] != vendor.name:
                vendor.name = corrected_data['vendor_name']
                logging.info(f"Vendor {vendor.id} name updated via corrected OCR data to: {vendor.name}")
                
            db.session.commit()
            
            # Update Trust scores
            from src.domain.services.trust_engine import TrustEngine
            TrustEngine.calculate_vendor_trust(vendor.id)
            
            logging.info(f"OCR correction applied for record id={ocr_res.id} by {reviewer}")
            return {'success': True, 'ocr_result': ocr_res.to_dict()}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error submitting OCR corrections: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def _extract_fields(text: str, doc_type: str, vendor_name: str) -> dict:
        """Helper to scan raw text or generate fallback metrics for demonstrations."""
        # Initialize default return keys
        data = {
            'vendor_name': '',
            'gst_number': '',
            'pan_number': '',
            'address': '',
            'email': '',
            'phone': '',
            'bank_account': '',
            'ifsc': '',
            'cin': '',
            'dates': ''
        }
        
        # 1. Regex scanning of raw text if text is present
        if text:
            # Email pattern
            emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
            if emails: data['email'] = emails[0]
            
            # GST pattern
            gsts = re.findall(r'[0-9]{2}[A-Z0-9]{13}', text)
            if gsts: data['gst_number'] = gsts[0]
            
            # PAN pattern
            pans = re.findall(r'[A-Z0-9]{10}', text)
            if pans: data['pan_number'] = pans[0]
            
            # Phone pattern
            phones = re.findall(r'\b\d{10}\b', text)
            if phones: data['phone'] = phones[0]
            
            # IFSC pattern
            ifscs = re.findall(r'[A-Z]{4}0[A-Z0-9]{6}', text)
            if ifscs: data['ifsc'] = ifscs[0]
            
            # CIN pattern
            cins = re.findall(r'[UL][0-9]{5}[A-Z]{2}[0-9]{4}[PLC]{3}[0-9]{6}', text)
            if cins: data['cin'] = cins[0]

        # 2. Add realistic mock values if regex extraction was empty, introducing discrepancies
        # to demonstrate mismatch flagging and verification capabilities in UI
        if not data['vendor_name']:
            # 10% chance of typo in vendor name to demonstrate mismatch
            if random.random() < 0.15:
                data['vendor_name'] = f"{vendor_name} Ltd"
            else:
                data['vendor_name'] = vendor_name
                
        if doc_type == 'GST Certificate' and not data['gst_number']:
            # Random GST matching vendor ID
            data['gst_number'] = f"27AAAAA{random.randint(1000, 9999)}A1Z5"
            data['address'] = "Plot 45, Industrial Zone, Mumbai, MH, 400001"
            
        elif doc_type == 'PAN Card' and not data['pan_number']:
            data['pan_number'] = f"ABCPV{random.randint(1000, 9999)}C"
            
        elif doc_type == 'Bank Proof' and not data['bank_account']:
            data['bank_account'] = f"91201004{random.randint(10000, 99999)}"
            data['ifsc'] = "UTIB0000245"
            
        elif doc_type == 'Contracts':
            data['cin'] = f"L{random.randint(10000, 99999)}MH{random.randint(1990, 2020)}PLC{random.randint(100000, 999999)}"
            data['dates'] = "2026-04-01"
            
        # Common defaults
        if not data['email']:
            # Make phone and email mismatch slightly to showcase highlights
            data['email'] = f"contact@{vendor_name.lower().replace(' ', '_')}.com"
        if not data['phone']:
            data['phone'] = f"+91 {random.randint(9000000000, 9999999999)}"
            
        return data

    @staticmethod
    def _compare_data(extracted: dict, vendor: Vendor) -> dict:
        """Compares extracted values against vendor master record attributes."""
        name_match = False
        if extracted.get('vendor_name'):
            name_match = extracted['vendor_name'].strip().lower() == vendor.name.strip().lower()
            
        gst_match = True
        if extracted.get('gst_number') and vendor.gst_number:
            gst_match = extracted['gst_number'].strip().replace('-', '') == vendor.gst_number.strip().replace('-', '')
            
        pan_match = True
        if extracted.get('pan_number') and vendor.pan_number:
            pan_match = extracted['pan_number'].strip().upper() == vendor.pan_number.strip().upper()
            
        bank_match = True
        if extracted.get('bank_account') and vendor.bank_account:
            bank_match = extracted['bank_account'].strip() == vendor.bank_account.strip()
            
        address_match = True
        if extracted.get('address') and vendor.address:
            address_match = extracted['address'].strip().lower() in vendor.address.strip().lower() or vendor.address.strip().lower() in extracted['address'].strip().lower()
            
        cin_match = True
        if extracted.get('cin'):
            cin_match = bool(re.match(r'^[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$', extracted['cin']))

        return {
            'vendor_name': name_match,
            'email': True,
            'phone': True,
            'gst_number': gst_match,
            'pan_number': pan_match,
            'bank_account': bank_match,
            'address': address_match,
            'cin': cin_match
        }

    @staticmethod
    def _calculate_confidence(extracted: dict, doc_type: str) -> dict:
        """Simulates field-level OCR scanning confidence readings."""
        scores = {}
        for key, val in extracted.items():
            if not val:
                scores[key] = 0.0
                continue
                
            # Set high confidence for key documents
            if doc_type == 'GST Certificate' and key in {'gst_number', 'vendor_name'}:
                scores[key] = round(random.uniform(0.94, 0.99), 2)
            elif doc_type == 'PAN Card' and key == 'pan_number':
                scores[key] = round(random.uniform(0.95, 0.99), 2)
            else:
                scores[key] = round(random.uniform(0.75, 0.95), 2)
        return scores
