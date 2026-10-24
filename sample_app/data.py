
"""Preloaded assessment domain data and synthetic candidates for Code Apex Talent Assessment.

Provides realistic company-oriented assessments (MCQ and Coding),
test cases (public and hidden), and initial candidate records.
"""

from copy import deepcopy


ASSESSMENTS_DATA = {
    "assessment-python-se": {
        "id": "assessment-python-se",
        "title": "Python Systems & Algorithms Assessment",
        "role": "Senior Software Engineer - Python",
        "description": "Comprehensive technical evaluation covering Python data structures, computational complexity, concurrency, and algorithmic problem solving.",
        "duration_minutes": 45,
        "type": "MCQ + Coding",
        "skills": ["Python", "Algorithms", "Data Structures", "System Design"],
        "mcq_total_marks": 16,
        "coding_total_marks": 100,
        "total_marks": 116,
        "passing_percentage": 70,
        "marking_rules": {
            "correct_marks": 4,
            "incorrect_penalty": -1,
            "unattempted_marks": 0,
            "description": "Each correct answer awards +4 marks. Each incorrect answer incurs a -1 mark penalty. Unattempted questions receive 0 marks."
        },
        "mcq_questions": [
            {
                "id": "q1",
                "number": 1,
                "title": "Python Data Structure Lookup Complexity",
                "text": "In standard CPython, what is the average-case time complexity of checking membership ('x in collection') for a collection of size n implemented as a built-in set compared to a built-in list?",
                "code_snippet": "# Case A: set lookup\nfound = key in user_id_set\n\n# Case B: list lookup\nfound = key in user_id_list",
                "options": [
                    {"key": "A", "text": "Set is O(1) average; List is O(n) average"},
                    {"key": "B", "text": "Set is O(log n) average; List is O(1) average"},
                    {"key": "C", "text": "Both are O(log n) average"},
                    {"key": "D", "text": "Both are O(n) average"}
                ],
                "correct_option": "A",
                "marks": 4,
                "negative_marks": 1
            },
            {
                "id": "q2",
                "number": 2,
                "title": "QuickSort Computational Complexity",
                "text": "What is the worst-case time complexity of the standard QuickSort algorithm when elements are already sorted and the first element is consistently chosen as the pivot?",
                "code_snippet": None,
                "options": [
                    {"key": "A", "text": "O(n)"},
                    {"key": "B", "text": "O(n log n)"},
                    {"key": "C", "text": "O(n²)"},
                    {"key": "D", "text": "O(log n)"}
                ],
                "correct_option": "C",
                "marks": 4,
                "negative_marks": 1
            },
            {
                "id": "q3",
                "number": 3,
                "title": "CPython Global Interpreter Lock (GIL)",
                "text": "Which of the following statements accurately characterizes the behavior of Python's Global Interpreter Lock (GIL) during multi-threaded I/O-bound operations?",
                "code_snippet": None,
                "options": [
                    {"key": "A", "text": "The GIL locks all threads during I/O operations, blocking any concurrency"},
                    {"key": "B", "text": "The GIL is released during system calls and I/O operations, allowing other threads to run"},
                    {"key": "C", "text": "Multi-threading cannot be used in Python under any circumstances"},
                    {"key": "D", "text": "The GIL automatically parallelizes CPU-bound tasks across all available CPU cores"}
                ],
                "correct_option": "B",
                "marks": 4,
                "negative_marks": 1
            },
            {
                "id": "q4",
                "number": 4,
                "title": "Database Isolation & ACID Guarantees",
                "text": "In a relational database transaction management system, which ACID property ensures that changes made by committed transactions persist even during an unexpected server crash?",
                "code_snippet": None,
                "options": [
                    {"key": "A", "text": "Atomicity"},
                    {"key": "B", "text": "Consistency"},
                    {"key": "C", "text": "Isolation"},
                    {"key": "D", "text": "Durability"}
                ],
                "correct_option": "D",
                "marks": 4,
                "negative_marks": 1
            }
        ],
        "coding_problem": {
            "id": "prob-two-sum",
            "title": "Two-Sum Target Indices",
            "difficulty": "Medium",
            "points": 100,
            "time_limit_seconds": 3,
            "description": (
                "Given an integer array 'nums' and an integer 'target', return the 0-based indices of the two distinct numbers "
                "such that they add up to target. You may assume that each input has exactly one valid solution, "
                "and you may not use the same element twice. Return the indices sorted in ascending order."
            ),
            "input_format": "nums: list[int], target: int",
            "output_format": "list[int] containing two 0-based indices [i, j] where i < j",
            "constraints": [
                "2 <= len(nums) <= 10^4",
                "-10^9 <= nums[i] <= 10^9",
                "-10^9 <= target <= 10^9",
                "Exactly one valid answer exists."
            ],
            "starter_code": (
                "def find_target_pair(nums: list[int], target: int) -> list[int]:\n"
                "    \"\"\"\n"
                "    Find two indices such that nums[i] + nums[j] == target (i < j).\n"
                "    \"\"\"\n"
                "    # Write your solution here\n"
                "    pass\n"
            ),
            "test_cases": [
                {
                    "id": "tc-pub-1",
                    "name": "Example 1 (Positive elements)",
                    "input_args": ([2, 7, 11, 15], 9),
                    "input_display": "nums = [2, 7, 11, 15], target = 9",
                    "expected_output": [0, 1],
                    "hidden": False,
                    "points": 25
                },
                {
                    "id": "tc-pub-2",
                    "name": "Example 2 (Unsorted elements)",
                    "input_args": ([3, 2, 4], 6),
                    "input_display": "nums = [3, 2, 4], target = 6",
                    "expected_output": [1, 2],
                    "hidden": False,
                    "points": 25
                },
                {
                    "id": "tc-hid-1",
                    "name": "Hidden Test 1 (Negative integers)",
                    "input_args": ([-1, -2, -3, -4, -5], -8),
                    "input_display": "nums = [-1, -2, -3, -4, -5], target = -8",
                    "expected_output": [2, 4],
                    "hidden": True,
                    "points": 25
                },
                {
                    "id": "tc-hid-2",
                    "name": "Hidden Test 2 (Duplicate elements)",
                    "input_args": ([1, 5, 5, 11], 10),
                    "input_display": "nums = [1, 5, 5, 11], target = 10",
                    "expected_output": [1, 2],
                    "hidden": True,
                    "points": 25
                }
            ]
        }
    },

    "assessment-backend-core": {
        "id": "assessment-backend-core",
        "title": "Backend Engineering & Data Structures",
        "role": "Backend Engineer",
        "description": "Assessment evaluating core backend algorithms, API design standards, caching strategies, and data structure manipulation.",
        "duration_minutes": 40,
        "type": "MCQ + Coding",
        "skills": ["Algorithms", "REST APIs", "Caching", "Python"],
        "mcq_total_marks": 16,
        "coding_total_marks": 100,
        "total_marks": 116,
        "passing_percentage": 70,
        "marking_rules": {
            "correct_marks": 4,
            "incorrect_penalty": -1,
            "unattempted_marks": 0,
            "description": "Each correct answer awards +4 marks. Each incorrect answer incurs a -1 mark penalty. Unattempted questions receive 0 marks."
        },
        "mcq_questions": [
            {
                "id": "q1",
                "number": 1,
                "title": "HTTP Idempotency",
                "text": "Which of the following HTTP methods is defined as idempotent according to the RFC 9110 specification?",
                "code_snippet": None,
                "options": [
                    {"key": "A", "text": "POST"},
                    {"key": "B", "text": "PUT"},
                    {"key": "C", "text": "PATCH (without conditional headers)"},
                    {"key": "D", "text": "CONNECT"}
                ],
                "correct_option": "B",
                "marks": 4,
                "negative_marks": 1
            },
            {
                "id": "q2",
                "number": 2,
                "title": "Hash Map Collision Handling",
                "text": "In open addressing with linear probing for hash table collision resolution, what happens to lookup performance when the load factor approaches 1.0?",
                "code_snippet": None,
                "options": [
                    {"key": "A", "text": "Lookup time remains strictly O(1)"},
                    {"key": "B", "text": "Lookup degrades toward O(n) due to primary clustering"},
                    {"key": "C", "text": "The table automatically converts to an AVL tree"},
                    {"key": "D", "text": "Lookup time becomes O(log n)"}
                ],
                "correct_option": "B",
                "marks": 4,
                "negative_marks": 1
            },
            {
                "id": "q3",
                "number": 3,
                "title": "Cache Eviction Policy",
                "text": "Which data structure combination provides O(1) get and O(1) put operations for an LRU (Least Recently Used) cache?",
                "code_snippet": None,
                "options": [
                    {"key": "A", "text": "Binary Search Tree and Array"},
                    {"key": "B", "text": "Doubly Linked List and Hash Map"},
                    {"key": "C", "text": "Max Heap and Stack"},
                    {"key": "D", "text": "Queue and Singly Linked List"}
                ],
                "correct_option": "B",
                "marks": 4,
                "negative_marks": 1
            },
            {
                "id": "q4",
                "number": 4,
                "title": "Database Connection Pooling",
                "text": "Why do production backend services employ connection pooling for relational databases?",
                "code_snippet": None,
                "options": [
                    {"key": "A", "text": "To eliminate the need for SQL queries"},
                    {"key": "B", "text": "To amortize the latency and CPU cost of opening and handshaking new TCP/TLS connections"},
                    {"key": "C", "text": "To guarantee that transactions never lock rows"},
                    {"key": "D", "text": "To allow client browsers to connect directly to the database"}
                ],
                "correct_option": "B",
                "marks": 4,
                "negative_marks": 1
            }
        ],
        "coding_problem": {
            "id": "prob-two-sum",
            "title": "Two-Sum Target Indices",
            "difficulty": "Medium",
            "points": 100,
            "time_limit_seconds": 3,
            "description": (
                "Given an integer array 'nums' and an integer 'target', return the 0-based indices of the two distinct numbers "
                "such that they add up to target. You may assume that each input has exactly one valid solution."
            ),
            "input_format": "nums: list[int], target: int",
            "output_format": "list[int] containing two 0-based indices [i, j] where i < j",
            "constraints": [
                "2 <= len(nums) <= 10^4",
                "-10^9 <= nums[i] <= 10^9",
                "-10^9 <= target <= 10^9"
            ],
            "starter_code": (
                "def find_target_pair(nums: list[int], target: int) -> list[int]:\n"
                "    \"\"\"\n"
                "    Find two indices such that nums[i] + nums[j] == target (i < j).\n"
                "    \"\"\"\n"
                "    # Write your solution here\n"
                "    pass\n"
            ),
            "test_cases": [
                {
                    "id": "tc-pub-1",
                    "name": "Example 1 (Positive elements)",
                    "input_args": ([2, 7, 11, 15], 9),
                    "input_display": "nums = [2, 7, 11, 15], target = 9",
                    "expected_output": [0, 1],
                    "hidden": False,
                    "points": 25
                },
                {
                    "id": "tc-pub-2",
                    "name": "Example 2 (Unsorted elements)",
                    "input_args": ([3, 2, 4], 6),
                    "input_display": "nums = [3, 2, 4], target = 6",
                    "expected_output": [1, 2],
                    "hidden": False,
                    "points": 25
                },
                {
                    "id": "tc-hid-1",
                    "name": "Hidden Test 1 (Negative integers)",
                    "input_args": ([-1, -2, -3, -4, -5], -8),
                    "input_display": "nums = [-1, -2, -3, -4, -5], target = -8",
                    "expected_output": [2, 4],
                    "hidden": True,
                    "points": 25
                },
                {
                    "id": "tc-hid-2",
                    "name": "Hidden Test 2 (Duplicate elements)",
                    "input_args": ([1, 5, 5, 11], 10),
                    "input_display": "nums = [1, 5, 5, 11], target = 10",
                    "expected_output": [1, 2],
                    "hidden": True,
                    "points": 25
                }
            ]
        }
    }
}


