from flask import Blueprint, request, jsonify
from src.domain.services.ocr_engine import OcrEngine
from src.infrastructure.security.decorators import login_required, role_required, get_current_user
from src.infrastructure.database.models import OcrResult
import logging

ocr_api = Blueprint('ocr_api', __name__)

@ocr_api.route('/api/v2/documents/<int:doc_id>/ocr', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward', 'Manager', 'Auditor'])
def run_ocr(doc_id):
    """API endpoint to trigger document OCR extraction."""
    result = OcrEngine.process_document(doc_id)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result), 200

@ocr_api.route('/api/v2/documents/<int:doc_id>/ocr', methods=['GET'])
@login_required
def get_ocr_details(doc_id):
    """API endpoint to retrieve OCR processing logs for a document."""
    ocr_res = OcrResult.query.filter_by(document_id=doc_id).first()
    if not ocr_res:
        return jsonify({'success': False, 'message': 'OCR details not found for this document'}), 404
        
    return jsonify({'success': True, 'ocr_result': ocr_res.to_dict()})

@ocr_api.route('/api/v2/ocr/<int:ocr_id>/correct', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward'])
def apply_ocr_correction(ocr_id):
    """API endpoint to apply manual corrections to OCR extractions."""
    data = request.get_json() or {}
    corrected_data = data.get('corrected_data')
    
    if not corrected_data:
        return jsonify({'success': False, 'message': 'corrected_data field is required'}), 400
        
    user = get_current_user()
    result = OcrEngine.submit_correction(ocr_id, corrected_data, user['email'])
    if not result['success']:
        return jsonify(result), 400
        
    return jsonify(result)
