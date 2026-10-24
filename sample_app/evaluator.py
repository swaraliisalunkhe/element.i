
"""In-process code evaluation engine for technical coding assessments."""

import sys
import io
import time
from typing import Any, Dict, List, Tuple


def execute_test_case(
    func: Any,
    input_args: Tuple,
    expected_output: Any
) -> Dict[str, Any]:
    """Execute a candidate function against one test case."""

    start_time = time.perf_counter()
    captured_stdout = io.StringIO()
    old_stdout = sys.stdout

    try:
        sys.stdout = captured_stdout
        actual_output = func(*input_args)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if isinstance(actual_output, (list, tuple)) and isinstance(
            expected_output, (list, tuple)
        ):
            passed = list(actual_output) == list(expected_output)
        else:
            passed = actual_output == expected_output

        return {
            "passed": passed,
            "status": "Passed" if passed else "Wrong Answer",
            "actual_output": actual_output,
            "expected_output": expected_output,
            "stdout": captured_stdout.getvalue(),
            "execution_time_ms": round(elapsed_ms, 2),
            "error_message": None
        }

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return {
            "passed": False,
            "status": "Runtime Error",
            "actual_output": None,
            "expected_output": expected_output,
            "stdout": captured_stdout.getvalue(),
            "execution_time_ms": round(elapsed_ms, 2),
            "error_message": f"{type(exc).__name__}: {exc}"
        }

    finally:
        sys.stdout = old_stdout


def evaluate_code(
    code_str: str,
    test_cases: List[Dict[str, Any]],
    entry_function: str = "find_target_pair"
) -> Dict[str, Any]:
    """Compile and execute submitted code against the supplied test cases."""

    local_env: Dict[str, Any] = {}

    try:
        compiled_code = compile(
            code_str,
            "<candidate_submission>",
            "exec"
        )
        exec(compiled_code, local_env, local_env)

    except SyntaxError as exc:
        return {
            "success": False,
            "verdict": "Syntax Error",
            "total_passed": 0,
            "total_tests": len(test_cases),
            "error_details": (
                f"SyntaxError: {exc.msg} (line {exc.lineno})"
            ),
            "test_results": []
        }

    except Exception as exc:
        return {
            "success": False,
            "verdict": "Compilation Error",
            "total_passed": 0,
            "total_tests": len(test_cases),
            "error_details": f"{type(exc).__name__}: {exc}",
            "test_results": []
        }

    func = local_env.get(entry_function)

    if not callable(func):
        return {
            "success": False,
            "verdict": "Missing Function",
            "total_passed": 0,
            "total_tests": len(test_cases),
            "error_details": (
                f"Function '{entry_function}' was not found "
                "or is not callable in the submission."
            ),
            "test_results": []
        }

    test_results = []
    passed_count = 0

    # Evaluate every supplied test case, including hidden test cases.
    for test_case in test_cases:
        result = execute_test_case(
            func,
            test_case["input_args"],
            test_case["expected_output"]
        )

        result["id"] = test_case.get("id")
        result["name"] = test_case.get("name")
        result["hidden"] = test_case.get("hidden", False)
        result["points"] = test_case.get("points", 25)
        result["input_display"] = test_case.get("input_display", "")

        test_results.append(result)

        if result["passed"]:
            passed_count += 1

    total_tests = len(test_cases)

    if passed_count == total_tests:
        verdict = "Accepted"
    elif any(
        result["status"] == "Wrong Answer"
        for result in test_results
    ):
        verdict = "Wrong Answer"
    else:
        verdict = "Runtime Error"

    return {
        "success": True,
        "verdict": verdict,
        "total_passed": passed_count,
        "total_tests": total_tests,
        "test_results": test_results,
        "error_details": None
    }
