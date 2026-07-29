import requests
import unittest
import time
import json

class TestAPISuiteComprehensive(unittest.TestCase):
    """Comprehensive API Test Suite verifying Success, Validation, Authentication, Authorization, & Errors across endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.base_url = "http://127.0.0.1:5000"
        
        # Admin User Setup
        cls.admin_email = f"api_admin_{int(time.time())}@system.local"
        cls.admin_pwd = "password123!"
        requests.post(f"{cls.base_url}/api/v2/auth/register", json={"email": cls.admin_email, "password": cls.admin_pwd, "role": "Admin"})
        res = requests.post(f"{cls.base_url}/api/v2/auth/login", json={"email": cls.admin_email, "password": cls.admin_pwd})
        cls.admin_token = res.json()['access_token']
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}", "Content-Type": "application/json"}
        
        # Viewer User Setup for RBAC checks
        cls.viewer_email = f"api_viewer_{int(time.time())}@system.local"
        cls.viewer_pwd = "password123!"
        requests.post(f"{cls.base_url}/api/v2/auth/register", json={"email": cls.viewer_email, "password": cls.viewer_pwd, "role": "Viewer"})
        res = requests.post(f"{cls.base_url}/api/v2/auth/login", json={"email": cls.viewer_email, "password": cls.viewer_pwd})
        cls.viewer_token = res.json()['access_token']
        cls.viewer_headers = {"Authorization": f"Bearer {cls.viewer_token}", "Content-Type": "application/json"}

    # 1. AUTHENTICATION (401 Unauthorized) TESTS
    def test_auth_unauthorized_access(self):
        """Unauthenticated requests must be rejected with 401 Unauthorized."""
        endpoints = [
            "/api/v2/audit-logs",
            "/api/v2/command-center/telemetry",
            "/api/v2/rules",
            "/api/v2/investigations",
            "/api/v2/jobs"
        ]
        for ep in endpoints:
            res = requests.get(f"{self.base_url}{ep}")
            self.assertEqual(res.status_code, 401, f"Expected 401 for unauthenticated request to {ep}")

    # 2. AUTHORIZATION (403 Forbidden RBAC) TESTS
    def test_rbac_forbidden_access(self):
        """Viewer role attempting to create rules must receive 403 Forbidden."""
        res = requests.post(
            f"{self.base_url}/api/v2/rules",
            json={"rule_name": "Test", "rule_key": "test_key", "category": "General", "impact_score": 10},
            headers=self.viewer_headers
        )
        self.assertEqual(res.status_code, 403, "Expected 403 Forbidden for Viewer role creating rules")

    # 3. VALIDATION (400 Bad Request) TESTS
    def test_validation_bad_request(self):
        """Missing or malformed parameters must trigger 400 Bad Request."""
        # Missing login credentials
        res = requests.post(f"{self.base_url}/api/v2/auth/login", json={})
        self.assertEqual(res.status_code, 400)
        
        # Missing required report parameters
        res = requests.post(f"{self.base_url}/api/v2/reports/generate", json={}, headers=self.admin_headers)
        self.assertEqual(res.status_code, 400)

    # 4. SUCCESS & ENDPOINT FUNCTIONALITY TESTS
    def test_endpoint_health(self):
        res = requests.get(f"{self.base_url}/api/v2/health")
        self.assertEqual(res.status_code, 200)

    def test_endpoint_auth_me(self):
        res = requests.get(f"{self.base_url}/api/v2/auth/me", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

    def test_endpoint_analytics_telemetry(self):
        res = requests.get(f"{self.base_url}/api/v2/analytics/telemetry", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

    def test_endpoint_command_center_telemetry(self):
        res = requests.get(f"{self.base_url}/api/v2/command-center/telemetry", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

    def test_endpoint_search(self):
        res = requests.get(f"{self.base_url}/api/v2/search?query=Tech", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

    def test_endpoint_audit_logs(self):
        res = requests.get(f"{self.base_url}/api/v2/audit-logs", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

    def test_endpoint_rules_list(self):
        res = requests.get(f"{self.base_url}/api/v2/rules", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

    def test_endpoint_investigations_list(self):
        res = requests.get(f"{self.base_url}/api/v2/investigations", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

    def test_endpoint_jobs_list(self):
        res = requests.get(f"{self.base_url}/api/v2/jobs", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

    def test_endpoint_notifications_list(self):
        res = requests.get(f"{self.base_url}/api/v2/notifications", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

    def test_endpoint_predictions_alerts(self):
        res = requests.get(f"{self.base_url}/api/v2/predictions/alerts", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

def run_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestAPISuiteComprehensive)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("API test suite failed.")

if __name__ == '__main__':
    run_tests()
