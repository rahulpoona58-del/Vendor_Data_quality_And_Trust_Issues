import os
import time
import json
import logging
import uuid
import psutil
from logging.handlers import RotatingFileHandler
from pathlib import Path
from flask import request, g

class StructuredJsonFormatter(logging.Formatter):
    """Custom JSON Formatter producing standardized structured logs for centralized logging systems."""

    def format(self, record):
        from datetime import datetime
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
            "event_type": getattr(record, "event_type", "GENERAL"),
            "request_id": getattr(record, "request_id", None),
            "message": record.getMessage(),
        }

        # Include additional structured metadata if attached
        if hasattr(record, "metadata") and isinstance(record.metadata, dict):
            log_record["metadata"] = record.metadata

        # Include exception tracebacks if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)

def setup_logging(config):
    """Configures centralized structured logging with console and rotating file handlers."""
    log_level_name = getattr(config, 'LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to prevent duplicate logs
    if root_logger.handlers:
        root_logger.handlers.clear()

    # 1. Console Stream Handler (Compact Format)
    console_format = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(event_type)s] %(module)s:%(lineno)d: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_format)
    console_handler.setLevel(log_level)

    # Inject default event_type filter for console handler
    class EventTypeFilter(logging.Filter):
        def filter(self, record):
            if not hasattr(record, 'event_type'):
                record.event_type = 'GENERAL'
            if not hasattr(record, 'request_id'):
                record.request_id = None
            return True

    console_handler.addFilter(EventTypeFilter())
    root_logger.addHandler(console_handler)

    # 2. Structured JSON Rotating File Handler
    log_file_path = Path(getattr(config, 'LOG_FILE_PATH', 'logs/app.log'))
    try:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB rotating file limit
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(StructuredJsonFormatter())
        file_handler.setLevel(log_level)
        file_handler.addFilter(EventTypeFilter())
        root_logger.addHandler(file_handler)

        logging.info(f"Centralized Structured Logging initialized at {log_file_path}", extra={"event_type": "SYSTEM_INIT"})
    except Exception as e:
        logging.error(f"Failed to initialize file logger: {str(e)}", extra={"event_type": "SYSTEM_ERROR"})

# =========================================================================
# STRUCTURED EVENT LOGGING HELPERS
# =========================================================================

def log_event(event_type: str, level: int, message: str, metadata: dict = None):
    """Emits a structured log event with metadata payload."""
    logger = logging.getLogger("app.centralized")
    extra = {
        "event_type": event_type,
        "metadata": metadata or {},
        "request_id": getattr(g, "request_id", None)
    }
    logger.log(level, message, extra=extra)

def log_api_request(method: str, path: str, status_code: int, duration_ms: float, client_ip: str, user_id: str = None):
    """Logs structured HTTP API Request telemetries."""
    level = logging.INFO if status_code < 400 else (logging.WARNING if status_code < 500 else logging.ERROR)
    metadata = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "client_ip": client_ip,
        "user_id": user_id
    }
    log_event("API_REQUEST", level, f"HTTP {method} {path} - {status_code} ({metadata['duration_ms']}ms)", metadata)

def log_auth_event(event_name: str, email: str, success: bool, details: str = None, client_ip: str = None):
    """Logs structured Authentication and Authorization events."""
    level = logging.INFO if success else logging.WARNING
    metadata = {
        "auth_event": event_name,
        "email": email,
        "success": success,
        "details": details,
        "client_ip": client_ip or (request.remote_addr if request else "N/A")
    }
    log_event("AUTHENTICATION", level, f"Auth Event '{event_name}' for {email}: {'SUCCESS' if success else 'FAILED'}", metadata)

def log_job_event(job_id: str, job_name: str, status: str, progress: int = 0, error: str = None):
    """Logs structured Background Asynchronous Job telemetries."""
    level = logging.ERROR if status == "FAILED" else logging.INFO
    metadata = {
        "job_id": job_id,
        "job_name": job_name,
        "status": status,
        "progress_pct": progress,
        "error": error
    }
    log_event("BACKGROUND_JOB", level, f"Background Job [{job_id}] '{job_name}': Status={status} ({progress}%)", metadata)

def log_error_event(error_name: str, message: str, traceback_str: str = None, context: dict = None):
    """Logs structured Exception and System Error events."""
    metadata = {
        "error_name": error_name,
        "details": message,
        "traceback": traceback_str,
        "context": context or {}
    }
    log_event("SYSTEM_ERROR", logging.ERROR, f"Exception Caught: {error_name} - {message}", metadata)

def get_health_metrics() -> dict:
    """Collects and returns structured system health & resource utilization metrics."""
    try:
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        cpu_pct = psutil.cpu_percent(interval=None)
        
        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "HEALTHY",
            "process_id": os.getpid(),
            "cpu_usage_pct": cpu_pct,
            "memory_rss_bytes": mem_info.rss,
            "memory_rss_mb": round(mem_info.rss / (1024 * 1024), 2),
            "thread_count": process.num_threads(),
            "open_files": len(process.open_files()) if hasattr(process, 'open_files') else 0
        }
    except Exception as e:
        return {
            "status": "DEGRADED",
            "error": str(e)
        }

def log_health_metrics():
    """Logs structured health metrics snapshot."""
    metrics = get_health_metrics()
    log_event("HEALTH_METRICS", logging.INFO, f"Health Metrics: CPU={metrics.get('cpu_usage_pct')}%, RAM={metrics.get('memory_rss_mb')}MB", metrics)
