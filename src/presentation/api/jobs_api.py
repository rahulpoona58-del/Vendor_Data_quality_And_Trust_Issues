from flask import Blueprint, request, jsonify
from src.infrastructure.async_jobs.background_job_service import BackgroundJobService
from src.infrastructure.security.decorators import login_required, role_required
from src.domain.services.report_service import ReportService
from src.domain.agents.agent_system import AgentOrchestrator
import logging
import time

jobs_api = Blueprint('jobs_api', __name__)

def _dummy_long_task(duration: float = 1.0, progress_callback=None):
    """Simulates a background processing task with step-by-step progress callbacks."""
    for i in range(1, 6):
        time.sleep(duration / 5.0)
        if progress_callback:
            progress_callback(i * 20)
    return {'status': 'Completed', 'items_processed': 100}

@jobs_api.route('/api/v2/jobs/submit', methods=['POST'])
@login_required
def submit_background_job():
    """API endpoint to submit a long-running job for background processing."""
    data = request.get_json() or {}
    job_type = data.get('job_type', 'General')
    
    if job_type == 'Report':
        report_type = data.get('report_type', 'Vendor Summary')
        fmt = data.get('format', 'CSV')
        job_id = BackgroundJobService.submit_job(
            job_type='Report Generation',
            target_fn=ReportService.generate_report,
            args=(report_type, fmt)
        )
    elif job_type == 'AI Analysis':
        vendor_id = int(data.get('vendor_id', 1))
        role = request.headers.get('X-Role') or 'Viewer'
        orchestrator = AgentOrchestrator()
        job_id = BackgroundJobService.submit_job(
            job_type='AI Multi-Agent Diagnostic',
            target_fn=orchestrator.run_vendor_diagnostic,
            args=(vendor_id, role)
        )
    else:
        job_id = BackgroundJobService.submit_job(
            job_type=job_type,
            target_fn=_dummy_long_task,
            args=(1.0,)
        )
        
    return jsonify({
        'success': True,
        'message': f"Background job '{job_type}' submitted successfully.",
        'job_id': job_id
    }), 202

@jobs_api.route('/api/v2/jobs/<job_id>', methods=['GET'])
@login_required
def get_job_status(job_id):
    """API endpoint to poll job execution status, progress percentage, and results."""
    status = BackgroundJobService.get_job_status(job_id)
    if 'success' in status and not status['success']:
        return jsonify(status), 404
    return jsonify({'success': True, 'job': status}), 200

@jobs_api.route('/api/v2/jobs', methods=['GET'])
@login_required
def list_jobs():
    """API endpoint to list recent background jobs."""
    jobs = BackgroundJobService.list_jobs()
    return jsonify({'success': True, 'jobs': jobs}), 200
