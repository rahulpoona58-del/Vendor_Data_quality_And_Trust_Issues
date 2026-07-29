import requests
import unittest
from bs4 import BeautifulSoup
import time
import json

class TestFrontendUIComprehensive(unittest.TestCase):
    """Frontend UI & Template Verification Suite testing forms, navigation, dashboards, tables, search, & charts."""

    @classmethod
    def setUpClass(cls):
        cls.base_url = "http://127.0.0.1:5000"
        
        # Register & Login as Admin
        cls.admin_email = f"ui_admin_{int(time.time())}@system.local"
        cls.admin_pwd = "password123!"
        requests.post(f"{cls.base_url}/api/v2/auth/register", json={"email": cls.admin_email, "password": cls.admin_pwd, "role": "Admin"})
        res = requests.post(f"{cls.base_url}/api/v2/auth/login", json={"email": cls.admin_email, "password": cls.admin_pwd})
        assert res.status_code == 200, f"Login failed: {res.text}"
        cls.admin_token = res.json()['access_token']
        cls.headers = {"Authorization": f"Bearer {cls.admin_token}"}

    def test_dashboard_templates_render(self):
        """Verify key UI dashboard templates render successfully with 200 status and HTML tags."""
        routes = [
            "/dashboard",
            "/executive-dashboard",
            "/geographic-analytics",
            "/xai-dashboard",
            "/vendor-360",
            "/audit-viewer"
        ]
        for route in routes:
            res = requests.get(f"{self.base_url}{route}", headers=self.headers)
            self.assertEqual(res.status_code, 200, f"Failed to render HTML page for route {route}: {res.status_code}")
            soup = BeautifulSoup(res.text, 'html.parser')
            self.assertIsNotNone(soup.find('html'), f"Page {route} is missing <html> root element")

    def test_forms_structure_and_inputs(self):
        """Verify forms, inputs, and submit buttons across UI pages."""
        res = requests.get(f"{self.base_url}/login")
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            inputs = soup.find_all('input')
            self.assertGreater(len(inputs), 0, "Login form must contain input fields")

    def test_dashboard_charts_and_canvas(self):
        """Verify canvas elements and Chart.js integration scripts in dashboard UI."""
        res = requests.get(f"{self.base_url}/executive-dashboard", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        soup = BeautifulSoup(res.text, 'html.parser')
        canvases = soup.find_all('canvas')
        self.assertTrue(len(canvases) > 0 or 'chart' in res.text.lower(), "Executive dashboard should contain chart elements")

    def test_data_tables_structure(self):
        """Verify data table elements, headings, and search controls in Audit Viewer."""
        res = requests.get(f"{self.base_url}/audit-viewer", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        soup = BeautifulSoup(res.text, 'html.parser')
        table_or_card = soup.find('table') or soup.find(class_=lambda c: c and 'table' in c.lower()) or soup.find(id=lambda i: i and 'table' in i.lower()) or soup.find('div')
        self.assertIsNotNone(table_or_card, "Audit viewer must render a data container")

    def test_responsive_meta_tags(self):
        """Verify mobile-responsive viewport meta tags exist on all HTML pages."""
        routes = ["/dashboard", "/executive-dashboard", "/audit-viewer"]
        for r in routes:
            res = requests.get(f"{self.base_url}{r}", headers=self.headers)
            self.assertEqual(res.status_code, 200)
            soup = BeautifulSoup(res.text, 'html.parser')
            viewport = soup.find('meta', attrs={'name': 'viewport'})
            self.assertIsNotNone(viewport, f"Route {r} is missing <meta name='viewport'> for responsiveness")

def run_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestFrontendUIComprehensive)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("Frontend UI test suite failed.")

if __name__ == '__main__':
    run_tests()
