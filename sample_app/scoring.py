
"""Assessment scoring engine for MCQ and coding submissions.

Contains scoring rules and itemized breakdown generation.
"""

from typing import Any, Dict


def calculate_mcq_score(
    answers: Dict[str, str],
    assessment: Dict[str, Any]
) -> Dict[str, Any]:
    """Score MCQ answers.

    Marking scheme:
    +4 for correct, -1 for incorrect, and 0 for unattempted.
    """
    questions = assessment.get("mcq_questions", [])
    correct_count = 0
    incorrect_count = 0
    unattempted_count = 0
    question_breakdown = []

    for q in questions:
        qid = q["id"]
        correct_key = q["correct_option"]
        selected_key = answers.get(qid)

        if not selected_key:
            unattempted_count += 1
            question_breakdown.append({
                "id": qid,
                "number": q["number"],
                "title": q["title"],
                "selected_option": "None",
                "correct_option": correct_key,
                "status": "Unattempted",
                "marks_awarded": 0
            })

        elif selected_key == correct_key:
            correct_count += 1
            question_breakdown.append({
                "id": qid,
                "number": q["number"],
                "title": q["title"],
                "selected_option": selected_key,
                "correct_option": correct_key,
                "status": "Correct",
                "marks_awarded": 4
            })

        else:
            incorrect_count += 1
            question_breakdown.append({
                "id": qid,
                "number": q["number"],
                "title": q["title"],
                "selected_option": selected_key,
                "correct_option": correct_key,
                "status": "Incorrect",
                "marks_awarded": -1
            })

    positive_marks = correct_count * 4
    penalty_marks = incorrect_count * 1
    total_mcq_score = positive_marks - penalty_marks
    max_mcq_score = len(questions) * 4

    return {
        "total_questions": len(questions),
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "unattempted_count": unattempted_count,
        "positive_marks": positive_marks,
        "penalty_marks": penalty_marks,
        "total_mcq_score": total_mcq_score,
        "max_mcq_score": max_mcq_score,
        "question_breakdown": question_breakdown
    }


def score_coding_submission(
    eval_result: Dict[str, Any],
    problem: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate coding score using ALL test results, including hidden tests."""

    test_results = eval_result.get("test_results", [])

    if not eval_result.get("success", False) or not test_results:
        return {
            "score": 0,
            "max_score": 100,
            "passed_tests": 0,
            "total_tests": len(problem.get("test_cases", [])),
            "verdict": eval_result.get("verdict", "Execution Error"),
            "details": eval_result.get("error_details", "No tests run"),
            "test_results": test_results
        }

    # Both public and hidden test cases contribute to the score.
    passed_tests = sum(
        1 for result in test_results
        if result.get("passed", False)
    )
    total_tests = len(test_results)

    coding_score = int((passed_tests / total_tests) * 100)

    return {
        "score": coding_score,
        "max_score": 100,
        "passed_tests": passed_tests,
        "total_tests": total_tests,
        "passed_public": sum(
            1 for result in test_results
            if not result.get("hidden", False)
            and result.get("passed", False)
        ),
        "total_public": sum(
            1 for result in test_results
            if not result.get("hidden", False)
        ),
        "passed_hidden": sum(
            1 for result in test_results
            if result.get("hidden", False)
            and result.get("passed", False)
        ),
        "total_hidden": sum(
            1 for result in test_results
            if result.get("hidden", False)
        ),
        "verdict": "Accepted" if passed_tests == total_tests
        else "Wrong Answer",
        "test_results": test_results
    }
