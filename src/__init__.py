import os
import time
import uuid
import traceback
from flask import Flask, request, jsonify, g
from src.config import get_config
from src.infrastructure.logging.logger import setup_logging, log_api_request, log_error_event
from src.infrastructure.database.connection import init_db

def create_app():
    """Application Factory to initialize configs, database, logs, blueprints, and request telemetry."""
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    
    # Load configuration settings
    config = get_config()
    app.config.from_object(config)
    
    # Initialize centralized structured logging
    setup_logging(config)
    
    # Request Telemetry Middleware
    @app.before_request
    def before_request_telemetry():
        g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        g.start_time = time.time()

    @app.after_request
    def after_request_telemetry(response):
        # Calculate request latency in milliseconds
        if hasattr(g, 'start_time'):
            duration_ms = (time.time() - g.start_time) * 1000
            user_id = getattr(g, 'user_id', None)
            log_api_request(
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_ip=request.remote_addr or '127.0.0.1',
                user_id=user_id
            )
        response.headers['X-Request-ID'] = getattr(g, 'request_id', '')
        return response

    @app.errorhandler(Exception)
    def handle_unhandled_exception(err):
        tb_str = traceback.format_exc()
        log_error_event(
            error_name=err.__class__.__name__,
            message=str(err),
            traceback_str=tb_str,
            context={"path": request.path, "method": request.method}
        )
        if request.path.startswith('/api/'):
            return jsonify({"success": False, "message": "Internal Server Error", "request_id": getattr(g, 'request_id', None)}), 500
        raise err

    # Initialize database models & migrate hooks
    init_db(app)
    
    # Auto-seed database tables
    with app.app_context():
        from src.infrastructure.database.seeder import seed_database
        seed_database(app.config['CSV_DATA_PATH'])
    
    # Ensure secure file storage directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Start WebSocket Event Server (Background Task Gateway)
    from src.domain.services.event_queue import EventQueue
    EventQueue.start_realtime_server(port=5001)
    
    # Initialize SQLAlchemy ORM Event Listeners
    from src.infrastructure.realtime.event_listeners import setup_event_listeners
    setup_event_listeners()
    
    # Register REST API blueprints
    from src.presentation.api.auth_api import auth_api
    from src.presentation.api.document_api import document_api
    from src.presentation.api.ocr_api import ocr_api
    from src.presentation.api.cleaning_api import cleaning_api
    from src.presentation.api.trust_api import trust_api
    from src.presentation.api.fraud_api import fraud_api
    from src.presentation.api.compliance_api import compliance_api
    from src.presentation.api.timeline_api import timeline_api
    from src.presentation.api.notification_api import notification_api
    from src.presentation.api.recommendation_api import recommendation_api
    from src.presentation.api.analytics_api import analytics_api
    from src.presentation.api.audit_api import audit_api
    from src.presentation.api.rules_api import rules_api
    from src.presentation.api.search_api import search_api
    from src.presentation.api.copilot_api import copilot_api
    from src.presentation.api.prediction_api import prediction_api
    from src.presentation.api.health_api import health_api
    from src.presentation.api.report_api import report_api
    from src.presentation.api.workflow_api import workflow_api
    from src.presentation.api.anomaly_api import anomaly_api
    from src.presentation.api.reputation_api import reputation_api
    from src.presentation.api.simulation_api import simulation_api
    from src.presentation.api.investigation_api import investigation_api
    from src.presentation.api.agent_api import agent_api
    from src.presentation.api.command_center_api import command_center_api
    from src.presentation.api.semantic_search_api import semantic_search_api
    from src.presentation.api.jobs_api import jobs_api
    from src.presentation.api.docs_api import docs_api
    from src.presentation.api.demo_api import demo_api
    
    app.register_blueprint(auth_api)
    app.register_blueprint(document_api)
    app.register_blueprint(ocr_api)
    app.register_blueprint(cleaning_api)
    app.register_blueprint(trust_api)
    app.register_blueprint(fraud_api)
    app.register_blueprint(compliance_api)
    app.register_blueprint(timeline_api)
    app.register_blueprint(notification_api)
    app.register_blueprint(recommendation_api)
    app.register_blueprint(analytics_api)
    app.register_blueprint(audit_api)
    app.register_blueprint(rules_api)
    app.register_blueprint(search_api)
    app.register_blueprint(copilot_api)
    app.register_blueprint(prediction_api)
    app.register_blueprint(health_api)
    app.register_blueprint(report_api)
    app.register_blueprint(workflow_api)
    app.register_blueprint(anomaly_api)
    app.register_blueprint(reputation_api)
    app.register_blueprint(simulation_api)
    app.register_blueprint(investigation_api)
    app.register_blueprint(agent_api)
    app.register_blueprint(command_center_api)
    app.register_blueprint(semantic_search_api)
    app.register_blueprint(jobs_api)
    app.register_blueprint(docs_api)
    app.register_blueprint(demo_api)
    
    # Security Response Headers & CSRF Context Processor
    from src.infrastructure.security.csrf import generate_csrf_token, add_security_headers
    app.after_request(add_security_headers)
    
    @app.context_processor
    def inject_csrf():
        return dict(csrf_token=generate_csrf_token)
        
    return app
