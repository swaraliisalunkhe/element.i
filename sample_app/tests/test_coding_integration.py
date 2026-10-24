import asyncio
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sample_app import app as app_module
from sample_app.app import run_code_public_tests, submit_coding_solution
from sample_app.data import get_fresh_assessments


TWO_SUM_CODE = """
def find_target_pair(nums, target):
    seen = {}
    for index, number in enumerate(nums):
        complement = target - number
        if complement in seen:
            return [seen[complement], index]
        seen[number] = index
    return []
"""

MAX_SUBARRAY_CODE = """
def max_subarray_sum(nums):
    best = current = nums[0]
    for number in nums[1:]:
        current = max(number, current + number)
        best = max(best, current)
    return best
"""


class TestCodingIntegration(unittest.TestCase):
    def setUp(self):
        app_module.assessments = get_fresh_assessments()
        app_module.submissions = app_module.get_fresh_submissions()
        app_module.coding_history_by_candidate.clear()

    def test_each_assessment_has_both_problems_and_correct_entry_functions(self):
        for assessment in app_module.assessments.values():
            problems = app_module.get_coding_problems(assessment)
            self.assertEqual(
                [problem["id"] for problem in problems],
                ["prob-two-sum", "prob-max-subarray"],
            )
            self.assertEqual(
                app_module.get_coding_problem(assessment, "prob-two-sum")[
                    "entry_function"
                ],
                "find_target_pair",
            )
            self.assertEqual(
                app_module.get_coding_problem(assessment, "prob-max-subarray")[
                    "entry_function"
                ],
                "max_subarray_sum",
            )

    def test_public_runner_uses_selected_problem_and_only_public_tests(self):
        for assessment_id in app_module.assessments:
            two_sum_result = asyncio.run(
                run_code_public_tests(
                    assessment_id,
                    {"code": TWO_SUM_CODE, "coding_question": "prob-two-sum"},
                )
            )
            self.assertTrue(two_sum_result.body)
            self.assertEqual(
                len(app_module.get_coding_problem(
                    app_module.assessments[assessment_id], "prob-two-sum"
                )["test_cases"]),
                4,
            )

            max_result = asyncio.run(
                run_code_public_tests(
                    assessment_id,
                    {"code": MAX_SUBARRAY_CODE, "coding_question": "prob-max-subarray"},
                )
            )
            self.assertTrue(max_result.body)

            import json

            two_sum_data = json.loads(two_sum_result.body)
            max_data = json.loads(max_result.body)
            self.assertEqual(len(two_sum_data["test_results"]), 2)
            self.assertEqual(len(max_data["test_results"]), 2)
            self.assertEqual(two_sum_data["verdict"], "Accepted")
            self.assertEqual(max_data["verdict"], "Accepted")

    def test_final_submission_includes_hidden_tests_for_each_problem(self):
        for assessment_id in app_module.assessments:
            for problem_id, code in (
                ("prob-two-sum", TWO_SUM_CODE),
                ("prob-max-subarray", MAX_SUBARRAY_CODE),
            ):
                response = asyncio.run(
                    submit_coding_solution(
                        None,
                        assessment_id,
                        candidate_email="coding@example.com",
                        code_solution=code,
                        coding_question=problem_id,
                    )
                )
                self.assertEqual(response.status_code, 303)
                result = app_module.submissions[0]["coding_results"]
                self.assertEqual(result["total_tests"], 4)
                self.assertEqual(result["total_hidden"], 2)
                self.assertEqual(result["passed_hidden"], 2)
                self.assertEqual(result["score"], 100)

    def test_submitting_one_problem_cannot_evaluate_the_other(self):
        response = asyncio.run(
            submit_coding_solution(
                None,
                "assessment-python-se",
                candidate_email="isolation@example.com",
                code_solution=MAX_SUBARRAY_CODE,
                coding_question="prob-two-sum",
            )
        )
        self.assertEqual(response.status_code, 303)
        result = app_module.submissions[0]["coding_results"]
        self.assertEqual(result["verdict"], "Missing Function")
        self.assertEqual(result["score"], 0)

    def test_each_request_evaluates_the_latest_code(self):
        failing = asyncio.run(
            run_code_public_tests(
                "assessment-python-se",
                {"code": "def max_subarray_sum(nums): return 0", "coding_question": "prob-max-subarray"},
            )
        )
        passing = asyncio.run(
            run_code_public_tests(
                "assessment-python-se",
                {"code": MAX_SUBARRAY_CODE, "coding_question": "prob-max-subarray"},
            )
        )
        import json

        self.assertNotEqual(
            json.loads(failing.body)["total_passed"],
            json.loads(passing.body)["total_passed"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
