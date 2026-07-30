import unittest
import time
from app import create_app
from src.domain.services.ocr_engine import OcrEngine
from src.domain.services.anomaly_engine import AnomalyDetectionEngine
from src.domain.services.reputation_engine import ReputationIntelligenceEngine
from src.domain.services.recommendation_engine import RecommendationEngine
from src.infrastructure.async_jobs.background_job_service import BackgroundJobService
from src.infrastructure.cache.cache_service import MemoryCacheService

class TestComprehensiveServicesUnit(unittest.TestCase):
    """Comprehensive unit test suite expanding test coverage across core domain services and infrastructure."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.pop()

    # 1. OCR ENGINE UNIT TESTS
    def test_ocr_process_document_not_found(self):
        result = OcrEngine.process_document(doc_id=99999)
        self.assertFalse(result['success'])

    def test_ocr_process_document(self):
        result = OcrEngine.process_document(doc_id=1)
        self.assertIn('success', result)

    # 2. ANOMALY ENGINE UNIT TESTS
    def test_anomaly_engine_scan_vendor(self):
        result = AnomalyDetectionEngine.execute_scan()
        self.assertIn('success', result)

    # 3. REPUTATION ENGINE UNIT TESTS
    def test_reputation_engine_calculate(self):
        from src.infrastructure.database.models import Vendor
        v = Vendor.query.first()
        v_id = v.id if v else 1
        result = ReputationIntelligenceEngine.calculate_reputation(vendor_id=v_id)
        self.assertTrue(result['success'])
        self.assertIn('reputation', result)
        self.assertIn('reputation_score', result['reputation'])
        self.assertGreaterEqual(result['reputation']['reputation_score'], 0.0)

    # 4. RECOMMENDATION ENGINE UNIT TESTS
    def test_recommendation_engine_generate(self):
        result = RecommendationEngine.generate_recommendations(vendor_id=1)
        self.assertIsInstance(result, list)

    # 5. CACHE SERVICE UNIT TESTS
    def test_cache_service_set_get_expire_evict(self):
        cache = MemoryCacheService()
        cache.set("key1", "val1", ttl=60)
        self.assertEqual(cache.get("key1"), "val1")
        
        cache.clear()
        self.assertIsNone(cache.get("key1"))

    # 6. BACKGROUND JOB SERVICE UNIT TESTS
    def test_background_job_service_submit_and_poll(self):
        job_service = BackgroundJobService()
        
        def dummy_job(progress_callback=None):
            if progress_callback:
                progress_callback(50, "Halfway done")
            return {"result": "success"}

        job_id = job_service.submit_job("Dummy Job", dummy_job)
        self.assertIsNotNone(job_id)
        
        status = job_service.get_job_status(job_id)
        self.assertIsInstance(status.get('status'), str)

    # 7. HEALTH PROBE ENDPOINTS UNIT TESTS
    def test_health_endpoints_probe(self):
        client = self.app.test_client()
        res_full = client.get('/api/v2/health')
        self.assertEqual(res_full.status_code, 200)
        data = res_full.get_json()
        self.assertEqual(data['status'], 'HEALTHY')
        self.assertIn('application', data['components'])
        self.assertIn('database', data['components'])
        self.assertIn('cache', data['components'])
        self.assertIn('background_jobs', data['components'])

        res_live = client.get('/api/v2/health/liveness')
        self.assertEqual(res_live.status_code, 200)
        self.assertEqual(res_live.get_json()['status'], 'UP')

        res_ready = client.get('/api/v2/health/readiness')
        self.assertEqual(res_ready.status_code, 200)
        self.assertEqual(res_ready.get_json()['status'], 'READY')

if __name__ == '__main__':
    unittest.main()
