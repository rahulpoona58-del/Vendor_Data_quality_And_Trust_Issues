import time
import os
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import text
from src.infrastructure.database.models import db
from src.infrastructure.cache.cache_service import MemoryCacheService
from src.infrastructure.async_jobs.background_job_service import BackgroundJobService
from src.infrastructure.logging.logger import get_health_metrics, log_health_metrics
from src.infrastructure.security.decorators import login_required
from src.domain.services.health_engine import HealthEngine

health_api = Blueprint('health_api', __name__)

START_TIME = time.time()

def check_database_health() -> dict:
    """Verifies database connection availability and measures query latency."""
    t0 = time.time()
    try:
        db.session.execute(text('SELECT 1'))
        latency_ms = round((time.time() - t0) * 1000, 2)
        return {
            "status": "HEALTHY",
            "connected": True,
            "latency_ms": latency_ms
        }
    except Exception as e:
        return {
            "status": "UNHEALTHY",
            "connected": False,
            "error": str(e)
        }

def check_cache_health() -> dict:
    """Verifies memory/redis cache get/set operations and measures access latency."""
    t0 = time.time()
    try:
        key = "health_probe_key"
        MemoryCacheService.set(key, "OK", ttl=5)
        val = MemoryCacheService.get(key)
        latency_ms = round((time.time() - t0) * 1000, 2)
        
        is_healthy = (val == "OK")
        return {
            "status": "HEALTHY" if is_healthy else "UNHEALTHY",
            "connected": is_healthy,
            "latency_ms": latency_ms
        }
    except Exception as e:
        return {
            "status": "UNHEALTHY",
            "connected": False,
            "error": str(e)
        }

def check_background_jobs_health() -> dict:
    """Inspects background job service status and worker queue metrics."""
    try:
        jobs = BackgroundJobService.list_jobs(limit=100)
        queued = sum(1 for j in jobs if j.get('status') == 'Queued')
        processing = sum(1 for j in jobs if j.get('status') == 'Processing')
        completed = sum(1 for j in jobs if j.get('status') == 'Completed')
        failed = sum(1 for j in jobs if j.get('status') == 'Failed')
        
        return {
            "status": "HEALTHY",
            "total_tracked_jobs": len(jobs),
            "queued_jobs": queued,
            "processing_jobs": processing,
            "completed_jobs": completed,
            "failed_jobs": failed,
            "max_workers": 4
        }
    except Exception as e:
        return {
            "status": "DEGRADED",
            "error": str(e)
        }

@health_api.route('/api/v2/health', methods=['GET'])
def get_full_health_status():
    """Deployment Monitoring & Readiness Probe Endpoint verifying App, DB, Cache, and Jobs."""
    uptime_seconds = round(time.time() - START_TIME, 2)
    
    db_health = check_database_health()
    cache_health = check_cache_health()
    jobs_health = check_background_jobs_health()
    sys_metrics = get_health_metrics()
    
    all_healthy = (
        db_health["status"] == "HEALTHY" and
        cache_health["status"] == "HEALTHY" and
        jobs_health["status"] == "HEALTHY"
    )
    
    response_payload = {
        "status": "HEALTHY" if all_healthy else "UNHEALTHY",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": os.getenv("FLASK_ENV", "development"),
        "uptime_seconds": uptime_seconds,
        "components": {
            "application": {
                "status": "HEALTHY",
                "uptime_seconds": uptime_seconds,
                "process_id": os.getpid()
            },
            "database": db_health,
            "cache": cache_health,
            "background_jobs": jobs_health
        },
        "system_resources": sys_metrics
    }
    
    status_code = 200 if all_healthy else 503
    return jsonify(response_payload), status_code

@health_api.route('/api/v2/health/liveness', methods=['GET'])
def liveness_probe():
    """Kubernetes / Docker Container Liveness Probe (Returns 200 OK if web process is running)."""
    return jsonify({
        "status": "UP",
        "uptime_seconds": round(time.time() - START_TIME, 2)
    }), 200

@health_api.route('/api/v2/health/readiness', methods=['GET'])
def readiness_probe():
    """Deployment Readiness Probe (Verifies DB and Cache connectivity before serving traffic)."""
    db_health = check_database_health()
    cache_health = check_cache_health()
    
    ready = (db_health["connected"] and cache_health["connected"])
    return jsonify({
        "status": "READY" if ready else "NOT_READY",
        "database_connected": db_health["connected"],
        "cache_connected": cache_health["connected"]
    }), 200 if ready else 503

@health_api.route('/api/v2/health/metrics', methods=['GET'])
def get_detailed_health_metrics():
    """Returns detailed process metrics and emits a structured telemetry log."""
    log_health_metrics()
    metrics = get_health_metrics()
    return jsonify({"success": True, "metrics": metrics}), 200

@health_api.route('/api/v2/health/index', methods=['GET'])
@login_required
def get_health_index():
    """API endpoint returning combined health score parameters for dashboard visualization."""
    v_id = request.args.get('vendor_id')
    vendor_id = int(v_id) if v_id and v_id.isdigit() else None
    
    result = HealthEngine.calculate_health(vendor_id)
    return jsonify(result), 200
