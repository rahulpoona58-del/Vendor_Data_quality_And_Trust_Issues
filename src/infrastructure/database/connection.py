from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def init_db(app):
    """Initializes the database and migration utilities with the Flask application context."""
    db.init_app(app)
    migrate.init_app(app, db)
    
    with app.app_context():
        # Imports models to register schemas for migrations
        from . import models
        db.create_all()
