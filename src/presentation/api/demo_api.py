import os
import shutil
from flask import Blueprint, jsonify, current_app
from pathlib import Path
from scripts.seed_demo_dataset import seed_demo_dataset, DEMO_DB_PATH

demo_api = Blueprint('demo_api', __name__)

@demo_api.route('/api/v2/demo/setup', methods=['POST'])
def setup_demo():
    """One-click API endpoint initializing and populating isolated demo dataset."""
    try:
        seed_demo_dataset()
        return jsonify({
            "success": True,
            "message": "Demo Mode setup completed successfully!",
            "database_path": str(DEMO_DB_PATH),
            "sample_users": [
                {"email": "admin@demo.local", "role": "Admin"},
                {"email": "manager@demo.local", "role": "Manager"},
                {"email": "auditor@demo.local", "role": "Auditor"},
                {"email": "analyst@demo.local", "role": "Analyst"},
                {"email": "viewer@demo.local", "role": "Viewer"}
            ]
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": f"Demo setup failed: {str(e)}"}), 500

@demo_api.route('/api/v2/demo/reset', methods=['POST'])
def reset_demo():
    """One-click API endpoint resetting demo data back to baseline state without affecting production."""
    try:
        if DEMO_DB_PATH.exists():
            os.remove(DEMO_DB_PATH)
        seed_demo_dataset()
        return jsonify({
            "success": True,
            "message": "Demo database has been cleanly reset to initial state!"
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": f"Demo reset failed: {str(e)}"}), 500

@demo_api.route('/api/v2/demo/status', methods=['GET'])
def get_demo_status():
    """Returns current demo dataset status and statistics."""
    exists = DEMO_DB_PATH.exists()
    return jsonify({
        "demo_mode_active": exists,
        "demo_db_path": str(DEMO_DB_PATH),
        "db_size_bytes": DEMO_DB_PATH.stat().st_size if exists else 0
    }), 200
