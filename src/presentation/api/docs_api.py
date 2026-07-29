from flask import Blueprint, render_template_string, jsonify, send_from_directory
import os

docs_api = Blueprint('docs_api', __name__)

SWAGGER_UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Vendor Trust Platform - API Documentation (Swagger UI)</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.18.3/swagger-ui.css" />
  <style>
    body { margin: 0; padding: 0; background: #0f172a; }
    .swagger-ui { filter: invert(88%) hue-rotate(180deg); }
    .swagger-ui .topbar { display: none; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.18.3/swagger-ui-bundle.js"></script>
  <script>
    window.onload = () => {
      window.ui = SwaggerUIBundle({
        url: '/static/openapi.json',
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
      });
    };
  </script>
</body>
</html>
"""

@docs_api.route('/api/v2/docs', methods=['GET'])
def swagger_ui():
    """Renders interactive Swagger UI documentation."""
    return render_template_string(SWAGGER_UI_HTML)

@docs_api.route('/api/v2/docs/openapi.json', methods=['GET'])
def get_openapi_spec():
    """Serves raw OpenAPI 3.0.3 JSON specification."""
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'static')
    return send_from_directory(static_dir, 'openapi.json')
