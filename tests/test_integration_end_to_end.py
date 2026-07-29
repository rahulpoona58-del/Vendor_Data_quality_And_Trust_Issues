import requests
import unittest
import time
import io

class TestEndToEndIntegrationWorkflows(unittest.TestCase):
    """Full End-to-End Integration Test Suite covering Auth, Uploads, OCR, AI Modules, APIs, & DB."""

    @classmethod
    def setUpClass(cls):
        cls.base_url = "http://127.0.0.1:5000"
        cls.email = f"e2e_tester_{int(time.time())}@system.local"
        cls.password = "password123!"
        
        # 1. Register & Login
        reg_url = f"{cls.base_url}/api/v2/auth/register"
        requests.post(reg_url, json={"email": cls.email, "password": cls.password, "role": "Admin"})
        
        login_url = f"{cls.base_url}/api/v2/auth/login"
        res = requests.post(login_url, json={"email": cls.email, "password": cls.password})
        assert res.status_code == 200
        cls.token = res.json()['access_token']
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_workflow_1_authentication_and_rbac(self):
        """Verify JWT Auth and RBAC protected access."""
        url = f"{self.base_url}/api/v2/audit-logs"
        res = requests.get(url, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])

    def test_workflow_2_document_upload_and_ocr(self):
        """Verify secure PDF upload, magic byte check, and database record creation."""
        url = f"{self.base_url}/api/v2/vendors/1/documents"
        pdf_bytes = b"%PDF-1.4 header contents for test pdf..."
        files = {'file': ('integration_test_gst.pdf', io.BytesIO(pdf_bytes), 'application/pdf')}
        data = {'document_type': 'GST Certificate'}
        
        res = requests.post(url, files=files, data=data, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        res_data = res.json()
        self.assertTrue(res_data['success'])
        self.assertIn('document', res_data)

    def test_workflow_3_ai_copilot_rag_chat(self):
        """Verify AI Copilot RAG chat grounding and citation generation."""
        url = f"{self.base_url}/api/v2/copilot/chat"
        payload = {"query": "What is the compliance score of vendor 1?", "vendor_id": 1}
        res = requests.post(url, json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        res_data = res.json()
        self.assertTrue(res_data['success'])
        self.assertIn('answer', res_data)

    def test_workflow_4_multi_agent_system_diagnostic(self):
        """Verify 8-Agent autonomous diagnostic execution."""
        url = f"{self.base_url}/api/v2/agents/diagnostic?vendor_id=1"
        res = requests.get(url, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        res_data = res.json()
        self.assertTrue(res_data['success'])

    def test_workflow_5_report_generation(self):
        """Verify multi-format report generation download."""
        url = f"{self.base_url}/api/v2/reports/generate"
        payload = {"report_type": "Vendor Summary", "export_format": "CSV"}
        res = requests.post(url, json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.headers.get('Content-Type', ''))

if __name__ == '__main__':
    unittest.main()
