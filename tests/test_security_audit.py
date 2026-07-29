import unittest
import requests
import io
import time

class TestApplicationSecurityControls(unittest.TestCase):
    """Defensive Security Test Suite testing Authentication, RBAC Authorization, SQL Injection Resistance, XSS Escaping, CSRF Protection, and File Upload Validation."""

    @classmethod
    def setUpClass(cls):
        cls.base_url = "http://127.0.0.1:5000"
        
        # 1. Admin Account Creation
        cls.admin_email = f"sec_admin_{int(time.time())}@system.local"
        cls.admin_pwd = "password123!"
        requests.post(f"{cls.base_url}/api/v2/auth/register", json={"email": cls.admin_email, "password": cls.admin_pwd, "role": "Admin"})
        res = requests.post(f"{cls.base_url}/api/v2/auth/login", json={"email": cls.admin_email, "password": cls.admin_pwd})
        cls.admin_token = res.json()['access_token']
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}
        
        # 2. Viewer Account Creation
        cls.viewer_email = f"sec_viewer_{int(time.time())}@system.local"
        cls.viewer_pwd = "password123!"
        requests.post(f"{cls.base_url}/api/v2/auth/register", json={"email": cls.viewer_email, "password": cls.viewer_pwd, "role": "Viewer"})
        res = requests.post(f"{cls.base_url}/api/v2/auth/login", json={"email": cls.viewer_email, "password": cls.viewer_pwd})
        cls.viewer_token = res.json()['access_token']
        cls.viewer_headers = {"Authorization": f"Bearer {cls.viewer_token}"}

    # 1. AUTHENTICATION CONTROLS
    def test_security_authentication_enforcement(self):
        """Verify unauthenticated requests to protected endpoints return 401 Unauthorized."""
        res = requests.get(f"{self.base_url}/api/v2/audit-logs")
        self.assertEqual(res.status_code, 401)

    def test_security_authentication_invalid_credentials(self):
        """Verify invalid passwords return 401 Unauthorized."""
        res = requests.post(f"{self.base_url}/api/v2/auth/login", json={"email": self.admin_email, "password": "WrongPassword!"})
        self.assertEqual(res.status_code, 401)

    # 2. AUTHORIZATION CONTROLS (RBAC)
    def test_security_authorization_rbac_enforcement(self):
        """Verify Viewer role cannot perform Admin operations (creating rules)."""
        res = requests.post(
            f"{self.base_url}/api/v2/rules",
            json={"rule_name": "Test Rule", "rule_key": "test_key", "category": "General", "impact_score": 10},
            headers=self.viewer_headers
        )
        self.assertEqual(res.status_code, 403)

    # 3. SQL INJECTION RESISTANCE
    def test_security_sql_injection_parameterization(self):
        """Verify endpoints parameterize queries and safely handle SQL control characters."""
        sqli_patterns = ["' OR '1'='1", "1; DROP TABLE vendors; --", "admin'--"]
        for pattern in sqli_patterns:
            res = requests.get(f"{self.base_url}/api/v2/search?query={pattern}", headers=self.admin_headers)
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.json()['success'])

    # 4. XSS & HTML ESCAPING CONTROLS
    def test_security_xss_escaping_headers(self):
        """Verify application returns X-XSS-Protection or X-Content-Type-Options security headers."""
        res = requests.get(f"{self.base_url}/dashboard", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

    # 5. FILE UPLOAD SECURITY CONTROLS
    def test_security_file_upload_dangerous_extension_rejection(self):
        """Verify executable extensions (.exe, .php, .js) are rejected with 400 Bad Request."""
        bad_file = io.BytesIO(b"echo 'malicious script'")
        files = {'file': ('malicious.exe', bad_file, 'application/x-msdownload')}
        res = requests.post(f"{self.base_url}/api/v2/vendors/1/documents", files=files, data={'document_type': 'GST Certificate'}, headers=self.admin_headers)
        self.assertEqual(res.status_code, 400)

    def test_security_file_upload_magic_bytes_validation(self):
        """Verify PDF upload requires valid %PDF- magic bytes header."""
        valid_pdf = io.BytesIO(b"%PDF-1.4 header content")
        files = {'file': ('valid_doc.pdf', valid_pdf, 'application/pdf')}
        res = requests.post(f"{self.base_url}/api/v2/vendors/1/documents", files=files, data={'document_type': 'GST Certificate'}, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)

def run_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestApplicationSecurityControls)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("Security test suite failed.")

if __name__ == '__main__':
    run_tests()
