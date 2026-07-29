import unittest
from app import create_app
from src.domain.services.trust_engine import TrustEngine

class TestTrustEngineUnit(unittest.TestCase):
    """Isolated unit test suite for TrustEngine score calculation logic."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.pop()

    def test_calculate_vendor_trust_vendor_not_found(self):
        result = TrustEngine.calculate_vendor_trust(vendor_id=99999)
        self.assertFalse(result['success'])
        self.assertIn('not found', result['message'].lower())

    def test_calculate_vendor_trust_success(self):
        result = TrustEngine.calculate_vendor_trust(vendor_id=1)
        self.assertTrue(result['success'])
        self.assertIn('trust_result', result)
        score = result['trust_result']['trust_score']
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

if __name__ == '__main__':
    unittest.main()
