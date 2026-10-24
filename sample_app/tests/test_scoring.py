
import unittest

from sample_app.scoring import calculate_mcq_score, score_coding_submission


class TestMCQScoring(unittest.TestCase):
    def setUp(self):
        self.assessment = {
            "mcq_questions": [
                {
                    "id": "q1",
                    "number": 1,
                    "title": "Question 1",
                    "correct_option": "A",
                },
                {
                    "id": "q2",
                    "number": 2,
                    "title": "Question 2",
                    "correct_option": "B",
                },
                {
                    "id": "q3",
                    "number": 3,
                    "title": "Question 3",
                    "correct_option": "C",
                },
            ]
        }

    def test_correct_answer_gets_four_marks(self):
        result = calculate_mcq_score({"q1": "A"}, self.assessment)
        self.assertEqual(result["total_mcq_score"], 4)

    def test_incorrect_answer_loses_one_mark(self):
        result = calculate_mcq_score({"q1": "B"}, self.assessment)
        self.assertEqual(result["total_mcq_score"], -1)

    def test_unattempted_question_gets_zero(self):
        result = calculate_mcq_score({}, self.assessment)
        self.assertEqual(result["total_mcq_score"], 0)
        self.assertEqual(result["unattempted_count"], 3)

    def test_mixed_answers_are_scored_correctly(self):
        result = calculate_mcq_score(
            {"q1": "A", "q2": "A"}, self.assessment
        )
        self.assertEqual(result["total_mcq_score"], 3)


class TestCodingScoring(unittest.TestCase):
    def setUp(self):
        self.problem = {
            "points": 100,
            "test_cases": [
                {"hidden": False},
                {"hidden": True},
            ],
        }

    def test_hidden_and_public_tests_both_count(self):
        evaluation = {
            "success": True,
            "verdict": "Wrong Answer",
            "test_results": [
                {"passed": True, "status": "Passed"},
                {"passed": False, "status": "Wrong Answer"},
            ],
        }

        result = score_coding_submission(evaluation, self.problem)

        self.assertEqual(result["total_tests"], 2)
        self.assertEqual(result["passed_tests"], 1)
        self.assertEqual(result["score"], 50)

    def test_all_passed_tests_get_full_score(self):
        evaluation = {
            "success": True,
            "verdict": "Accepted",
            "test_results": [
                {"passed": True, "status": "Passed"},
                {"passed": True, "status": "Passed"},
            ],
        }

        result = score_coding_submission(evaluation, self.problem)

        self.assertEqual(result["score"], 100)
        self.assertEqual(result["passed_tests"], 2)
        self.assertEqual(result["verdict"], "Accepted")


if __name__ == "__main__":
    unittest.main(verbosity=2)