# Add the second coding question without removing the existing Two-Sum question.
for _assessment in ASSESSMENTS_DATA.values():
    _first_problem = _assessment["coding_problem"]
    _first_problem["entry_function"] = "find_target_pair"

    _second_problem = {
        "id": "prob-max-subarray",
        "title": "Maximum Subarray Sum",
        "difficulty": "Medium",
        "points": 100,
        "time_limit_seconds": 3,
        "description": (
            "Given an integer array nums, return the maximum sum "
            "of any non-empty contiguous subarray."
        ),
        "input_format": "nums: list[int]",
        "output_format": "An integer representing the maximum subarray sum",
        "constraints": [
            "1 <= len(nums) <= 10^5",
            "-10^4 <= nums[i] <= 10^4"
        ],
        "entry_function": "max_subarray_sum",
        "starter_code": (
            "def max_subarray_sum(nums: list[int]) -> int:\n"
            "    \"\"\"Return the maximum sum of a non-empty subarray.\"\"\"\n"
            "    # Write your solution here\n"
            "    pass\n"
        ),
        "test_cases": [
            {
                "id": "tc2-pub-1",
                "name": "Mixed positive and negative values",
                "input_args": ([-2, 1, -3, 4, -1, 2, 1, -5, 4],),
                "input_display": "nums = [-2, 1, -3, 4, -1, 2, 1, -5, 4]",
                "expected_output": 6,
                "hidden": False,
                "points": 25
            },
            {
                "id": "tc2-pub-2",
                "name": "Single element",
                "input_args": ([1],),
                "input_display": "nums = [1]",
                "expected_output": 1,
                "hidden": False,
                "points": 25
            },
            {
                "id": "tc2-hid-1",
                "name": "All negative values",
                "input_args": ([-3, -2, -5],),
                "input_display": "Hidden test case",
                "expected_output": -2,
                "hidden": True,
                "points": 25
            },
            {
                "id": "tc2-hid-2",
                "name": "Best subarray reaches the end",
                "input_args": ([5, 4, -1, 7, 8],),
                "input_display": "Hidden test case",
                "expected_output": 23,
                "hidden": True,
                "points": 25
            }
        ]
    }

    _assessment["coding_problems"] = [
        _first_problem,
        _second_problem
    ]


