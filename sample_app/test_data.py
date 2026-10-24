"""Trusted ground-truth answers, expected scores, and test validation fixtures.

Kept isolated from the candidate-facing UI to enable independent verification
of all five intentional bugs without exposing answers or bug hints to candidates.
"""

TRUSTED_ANSWER_KEYS = {
    "assessment-python-se": {
        "q1": "A",  # Set lookup is O(1) avg; List is O(n) avg
        "q2": "C",  # QuickSort worst-case is O(n²)
        "q3": "B",  # GIL is released during system calls and I/O
        "q4": "D",  # Durability guarantees persistence after crash
    },
    "assessment-backend-core": {
        "q1": "B",  # PUT is idempotent
        "q2": "B",  # Hash map degrades toward O(n) due to primary clustering
        "q3": "B",  # Doubly Linked List and Hash Map
        "q4": "B",  # Amortize TCP/TLS connection handshake cost
    }
}

TRUSTED_MARKING_RULES = {
    "correct_marks": 4,
    "incorrect_penalty": -1,
    "unattempted_marks": 0
}

# Ground truth expected calculation function
def calculate_expected_mcq_score(answers: dict, assessment_id: str = "assessment-python-se") -> dict:
    """Calculates what the true, bug-free score should be according to stated rules (+4 / -1 / 0)."""
    keys = TRUSTED_ANSWER_KEYS.get(assessment_id, {})
    correct_count = 0
    incorrect_count = 0
    unattempted_count = 0
    details = {}

    for qid, expected_key in keys.items():
        candidate_ans = answers.get(qid)
        if not candidate_ans:
            unattempted_count += 1
            details[qid] = {"status": "Unattempted", "marks": 0}
        elif candidate_ans == expected_key:
            correct_count += 1
            details[qid] = {"status": "Correct", "marks": 4}
        else:
            incorrect_count += 1
            details[qid] = {"status": "Incorrect", "marks": -1}

    true_score = (correct_count * 4) + (incorrect_count * -1)
    max_score = len(keys) * 4

    return {
        "total_questions": len(keys),
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "unattempted_count": unattempted_count,
        "expected_score": true_score,
        "max_score": max_score,
        "question_details": details
    }


# Synthetic bug test scenarios for test suites
BUG_VERIFICATION_SPECS = {
    "MCQ-01": {
        "description": "Selected answer differs from submitted answer on Question 2",
        "action": "Select Option B on Question 2",
        "expected_recorded_answer": "B",
        "actual_recorded_answer": "C",  # Due to value='C' binding error
        "assertion": "actual_recorded_answer == 'C'"
    },
    "MCQ-02": {
        "description": "Incorrect negative-marking calculation (-4 penalty instead of -1)",
        "answers": {"q1": "A", "q2": "A", "q3": "B", "q4": None},  # 2 correct (q1, q3), 1 incorrect (q2), 1 blank (q4)
        "expected_score": 7,  # (2 * 4) - (1 * 1) = 7
        "actual_buggy_score": 4,  # (2 * 4) - (1 * 4) = 4
        "assertion": "actual_score == 4 and actual_score != expected_score"
    },
    "MCQ-03": {
        "description": "Duplicate submission changes assessment results",
        "action": "Submit the same MCQ form payload twice",
        "expected_behavior": "Idempotent: score remains identical on re-submission",
        "actual_buggy_behavior": "Cumulative: score increments or mutates on duplicate submission",
        "assertion": "first_submit_score != second_submit_score"
    },
    "CODE-01": {
        "description": "Hidden test cases are ignored during scoring",
        "code_solution": (
            "def find_target_pair(nums: list[int], target: int) -> list[int]:\n"
            "    # Solution that passes only public tests, fails negative numbers\n"
            "    if target == 9: return [0, 1]\n"
            "    if target == 6: return [1, 2]\n"
            "    return []\n"
        ),
        "expected_score": 50,  # 2 public pass (50), 2 hidden fail (0) -> 50/100
        "actual_buggy_score": 100,  # Hidden tests ignored, gets 100/100
        "assertion": "actual_score == 100 and actual_score != expected_score"
    },
    "CODE-02": {
        "description": "Previous coding submission results are reused",
        "steps": [
            "1. Submit failing code (score: 0/100)",
            "2. Submit correct code (expected: 100/100)"
        ],
        "expected_second_submission_score": 100,
        "actual_second_submission_score": 0,  # Reuses cached result from attempt 1
        "assertion": "second_submission_score == 0 and second_submission_score != 100"
    }
}
