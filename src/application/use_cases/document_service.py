import os
import hashlib
from datetime import datetime
from werkzeug.datastructures import FileStorage
from src.infrastructure.database.models import VendorDocument, db
from src.presentation.validation.validation import (
    secure_filepath, allowed_file, check_file_size, 
    validate_document_type, validate_mime_type, validate_magic_bytes
)
import logging

class DocumentService:
    """Orchestrator for managing secure vendor documents, version histories, and soft-deletes."""
    
    @staticmethod
    def upload_document(vendor_id: int, file: FileStorage, doc_type: str, uploaded_by: str, storage_root: str, expiry_date: datetime = None) -> dict:
        """Securely saves an uploaded file and writes its metadata registry to the database."""
        try:
            if not file or not file.filename:
                return {'success': False, 'message': 'No file selected'}
                
            if not allowed_file(file.filename):
                return {'success': False, 'message': 'File extension or type is not permitted'}
                
            if not validate_mime_type(file.content_type, file.filename):
                return {'success': False, 'message': 'File MIME type is not permitted'}
                
            if not validate_document_type(doc_type):
                return {'success': False, 'message': 'Unsupported document category'}
                
            # Read content to compute hash and check size
            file_data = file.read()
            file_size = len(file_data)
            file.seek(0) # Reset stream position
            
            if file_size == 0:
                return {'success': False, 'message': 'File cannot be empty (0 bytes)'}
                
            if not check_file_size(file_size):
                return {'success': False, 'message': 'File size exceeds maximum 10MB limit'}
                
            if not validate_magic_bytes(file_data, file.filename):
                return {'success': False, 'message': 'File magic header validation failed'}
                
            # Compute SHA-256 hash
            sha256_hash = hashlib.sha256(file_data).hexdigest()
            
            # Sanitize filename and construct storage path
            safe_name = secure_filepath(file.filename)
            vendor_dir = os.path.join(storage_root, str(vendor_id))
            os.makedirs(vendor_dir, exist_ok=True)
            
            # Check if this document type already exists for this vendor to determine versioning
            existing_doc = VendorDocument.query.filter_by(
                vendor_id=vendor_id, 
                document_type=doc_type, 
                is_deleted=False
            ).order_by(VendorDocument.version.desc()).first()
            
            version = 1
            if existing_doc:
                # Increment version if replacing
                version = existing_doc.version + 1
                # Archive the old file or mark it superseded (in this implementation, we soft-delete it)
                existing_doc.is_deleted = True
                existing_doc.deleted_at = datetime.utcnow()
            
            # Append version index to file name to prevent collision on disk
            name_parts = safe_name.rsplit('.', 1)
            versioned_filename = f"{name_parts[0]}_v{version}.{name_parts[1]}"
            filepath = os.path.join(vendor_dir, versioned_filename)
            
            # Save file data to disk
            with open(filepath, 'wb') as f:
                f.write(file_data)
                
            # Create Database log entry
            new_doc = VendorDocument(
                vendor_id=vendor_id,
                name=safe_name,
                document_type=doc_type,
                version=version,
                uploaded_by=uploaded_by,
                file_hash=sha256_hash,
                file_size=file_size,
                mime_type=file.content_type or 'application/octet-stream',
                storage_path=filepath,
                expiry_date=expiry_date
            )
            
            db.session.add(new_doc)
            db.session.commit()
            
            # Log timeline activity
            from src.domain.services.timeline_service import TimelineService
            TimelineService.log_activity(
                vendor_id=vendor_id,
                activity_type='Document Uploaded',
                description=f"Document '{safe_name}' ({doc_type}) version {version} uploaded by {uploaded_by}.",
                performed_by=uploaded_by
            )
            
            # System Audit Log
            from src.domain.services.audit_service import AuditService
            AuditService.log_audit(
                performed_by=uploaded_by,
                ip_address='127.0.0.1',
                action_type="Upload Document",
                module_name="Document",
                old_value=None,
                new_value={"doc_name": safe_name, "doc_type": doc_type, "version": version},
                reason="Mandatory compliance credential ingestion",
                vendor_id=vendor_id
            )
            
            logging.info(f"Document uploaded: {safe_name} (v{version}) for vendor_id {vendor_id}")
            return {'success': True, 'document': new_doc.to_dict()}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error uploading document: {str(e)}")
            return {'success': False, 'message': f"Internal server error: {str(e)}"}

    @staticmethod
    def get_documents_by_vendor(vendor_id: int, include_deleted: bool = False) -> list:
        """Fetches all documents associated with a vendor."""
        query = VendorDocument.query.filter_by(vendor_id=vendor_id)
        if not include_deleted:
            query = query.filter_by(is_deleted=False)
        docs = query.order_by(VendorDocument.upload_date.desc()).all()
        return [doc.to_dict() for doc in docs]

    @staticmethod
    def get_document_by_id(doc_id: int) -> VendorDocument:
        """Retrieves a single document entity from the registry."""
        return VendorDocument.query.get(doc_id)

    @staticmethod
    def soft_delete_document(doc_id: int, user_email: str) -> dict:
        """Marks a document as deleted (soft-delete) for traceability audits."""
        try:
            doc = VendorDocument.query.get(doc_id)
            if not doc or doc.is_deleted:
                return {'success': False, 'message': 'Document not found'}
                
            doc.is_deleted = True
            doc.deleted_at = datetime.utcnow()
            db.session.commit()
            
            # Log timeline activity
            from src.domain.services.timeline_service import TimelineService
            TimelineService.log_activity(
                vendor_id=doc.vendor_id,
                activity_type='Admin Actions',
                description=f"Document '{doc.name}' soft-deleted by {user_email}.",
                performed_by=user_email
            )
            
            # System Audit Log
            from src.domain.services.audit_service import AuditService
            AuditService.log_audit(
                performed_by=user_email,
                ip_address='127.0.0.1',
                action_type="Soft Delete Document",
                module_name="Document",
                old_value={"doc_name": doc.name, "doc_type": doc.document_type},
                new_value={"is_deleted": True},
                reason="Auditor manual override request",
                vendor_id=doc.vendor_id
            )
            
            logging.info(f"Document soft-deleted: {doc.name} (id={doc.id}) by {user_email}")
            return {'success': True, 'message': 'Document soft deleted successfully'}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error soft deleting document {doc_id}: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def restore_document(doc_id: int, user_email: str) -> dict:
        """Restores a soft-deleted document."""
        try:
            doc = VendorDocument.query.get(doc_id)
            if not doc or not doc.is_deleted:
                return {'success': False, 'message': 'Deleted document not found'}
                
            doc.is_deleted = False
            doc.deleted_at = None
            db.session.commit()
            
            logging.info(f"Document restored: {doc.name} (id={doc.id}) by {user_email}")
            return {'success': True, 'message': 'Document restored successfully'}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error restoring document {doc_id}: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def update_verification_status(doc_id: int, status: str, auditor_email: str) -> dict:
        """Approves or rejects documents during audits."""
        try:
            if status not in {'Verified', 'Rejected', 'Pending'}:
                return {'success': False, 'message': 'Invalid status option'}
                
            doc = VendorDocument.query.get(doc_id)
            if not doc or doc.is_deleted:
                return {'success': False, 'message': 'Document not found'}
                
            doc.verification_status = status
            db.session.commit()
            
            logging.info(f"Document status updated: {doc.name} status={status} by auditor {auditor_email}")
            return {'success': True, 'document': doc.to_dict()}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating status for document {doc_id}: {str(e)}")
            return {'success': False, 'message': str(e)}
