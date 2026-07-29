import unittest
from app import create_app
from src.domain.services.fraud_engine import FraudEngine

class TestFraudEngineUnit(unittest.TestCase):
    """Isolated unit test suite for FraudEngine analysis routines."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.pop()

    def test_execute_scan_vendor_not_found(self):
        result = FraudEngine.execute_scan(vendor_id=99999)
        self.assertFalse(result['success'])
        self.assertIn('not found', result['message'].lower())

    def test_execute_scan_clean_vendor(self):
        result = FraudEngine.execute_scan(vendor_id=1)
        self.assertTrue(result['success'])
        self.assertIn('fraud_check', result)

if __name__ == '__main__':
    unittest.main()
