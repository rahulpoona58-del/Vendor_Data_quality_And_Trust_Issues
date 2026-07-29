from datetime import datetime
from src.infrastructure.database.models import BusinessRule, Vendor, VendorDocument, OcrResult, db
from src.infrastructure.database.models import VendorComplianceStatus, FraudCheck
import logging

class BusinessRulesEngine:
    """Configurable logic evaluator that resolves facts and applies actions recursively."""
    
    @staticmethod
    def resolve_facts(vendor_id: int) -> dict:
        """Assembles diagnostic state parameters (Facts) for a given vendor."""
        facts = {
            'gst_missing': True,
            'pan_missing': True,
            'trust_score': 50.0,
            'compliance_score': 50.0,
            'fraud_score': 0.0,
            'has_fraud_alert': False,
            'days_until_expiry': 999
        }
        
        try:
            vendor = Vendor.query.get(vendor_id)
            if not vendor:
                return facts
                
            facts['trust_score'] = vendor.trust_score
            
            # Check docs
            docs = VendorDocument.query.filter_by(vendor_id=vendor_id, is_deleted=False).all()
            now = datetime.utcnow()
            
            for doc in docs:
                if doc.document_type == 'GST Certificate' and doc.verification_status == 'Verified':
                    facts['gst_missing'] = False
                elif doc.document_type == 'PAN Card' and doc.verification_status == 'Verified':
                    facts['pan_missing'] = False
                    
                if doc.expiry_date:
                    days = (doc.expiry_date - now).days
                    if days < facts['days_until_expiry']:
                        facts['days_until_expiry'] = max(0, days)
                        
            # Check compliance
            comp = VendorComplianceStatus.query.filter_by(vendor_id=vendor_id).first()
            if comp:
                facts['compliance_score'] = comp.compliance_score
                
            # Check fraud
            fraud = FraudCheck.query.filter_by(vendor_id=vendor_id).first()
            if fraud:
                facts['fraud_score'] = fraud.fraud_score
                facts['has_fraud_alert'] = fraud.status == 'Alert'
                
        except Exception as e:
            logging.error(f"Error resolving rule engine facts: {str(e)}")
            
        return facts

    @staticmethod
    def evaluate_condition(condition: dict, facts: dict) -> bool:
        """Recursively parses a rule condition JSON block against resolved facts."""
        if not condition or not isinstance(condition, dict):
            return False
            
        operator = condition.get('operator', '').upper()
        
        # Logical operations (AND, OR, NOT)
        if operator == 'AND':
            rules = condition.get('rules', [])
            if not rules:
                return False
            return all(BusinessRulesEngine.evaluate_condition(r, facts) for r in rules)
            
        elif operator == 'OR':
            rules = condition.get('rules', [])
            if not rules:
                return False
            return any(BusinessRulesEngine.evaluate_condition(r, facts) for r in rules)
            
        elif operator == 'NOT':
            rule = condition.get('rule')
            if not rule:
                return False
            return not BusinessRulesEngine.evaluate_condition(rule, facts)
            
        # Leaf operations (fact comparison)
        fact = condition.get('fact')
        if fact:
            val = facts.get(fact)
            target = condition.get('value')
            comp = condition.get('comparator', 'eq').lower()
            
            if val is None:
                return False
                
            if comp == 'eq':
                return val == target
            elif comp == 'neq':
                return val != target
            elif comp == 'gt':
                return float(val) > float(target)
            elif comp == 'lt':
                return float(val) < float(target)
            elif comp == 'gte':
                return float(val) >= float(target)
            elif comp == 'lte':
                return float(val) <= float(target)
                
        return False

    @staticmethod
    def evaluate_rules(vendor_id: int, rule_group: str) -> list:
        """Resolves vendor facts, executes matching rules in sequence order, and compiles actions."""
        try:
            rules = BusinessRule.query.filter_by(rule_group=rule_group, is_enabled=True)\
                                      .order_by(BusinessRule.priority.asc()).all()
            if not rules:
                return []
                
            facts = BusinessRulesEngine.resolve_facts(vendor_id)
            actions = []
            
            for rule in rules:
                is_match = BusinessRulesEngine.evaluate_condition(rule.conditions_json, facts)
                if is_match:
                    actions.append({
                        'rule_id': rule.id,
                        'rule_name': rule.name,
                        'action': rule.actions_json
                    })
                    logging.info(f"Business Rule matched: {rule.name} (Group: {rule_group}) on Vendor ID {vendor_id}")
            return actions
        except Exception as e:
            logging.error(f"Rule evaluation failed: {str(e)}")
            return []

    @staticmethod
    def simulate_rule(vendor_id: int, rule_id: int) -> dict:
        """Mocks fact evaluation and returns the simulated actions outcome."""
        try:
            rule = BusinessRule.query.get(rule_id)
            if not rule:
                return {'success': False, 'message': 'Rule not found'}
                
            facts = BusinessRulesEngine.resolve_facts(vendor_id)
            is_match = BusinessRulesEngine.evaluate_condition(rule.conditions_json, facts)
            
            return {
                'success': True,
                'is_match': is_match,
                'resolved_facts': facts,
                'rule_name': rule.name,
                'actions': rule.actions_json if is_match else None
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}
