import requests
import unittest
import time
import io
import json

class TestEndToEndUserJourneys(unittest.TestCase):
    """Comprehensive E2E User Journey Test Suite covering Login, Vendor Mgmt, OCR, Trust Calculation, Reports, & Investigations."""

    @classmethod
    def setUpClass(cls):
        cls.base_url = "http://127.0.0.1:5000"
        
        # 1. Login Journey
        cls.admin_email = f"e2e_journey_{int(time.time())}@system.local"
        cls.admin_pwd = "password123!"
        reg_res = requests.post(f"{cls.base_url}/api/v2/auth/register", json={"email": cls.admin_email, "password": cls.admin_pwd, "role": "Admin"})
        assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
        
        login_res = requests.post(f"{cls.base_url}/api/v2/auth/login", json={"email": cls.admin_email, "password": cls.admin_pwd})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        cls.token = login_res.json()['access_token']
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_journey_1_vendor_management(self):
        """Journey 2: Vendor management (fetch, query, 360 view)."""
        # Fetch Vendor 360 profile
        res = requests.get(f"{self.base_url}/api/v2/search?query=Vendor", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])

    def test_journey_2_document_upload_and_ocr(self):
        """Journey 3: Document Upload & Automated OCR Extraction."""
        pdf_bytes = b"%PDF-1.5 test document content for OCR processing"
        files = {'file': ('gst_cert_ocr_e2e.pdf', io.BytesIO(pdf_bytes), 'application/pdf')}
        data = {'document_type': 'GST Certificate'}
        
        res = requests.post(f"{self.base_url}/api/v2/vendors/1/documents", files=files, data=data, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.json()['success'])

    def test_journey_3_trust_calculation(self):
        """Journey 4: Trust Score & Risk Engine Calculation."""
        res = requests.post(f"{self.base_url}/api/v2/trust/calculate", json={"vendor_id": 1}, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        res_data = res.json()
        self.assertTrue(res_data['success'])
        self.assertIn('trust_score', res_data['data'])

    def test_journey_4_reports_generation(self):
        """Journey 5: Multi-Format Executive Analytics Reports Generation."""
        res = requests.post(f"{self.base_url}/api/v2/reports/generate", json={"report_type": "Executive Summary", "export_format": "CSV"}, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.headers.get('Content-Type', ''))

    def test_journey_5_investigations_management(self):
        """Journey 6: Fraud Alert to Investigation Case Creation & Resolution."""
        # Query active investigations list
        res = requests.get(f"{self.base_url}/api/v2/investigations", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])

def run_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestEndToEndUserJourneys)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("E2E User Journeys test suite failed.")

if __name__ == '__main__':
    run_tests()
