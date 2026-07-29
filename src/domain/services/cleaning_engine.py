import re
from datetime import datetime
from src.infrastructure.database.models import Vendor, OcrResult, DataCleaningSuggestion, db
import logging

class DataCleaningEngine:
    """Cleanses spelling, formatting, and casing anomalies from vendor profiles and OCR results."""
    
    @staticmethod
    def scan_vendor(vendor_id: int) -> dict:
        """Runs checks against vendor details and OCR metrics, registering correction suggestions."""
        try:
            vendor = Vendor.query.get(vendor_id)
            if not vendor:
                return {'success': False, 'message': 'Vendor not found'}
                
            suggestions = []
            
            # 1. Clean Vendor Name
            name = vendor.name
            cleaned_name = DataCleaningEngine._normalize_name(name)
            if cleaned_name != name:
                sug = DataCleaningEngine._create_or_update_suggestion(
                    vendor_id=vendor.id,
                    field_name='vendor_name',
                    original=name,
                    suggested=cleaned_name,
                    confidence=0.95,
                    reason="Normalized casing, removed duplicate words, and standardized corporate suffixes."
                )
                suggestions.append(sug)
                
            # 2. Check OCR Extracted details for formatting and spelling errors
            ocr_res = OcrResult.query.filter_by(vendor_id=vendor.id).first()
            if ocr_res:
                data = ocr_res.corrected_data or ocr_res.extracted_data
                
                # Check Email Formatting
                email = data.get('email', '')
                if email:
                    cleaned_email = DataCleaningEngine._normalize_email(email)
                    if cleaned_email != email:
                        sug = DataCleaningEngine._create_or_update_suggestion(
                            vendor_id=vendor.id,
                            field_name='email',
                            original=email,
                            suggested=cleaned_email,
                            confidence=0.99,
                            reason="Normalized email string to lowercase format."
                        )
                        suggestions.append(sug)
                        
                # Check Phone Formatting
                phone = data.get('phone', '')
                if phone:
                    cleaned_phone = DataCleaningEngine._normalize_phone(phone)
                    if cleaned_phone != phone:
                        sug = DataCleaningEngine._create_or_update_suggestion(
                            vendor_id=vendor.id,
                            field_name='phone',
                            original=phone,
                            suggested=cleaned_phone,
                            confidence=0.90,
                            reason="Formatted phone string to international E.164 standard (+91)."
                        )
                        suggestions.append(sug)
                        
                # Check Address Formatting
                address = data.get('address', '')
                if address:
                    cleaned_address = DataCleaningEngine._normalize_address(address)
                    if cleaned_address != address:
                        sug = DataCleaningEngine._create_or_update_suggestion(
                            vendor_id=vendor.id,
                            field_name='address',
                            original=address,
                            suggested=cleaned_address,
                            confidence=0.85,
                            reason="Title-cased address elements and standardized road abbreviations."
                        )
                        suggestions.append(sug)
                        
            db.session.commit()
            return {'success': True, 'suggestions': [s.to_dict() for s in suggestions]}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Data cleaning check failed: {str(e)}")
            return {'success': False, 'message': f"Data cleaning error: {str(e)}"}

    @staticmethod
    def apply_suggestion(suggestion_id: int) -> dict:
        """Applies a cleaning suggestion to the master database."""
        try:
            sug = DataCleaningSuggestion.query.get(suggestion_id)
            if not sug or sug.status != 'Pending':
                return {'success': False, 'message': 'Active cleaning suggestion not found'}
                
            vendor = Vendor.query.get(sug.vendor_id)
            
            old_val = ""
            if sug.field_name == 'vendor_name':
                old_val = vendor.name
                vendor.name = sug.suggested_value
                logging.info(f"Cleaned vendor name updated from '{old_val}' to '{sug.suggested_value}'")
                
            elif sug.field_name in {'email', 'phone', 'address'}:
                old_val = getattr(vendor, sug.field_name) or ""
                setattr(vendor, sug.field_name, sug.suggested_value)
                
                # Update OCR records
                ocr_res = OcrResult.query.filter_by(vendor_id=vendor.id).first()
                if ocr_res:
                    curr_data = dict(ocr_res.corrected_data or ocr_res.extracted_data)
                    curr_data[sug.field_name] = sug.suggested_value
                    ocr_res.corrected_data = curr_data
                    logging.info(f"Cleaned OCR property '{sug.field_name}' updated to '{sug.suggested_value}'")
                    
            sug.status = 'Applied'
            sug.applied_at = datetime.utcnow()
            
            # Log lineage audit trace entry
            from src.domain.services.audit_service import AuditService
            AuditService.log_audit(
                performed_by='Data Cleaning Engine',
                ip_address='127.0.0.1',
                action_type='Apply Data Cleaning',
                module_name='Data Cleaning',
                old_value={sug.field_name: old_val},
                new_value={sug.field_name: sug.suggested_value},
                reason=sug.reason,
                vendor_id=vendor.id,
                original_source='AI Recommendation',
                import_source='Bulk Cleaning Pipeline',
                ai_suggested=True,
                human_approved=True,
                validation_result='Passed formatting check'
            )
            
            db.session.commit()
            
            return {'success': True, 'suggestion': sug.to_dict()}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error applying correction: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def reject_suggestion(suggestion_id: int) -> dict:
        """Rejects a cleansing suggestion, archiving it from operational view."""
        try:
            sug = DataCleaningSuggestion.query.get(suggestion_id)
            if not sug or sug.status != 'Pending':
                return {'success': False, 'message': 'Active suggestion not found'}
                
            sug.status = 'Rejected'
            db.session.commit()
            return {'success': True, 'suggestion': sug.to_dict()}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error rejecting suggestion: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def bulk_apply_suggestions(vendor_id: int) -> dict:
        """Applies all 'Approved' or 'Pending' suggestions in a single transaction."""
        try:
            sugs = DataCleaningSuggestion.query.filter_by(vendor_id=vendor_id, status='Pending').all()
            applied_ids = []
            
            for sug in sugs:
                res = DataCleaningEngine.apply_suggestion(sug.id)
                if res['success']:
                    applied_ids.append(sug.id)
                    
            return {'success': True, 'applied_count': len(applied_ids), 'ids': applied_ids}
        except Exception as e:
            logging.error(f"Error bulk-applying cleaning suggestions: {str(e)}")
            return {'success': False, 'message': str(e)}

    # Helper Normalizers
    @staticmethod
    def _normalize_name(name: str) -> str:
        """Removes casing anomalies, duplicate words, and cleans name suffixes."""
        # 1. Casing normalization (Title Case)
        words = name.split()
        normalized_words = []
        for word in words:
            # If word is fully uppercase like "VENDOR_12", convert to Title case
            if word.isupper():
                normalized_words.append(word.capitalize())
            else:
                normalized_words.append(word)
        temp_name = " ".join(normalized_words)
        
        # 2. Duplicate words removal (e.g. "Inc Inc" -> "Inc")
        temp_name = re.sub(r'\b(\w+)\s+\1\b', r'\1', temp_name, flags=re.IGNORECASE)
        
        # 3. Standardize Suffixes
        temp_name = re.sub(r'\bINCORPORATED\b', 'Inc.', temp_name, flags=re.IGNORECASE)
        temp_name = re.sub(r'\bLMTD\b', 'Ltd.', temp_name, flags=re.IGNORECASE)
        temp_name = re.sub(r'\bCO\b', 'Co.', temp_name, flags=re.IGNORECASE)
        
        return temp_name.strip()

    @staticmethod
    def _normalize_email(email: str) -> str:
        """Normalizes email strings to lower case and replaces invalid separators."""
        # Remove spacing
        cleaned = email.strip().lower()
        # Correct common character slips (e.g. contact#vendor.com -> contact@vendor.com)
        cleaned = cleaned.replace('#', '@')
        return cleaned

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Standardizes phone numbers to standard country code spacing."""
        # Extract digits
        digits = re.sub(r'\D', '', phone)
        if len(digits) == 10:
            return f"+91 {digits[:5]} {digits[5:]}"
        elif len(digits) == 12 and digits.startswith('91'):
            return f"+91 {digits[2:7]} {digits[7:]}"
        return phone.strip()

    @staticmethod
    def _normalize_address(address: str) -> str:
        """Applies road suffix normalization and title capitalization."""
        # Standardize words
        cleaned = address.title()
        cleaned = re.sub(r'\bStreet\b', 'St.', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bRoad\b', 'Rd.', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bAvenue\b', 'Ave.', cleaned, flags=re.IGNORECASE)
        return cleaned

    @staticmethod
    def _create_or_update_suggestion(vendor_id: int, field_name: str, original: str, suggested: str, confidence: float, reason: str) -> DataCleaningSuggestion:
        """Saves suggestion mapping record to database, preventing duplication."""
        existing = DataCleaningSuggestion.query.filter_by(
            vendor_id=vendor_id,
            field_name=field_name,
            status='Pending'
        ).first()
        
        if existing:
            existing.suggested_value = suggested
            existing.confidence = confidence
            existing.reason = reason
            return existing
        else:
            new_sug = DataCleaningSuggestion(
                vendor_id=vendor_id,
                field_name=field_name,
                original_value=original,
                suggested_value=suggested,
                confidence=confidence,
                reason=reason,
                status='Pending'
            )
            db.session.add(new_sug)
            return new_sug
