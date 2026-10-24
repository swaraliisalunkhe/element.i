import asyncio
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sample_app import app as app_module
from sample_app.app import submit_mcq_assessment
from sample_app.data import get_fresh_assessments, get_fresh_candidates, get_fresh_submissions


class TestIntentionalDemoBugs(unittest.TestCase):
    def setUp(self):
        app_module.assessments = get_fresh_assessments()
        app_module.candidates = get_fresh_candidates()
        app_module.submissions = get_fresh_submissions()

    def test_mcq_option_mismatch_remains_in_template(self):
        template = (Path(__file__).parents[1] / "templates" / "mcq_assessment.html").read_bytes().decode("utf-8", errors="ignore")
        self.assertIn('id="{{ q.id }}_opt_{{ opt.key }}"', template)
        self.assertIn("{% set option_value = 'C' %}", template)

    def test_repeated_entire_mcq_submissions_create_duplicate_records(self):
        payload = {
            "request": None,
            "assessment_id": "assessment-python-se",
            "candidate_email": "duplicate@example.com",
            "q_q1": "A",
            "q_q2": None,
            "q_q3": "B",
            "q_q4": None,
        }
        initial_count = len(app_module.submissions)
        first = asyncio.run(submit_mcq_assessment(**payload))
        second = asyncio.run(submit_mcq_assessment(**payload))

        self.assertEqual(first.status_code, 303)
        self.assertEqual(second.status_code, 303)
        self.assertEqual(len(app_module.submissions), initial_count + 2)

    def test_stale_editor_workflow_remains_confined_to_frontend(self):
        template = (Path(__file__).parents[1] / "templates" / "coding_assessment.html").read_bytes().decode("utf-8", errors="ignore")
        self.assertIn("questionOneSubmissionSnapshot", template)
        self.assertIn("questionOneSnapshotCaptured", template)
        self.assertIn("submittedCode", template)
        self.assertIn("questionOneSubmissionSnapshot", template)


if __name__ == "__main__":
    unittest.main(verbosity=2)
