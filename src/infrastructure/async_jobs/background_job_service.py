import uuid
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

class BackgroundJobService:
    """Asynchronous ThreadPool-backed Background Job Manager supporting progress tracking and safe retries."""
    _jobs = {}
    _lock = threading.RLock()
    _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bg_worker")

    @classmethod
    def submit_job(cls, job_type: str, target_fn, args=(), kwargs=None, max_retries: int = 3) -> str:
        """Enqueues a task for background execution, returning a unique job_id."""
        kwargs = kwargs or {}
        job_id = str(uuid.uuid4())
        
        job_record = {
            'job_id': job_id,
            'job_type': job_type,
            'status': 'Queued',
            'progress': 0,
            'result': None,
            'error': None,
            'retries': 0,
            'max_retries': max_retries,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        with cls._lock:
            cls._jobs[job_id] = job_record
            
        cls._executor.submit(cls._run_job_wrapper, job_id, target_fn, args, kwargs)
        from src.infrastructure.logging.logger import log_job_event
        log_job_event(job_id, job_type, "QUEUED", progress=0)
        return job_id

    @classmethod
    def _run_job_wrapper(cls, job_id: str, target_fn, args, kwargs):
        """Wrapper handling progress updates, execution, exception tracking, and safe retries."""
        from src.infrastructure.logging.logger import log_job_event
        with cls._lock:
            if job_id not in cls._jobs:
                return
            job = cls._jobs[job_id]
            job['status'] = 'Processing'
            job['progress'] = 10
            job['updated_at'] = datetime.utcnow().isoformat()

        def update_progress(pct: int, msg: str = None):
            with cls._lock:
                if job_id in cls._jobs:
                    cls._jobs[job_id]['progress'] = max(0, min(100, pct))
                    cls._jobs[job_id]['updated_at'] = datetime.utcnow().isoformat()
                    log_job_event(job_id, job['job_type'], "RUNNING", progress=pct)

        try:
            # Pass progress callback if function accepts it
            result = target_fn(*args, progress_callback=update_progress, **kwargs) if 'progress_callback' in target_fn.__code__.co_varnames else target_fn(*args, **kwargs)
            
            with cls._lock:
                if job_id in cls._jobs:
                    cls._jobs[job_id]['status'] = 'Completed'
                    cls._jobs[job_id]['progress'] = 100
                    cls._jobs[job_id]['result'] = result
                    cls._jobs[job_id]['updated_at'] = datetime.utcnow().isoformat()
            log_job_event(job_id, job['job_type'], "COMPLETED", progress=100)
        except Exception as e:
            with cls._lock:
                if job_id in cls._jobs:
                    job = cls._jobs[job_id]
                    job['retries'] += 1
                    if job['retries'] <= job['max_retries']:
                        job['status'] = f"Retrying ({job['retries']}/{job['max_retries']})"
                        job['error'] = str(e)
                        job['updated_at'] = datetime.utcnow().isoformat()
                        log_job_event(job_id, job['job_type'], "RETRYING", progress=job['progress'], error=str(e))
                        cls._executor.submit(cls._run_job_wrapper, job_id, target_fn, args, kwargs)
                    else:
                        job['status'] = 'Failed'
                        job['error'] = str(e)
                        job['updated_at'] = datetime.utcnow().isoformat()
                        log_job_event(job_id, job['job_type'], "FAILED", progress=job['progress'], error=str(e))

    @classmethod
    def get_job_status(cls, job_id: str) -> dict:
        """Retrieves current execution status and progress metadata for a given job_id."""
        with cls._lock:
            if job_id in cls._jobs:
                return dict(cls._jobs[job_id])
            return {'success': False, 'message': f"Job '{job_id}' not found."}

    @classmethod
    def list_jobs(cls, limit: int = 50) -> list:
        """Lists recent background jobs."""
        with cls._lock:
            sorted_jobs = sorted(cls._jobs.values(), key=lambda j: j['created_at'], reverse=True)
            return sorted_jobs[:limit]
