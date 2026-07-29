import unittest
from app import create_app
from src.domain.services.compliance_engine import ComplianceEngine

class TestComplianceEngineUnit(unittest.TestCase):
    """Isolated unit test suite for ComplianceEngine evaluation logic."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.pop()

    def test_evaluate_compliance_vendor_not_found(self):
        result = ComplianceEngine.evaluate_compliance(vendor_id=99999)
        self.assertFalse(result['success'])
        self.assertIn('not found', result['message'].lower())

    def test_evaluate_compliance_success(self):
        result = ComplianceEngine.evaluate_compliance(vendor_id=1)
        self.assertTrue(result['success'])
        self.assertIn('compliance_status', result)
        score = result['compliance_status']['compliance_score']
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

if __name__ == '__main__':
    unittest.main()