INITIAL_CANDIDATES = {
    "alice.recruiter@example.com": {
        "email": "alice.recruiter@example.com",
        "name": "Alice Morgan",
        "role": "Recruiting Manager",
        "password": "password123"
    },
    "bob.candidate@example.com": {
        "email": "bob.candidate@example.com",
        "name": "Bob Chen",
        "role": "Candidate",
        "password": "password123"
    },
    "charlie.candidate@example.com": {
        "email": "charlie.candidate@example.com",
        "name": "Charlie Davis",
        "role": "Candidate",
        "password": "password123"
    }
}


INITIAL_SUBMISSIONS = [
    {
        "id": "sub-101",
        "assessment_id": "assessment-python-se",
        "assessment_title": "Python Systems & Algorithms Assessment",
        "candidate_email": "bob.candidate@example.com",
        "candidate_name": "Bob Chen",
        "status": "Completed",
        "submitted_at": "2026-10-24 14:30 UTC",
        "mcq_score": 12,
        "mcq_total": 16,
        "coding_score": 100,
        "coding_total": 100,
        "total_score": 112,
        "max_score": 116,
        "percentage": 96.5,
        "result_status": "Qualified"
    },
    {
        "id": "sub-102",
        "assessment_id": "assessment-python-se",
        "assessment_title": "Python Systems & Algorithms Assessment",
        "candidate_email": "charlie.candidate@example.com",
        "candidate_name": "Charlie Davis",
        "status": "Under Review",
        "submitted_at": "2026-10-24 16:15 UTC",
        "mcq_score": 7,
        "mcq_total": 16,
        "coding_score": 50,
        "coding_total": 100,
        "total_score": 57,
        "max_score": 116,
        "percentage": 49.1,
        "result_status": "Review Needed"
    }
]


def get_fresh_assessments() -> dict:
    return deepcopy(ASSESSMENTS_DATA)


def get_fresh_candidates() -> dict:
    return deepcopy(INITIAL_CANDIDATES)


def get_fresh_submissions() -> list:
    return deepcopy(INITIAL_SUBMISSIONS)
