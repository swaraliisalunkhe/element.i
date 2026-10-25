
import asyncio
import sys
import unittest
from pathlib import Path

# Add the project root so imports work from the sample_app directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sample_app.app import app, assessments


class ASGIClient:
    """Small dependency-free client for the GET route smoke tests."""

    def get(self, path):
        return asyncio.run(self._get(path))

    async def _get(self, path):
        body = bytearray()
        response = {"status_code": None, "headers": {}}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                response["status_code"] = message["status"]
                response["headers"] = dict(message.get("headers", []))
            elif message["type"] == "http.response.body":
                body.extend(message.get("body", b""))

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path.split("?", 1)[0],
            "raw_path": path.split("?", 1)[0].encode(),
            "query_string": path.split("?", 1)[1].encode()
            if "?" in path
            else b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "root_path": "",
        }

        await app(scope, receive, send)
        response["body"] = bytes(body)
        return response


client = ASGIClient()

class TestAppRoutes(unittest.TestCase):
    def test_home_page_loads(self):
        response = client.get("/")
        self.assertEqual(response["status_code"], 200)

    def test_assessments_page_loads(self):
        response = client.get("/assessments")
        self.assertEqual(response["status_code"], 200)

    def test_assessments_preserve_logged_in_candidate_identity(self):
        response = client.get(
            "/assessments?email=bob.candidate%40example.com"
        )
        self.assertEqual(response["status_code"], 200)
        html = response["body"].decode()
        self.assertIn("Bob Chen", html)
        self.assertIn(
            "/assessments/assessment-python-se/mcq?candidate_email=bob.candidate%40example.com",
            html,
        )
        self.assertIn(
            "/assessments/assessment-python-se/coding?candidate_email=bob.candidate%40example.com",
            html,
        )

    def test_dashboard_loads(self):
        response = client.get("/dashboard")
        self.assertEqual(response["status_code"], 200)

    def test_dashboard_assessment_links_preserve_logged_in_identity(self):
        response = client.get(
            "/dashboard?email=bob.candidate%40example.com"
        )
        self.assertEqual(response["status_code"], 200)
        html = response["body"].decode()
        self.assertIn(
            "/assessments?email=bob.candidate%40example.com",
            html,
        )

    def test_mcq_page_loads(self):
        response = client.get("/assessments/assessment-python-se/mcq")
        self.assertEqual(response["status_code"], 200)

    def test_coding_page_loads(self):
        response = client.get("/assessments/assessment-python-se/coding")
        self.assertEqual(response["status_code"], 200)

    def test_unknown_assessment_redirects(self):
        response = client.get(
            "/assessments/does-not-exist/mcq",
        )
        self.assertEqual(response["status_code"], 303)
        self.assertEqual(response["headers"][b"location"], b"/assessments")

    def test_both_coding_questions_are_rendered_for_both_assessments(self):
        for assessment_id in assessments:
            response = client.get(f"/assessments/{assessment_id}/coding")
            self.assertEqual(response["status_code"], 200)
            html = response["body"].decode()
            self.assertIn("prob-two-sum", html)
            self.assertIn("prob-max-subarray", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
