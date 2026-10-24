"""Builds shared/contracts/run_detail.json from the other examples. Owner: Member A.

Run from the repository root:  python shared/contracts/build_run_detail.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


detail = load("run_response.json")
detail["description"] = "Online assessment QA run on the sample assessment."
detail["mode"] = "assessment"
detail["summary"] = {
    "journeys_count": 1, "tests_total": 3, "tests_passed": 2, "tests_failed": 1, "bugs_count": 1,
}
detail["assessment_map"] = load("assessment_map.json")
detail["suite"] = load("test_suite.json")
detail["coverage"] = {
    "questions": {"total": 6, "exercised": 3},
    "questions_by_type": {
        "mcq": {"total": 4, "exercised": 2},
        "coding": {"total": 2, "exercised": 1},
    },
    "states": {"total": 12, "exercised": 10},
    "scenarios": {"total": 9, "exercised": 3},
}

(HERE / "run_detail.json").write_text(json.dumps(detail, indent=2) + "\n", encoding="utf-8")
print("Wrote shared/contracts/run_detail.json")