import re
import functools
from flask import request, jsonify

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
GST_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")

class Validator:
    """Reusable validation utilities ensuring strict input boundary integrity."""
    
    @staticmethod
    def is_email(val: str) -> bool:
        if not val or not isinstance(val, str):
            return False
        return bool(EMAIL_REGEX.match(val.strip()))

    @staticmethod
    def is_gst(val: str) -> bool:
        if not val or not isinstance(val, str):
            return False
        return bool(GST_REGEX.match(val.strip().upper()))

    @staticmethod
    def is_pan(val: str) -> bool:
        if not val or not isinstance(val, str):
            return False
        return bool(PAN_REGEX.match(val.strip().upper()))

    @staticmethod
    def parse_int(val, default=None, min_val=None, max_val=None):
        if val is None:
            return default
        try:
            parsed = int(val)
            if min_val is not None and parsed < min_val:
                return default
            if max_val is not None and parsed > max_val:
                return default
            return parsed
        except (ValueError, TypeError):
            return default

    @staticmethod
    def parse_float(val, default=None, min_val=None, max_val=None):
        if val is None:
            return default
        try:
            parsed = float(val)
            if min_val is not None and parsed < min_val:
                return default
            if max_val is not None and parsed > max_val:
                return default
            return parsed
        except (ValueError, TypeError):
            return default

    @staticmethod
    def validate_payload(data: dict, required_fields: list = None, field_rules: dict = None) -> tuple:
        """Evaluates payload against required fields and rule checks. Returns (is_valid, errors_list)."""
        errors = []
        if not isinstance(data, dict):
            return False, [{'field': 'body', 'message': 'Malformed JSON payload expected'}]
            
        if required_fields:
            for field in required_fields:
                val = data.get(field)
                if val is None or (isinstance(val, str) and not val.strip()):
                    errors.append({'field': field, 'message': f"Field '{field}' is required and cannot be empty"})
                    
        if field_rules and isinstance(field_rules, dict):
            for field, rules in field_rules.items():
                val = data.get(field)
                if val is None and rules.get('required'):
                    continue # Handled above
                if val is not None:
                    if rules.get('type') == 'email' and not Validator.is_email(val):
                        errors.append({'field': field, 'message': f"Field '{field}' must be a valid email address"})
                    elif rules.get('type') == 'int':
                        parsed = Validator.parse_int(val, min_val=rules.get('min'), max_val=rules.get('max'))
                        if parsed is None:
                            errors.append({'field': field, 'message': f"Field '{field}' must be an integer within bounds"})
                    elif rules.get('type') == 'enum' and val not in rules.get('allowed', []):
                        errors.append({'field': field, 'message': f"Field '{field}' must be one of {rules.get('allowed')}"})
                        
        return len(errors) == 0, errors

def validate_request(required_fields: list = None, field_rules: dict = None):
    """Decorator to enforce strict input validation on JSON API routes."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if request.method in ['POST', 'PUT', 'PATCH']:
                data = request.get_json(silent=True)
                if data is None and request.content_length and request.content_length > 0 and not request.files:
                    return jsonify({
                        'success': False,
                        'message': 'Malformed JSON payload',
                        'errors': [{'field': 'body', 'message': 'Invalid or unparseable JSON format'}]
                    }), 400
                    
                data = data or {}
                is_valid, errors = Validator.validate_payload(data, required_fields, field_rules)
                if not is_valid:
                    return jsonify({
                        'success': False,
                        'message': 'Input validation failed',
                        'errors': errors
                    }), 400
                    
            return f(*args, **kwargs)
        return wrapper
    return decorator
