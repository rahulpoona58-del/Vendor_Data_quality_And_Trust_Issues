from flask import Blueprint, request, jsonify, send_file, current_app
from src.application.use_cases.document_service import DocumentService
from src.infrastructure.security.decorators import login_required, role_required, get_current_user
from datetime import datetime
import os
import logging

from src.infrastructure.security.rate_limiter import rate_limit

document_api = Blueprint('document_api', __name__)

@document_api.route('/api/v2/vendors/<int:vendor_id>/documents', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward', 'Manager'])
@rate_limit('upload')
def upload_vendor_document(vendor_id):
    """API endpoint to securely upload a vendor document."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file element in request'}), 400
        
    file = request.files['file']
    doc_type = request.form.get('document_type')
    expiry_date_str = request.form.get('expiry_date') # ISO date string YYYY-MM-DD
    
    if not doc_type:
        return jsonify({'success': False, 'message': 'document_type parameter is required'}), 400
        
    expiry_date = None
    if expiry_date_str:
        try:
            expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid expiry date format. Use YYYY-MM-DD'}), 400
            
    user = get_current_user()
    storage_root = current_app.config['UPLOAD_FOLDER']
    
    result = DocumentService.upload_document(
        vendor_id=vendor_id,
        file=file,
        doc_type=doc_type,
        uploaded_by=user['email'],
        storage_root=storage_root,
        expiry_date=expiry_date
    )
    
    if not result['success']:
        return jsonify(result), 400
        
    return jsonify(result), 201

@document_api.route('/api/v2/vendors/<int:vendor_id>/documents', methods=['GET'])
@login_required
def list_vendor_documents(vendor_id):
    """API endpoint to list active documents for a specific vendor."""
    include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'
    docs = DocumentService.get_documents_by_vendor(vendor_id, include_deleted=include_deleted)
    return jsonify({'success': True, 'documents': docs})

@document_api.route('/api/v2/documents/<int:doc_id>', methods=['DELETE'])
@login_required
@role_required(['Admin', 'Data Steward'])
def delete_document(doc_id):
    """API endpoint to soft delete a document."""
    user = get_current_user()
    result = DocumentService.soft_delete_document(doc_id, user['email'])
    if not result['success']:
        return jsonify(result), 404
    return jsonify(result)

@document_api.route('/api/v2/documents/<int:doc_id>/restore', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward'])
def restore_document(doc_id):
    """API endpoint to restore a soft-deleted document."""
    user = get_current_user()
    result = DocumentService.restore_document(doc_id, user['email'])
    if not result['success']:
        return jsonify(result), 404
    return jsonify(result)

@document_api.route('/api/v2/documents/<int:doc_id>/verify', methods=['POST'])
@login_required
@role_required(['Admin', 'Auditor'])
def verify_document(doc_id):
    """API endpoint for auditors to approve/reject documents."""
    status = request.json.get('status')
    if not status:
        return jsonify({'success': False, 'message': 'status parameter is required'}), 400
        
    user = get_current_user()
    result = DocumentService.update_verification_status(doc_id, status, user['email'])
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result)

@document_api.route('/api/v2/documents/<int:doc_id>/download', methods=['GET'])
@login_required
def download_document(doc_id):
    """API endpoint to securely download a document."""
    doc = DocumentService.get_document_by_id(doc_id)
    if not doc or doc.is_deleted:
        return jsonify({'success': False, 'message': 'Document not found'}), 404
        
    # Verify file exists on local storage
    if not os.path.exists(doc.storage_path):
        return jsonify({'success': False, 'message': 'File not found on storage server'}), 404
        
    # Prevent traversal attacks: verify storage file is inside configured directory
    storage_root = os.path.abspath(current_app.config['UPLOAD_FOLDER'])
    absolute_filepath = os.path.abspath(doc.storage_path)
    if not absolute_filepath.startswith(storage_root):
        logging.critical(f"Directory traversal attempt detected! File: {doc.storage_path}")
        return jsonify({'success': False, 'message': 'Access Denied'}), 403
        
    return send_file(
        absolute_filepath,
        mimetype=doc.mime_type,
        as_attachment=True,
        download_name=doc.name
    )
