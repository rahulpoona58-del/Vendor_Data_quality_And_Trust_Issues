from flask import Blueprint, request, jsonify, make_response, send_file
from src.domain.services.report_service import ReportService
from src.infrastructure.database.models import ReportSchedule, GeneratedReport, db
from src.infrastructure.security.decorators import login_required
import io
import logging

from src.infrastructure.async_jobs.background_job_service import BackgroundJobService

report_api = Blueprint('report_api', __name__)

@report_api.route('/api/v2/reports/generate', methods=['POST'])
@login_required
def generate():
    """Endpoint to trigger a real-time report download or enqueue an async background report job."""
    data = request.get_json() or {}
    report_type = data.get('report_type')
    export_format = data.get('export_format')
    is_async = data.get('async') is True or request.args.get('async') == 'true'
    
    if not report_type or not export_format:
        return jsonify({'success': False, 'message': 'report_type and export_format are required'}), 400
        
    try:
        if is_async:
            job_id = BackgroundJobService.submit_job(
                job_type='Report Generation',
                target_fn=ReportService.generate_report,
                args=(report_type, export_format, 'Admin')
            )
            return jsonify({
                'success': True,
                'message': f"Report '{report_type}' generation task queued for background execution.",
                'job_id': job_id,
                'status_url': f"/api/v2/jobs/{job_id}"
            }), 202
            
        content, mime_type, filename = ReportService.generate_report(report_type, export_format, generated_by='Admin')
        
        # If it is HTML, we can return the string directly or send it as a file download.
        # Let's send as a file download or stream!
        if isinstance(content, str):
            mem = io.BytesIO(content.encode('utf-8'))
        else:
            mem = io.BytesIO(content)
            
        return send_file(
            mem,
            mimetype=mime_type,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logging.error(f"Report endpoint failure: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@report_api.route('/api/v2/reports/schedule', methods=['POST'])
@login_required
def schedule_report():
    """Configures a recurring telemetry report schedule."""
    data = request.get_json() or {}
    report_type = data.get('report_type')
    frequency = data.get('frequency')
    export_format = data.get('export_format')
    recipient_email = data.get('recipient_email')
    
    if not all([report_type, frequency, export_format, recipient_email]):
        return jsonify({'success': False, 'message': 'Missing parameters'}), 400
        
    try:
        schedule = ReportSchedule(
            report_type=report_type,
            frequency=frequency,
            export_format=export_format,
            recipient_email=recipient_email,
            is_active=True
        )
        db.session.add(schedule)
        db.session.commit()
        return jsonify({'success': True, 'schedule': schedule.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@report_api.route('/api/v2/reports/schedule', methods=['GET'])
@login_required
def list_schedules():
    """Lists all configured recurring schedules."""
    schedules = ReportSchedule.query.all()
    return jsonify({'success': True, 'schedules': [s.to_dict() for s in schedules]}), 200

@report_api.route('/api/v2/reports/schedule/<int:schedule_id>', methods=['DELETE'])
@login_required
def delete_schedule(schedule_id):
    """Deletes a scheduled report profile."""
    schedule = ReportSchedule.query.get(schedule_id)
    if not schedule:
        return jsonify({'success': False, 'message': 'Schedule not found'}), 404
        
    try:
        db.session.delete(schedule)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Schedule deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@report_api.route('/api/v2/reports/history', methods=['GET'])
@login_required
def get_history():
    """Retrieves all generated report archive logs."""
    history = GeneratedReport.query.order_by(GeneratedReport.created_at.desc()).limit(50).all()
    return jsonify({'success': True, 'history': [h.to_dict() for h in history]}), 200
