
"""Code Apex Talent Assessment Platform — Primary FastAPI Server."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, Form, Body, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sample_app.data import (
    get_fresh_assessments,
    get_fresh_candidates,
    get_fresh_submissions,
)
from sample_app.evaluator import evaluate_code
from sample_app.scoring import (
    calculate_mcq_score,
    score_coding_submission,
)


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Code Apex Talent Assessment", version="2.0.0")

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# In-memory application state
assessments = get_fresh_assessments()
candidates = get_fresh_candidates()
submissions = get_fresh_submissions()
contact_messages = []

# Keep submission history only; do not cache evaluation results.
coding_history_by_candidate = {}


def get_coding_problems(assessment):
    """Return the coding problems configured for an assessment."""
    problems = assessment.get("coding_problems")

    if not problems:
        problem = assessment.get("coding_problem", {})
        return [problem] if problem else []

    return problems


def get_coding_problem(assessment, question_id=None):
    """Find a coding problem by its ID, defaulting to the first problem."""
    problems = get_coding_problems(assessment)

    if not problems:
        return None

    if question_id:
        for problem in problems:
            if problem.get("id") == question_id:
                return problem

        return None

    return problems[0]


# ==============================================================================
# LANDING & DASHBOARD ROUTES
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "active_page": "home",
            "assessments": assessments,
        },
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, email: str = "alice.recruiter@example.com"):
    user = candidates.get(
        email,
        {
            "name": email.split("@")[0].capitalize(),
            "email": email,
            "role": "Recruiting Manager",
        },
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_page": "dashboard",
            "user": user,
            "assessments": assessments,
            "submissions": submissions,
        },
    )


@app.get("/assessments", response_class=HTMLResponse)
async def assessments_catalog(
    request: Request,
    email: str = None,
):
    user = None

    if email:
        email = email.strip().lower()
        user = candidates.get(
            email,
            {
                "name": email.split("@")[0].capitalize(),
                "email": email,
                "role": "Candidate",
            },
        )

    return templates.TemplateResponse(
        request=request,
        name="assessments.html",
        context={
            "active_page": "assessments",
            "assessments": assessments,
            "candidate_email": email,
            "user": user,
        },
    )


# ==============================================================================
# MCQ ASSESSMENT ROUTES
# ==============================================================================

@app.get("/assessments/{assessment_id}/mcq", response_class=HTMLResponse)
async def take_mcq_assessment(
    request: Request,
    assessment_id: str,
    candidate_email: str = "bob.candidate@example.com",
):
    assessment = assessments.get(assessment_id)

    if not assessment:
        return RedirectResponse("/assessments", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="mcq_assessment.html",
        context={
            "active_page": "assessments",
            "assessment": assessment,
            "candidate_email": candidate_email,
        },
    )


@app.post("/assessments/{assessment_id}/submit-mcq")
async def submit_mcq_assessment(
    request: Request,
    assessment_id: str,
    candidate_email: str = Form("bob.candidate@example.com"),
    q_q1: str = Form(None),
    q_q2: str = Form(None),
    q_q3: str = Form(None),
    q_q4: str = Form(None),
):
    """Process MCQ answers; repeated submissions remain intentionally possible."""
    assessment = assessments.get(assessment_id)

    if not assessment:
        return RedirectResponse("/assessments", status_code=303)

    answers = {
        "q1": q_q1,
        "q2": q_q2,
        "q3": q_q3,
        "q4": q_q4,
    }

    score_data = calculate_mcq_score(answers, assessment)

    # INTENTIONAL BUG MCQ-02:
    # Repeated clicks create repeated submission records.
    sub_id = f"sub-{uuid4().hex[:6]}"

    candidate_info = candidates.get(candidate_email, {})
    candidate_name = candidate_info.get(
        "name",
        candidate_email.split("@")[0].replace(".", " ").title(),
    )

    max_score = score_data["max_mcq_score"]
    total_score = score_data["total_mcq_score"]

    new_submission = {
        "id": sub_id,
        "assessment_id": assessment_id,
        "assessment_title": assessment["title"],
        "candidate_email": candidate_email,
        "candidate_name": candidate_name,
        "status": "Completed",
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
        "mcq_results": score_data,
        "coding_results": None,
        "total_score": total_score,
        "max_score": max_score,
        "percentage": (
            round((total_score / max_score) * 100, 1)
            if max_score
            else 0
        ),
        "result_status": (
            "Qualified"
            if total_score >= max_score * 0.6
            else "Review Needed"
        ),
    }

    submissions.insert(0, new_submission)

    return RedirectResponse(f"/results/{sub_id}", status_code=303)


# ==============================================================================
# CODING ASSESSMENT ROUTES
# ==============================================================================

@app.get("/assessments/{assessment_id}/coding", response_class=HTMLResponse)
async def take_coding_assessment(
    request: Request,
    assessment_id: str,
    candidate_email: str = "bob.candidate@example.com",
    coding_question: str = None,
):
    assessment = assessments.get(assessment_id)

    if not assessment:
        return RedirectResponse("/assessments", status_code=303)

    coding_problems = get_coding_problems(assessment)
    problem = get_coding_problem(assessment, coding_question)

    if not problem:
        problem = get_coding_problem(assessment)

    if not problem:
        raise HTTPException(
            status_code=404,
            detail="No coding problems configured for this assessment",
        )

    history_key = (
        f"{candidate_email}_{assessment_id}_{problem['id']}"
    )
    history = coding_history_by_candidate.get(history_key, [])

    return templates.TemplateResponse(
        request=request,
        name="coding_assessment.html",
        context={
            "active_page": "assessments",
            "assessment": assessment,
            "problem": problem,
            "coding_problems": coding_problems,
            "starter_code": problem.get("starter_code", ""),
            "candidate_email": candidate_email,
            "coding_question": problem["id"],
            "submissions_history": history,
        },
    )


@app.post("/assessments/{assessment_id}/run-code")
async def run_code_public_tests(
    assessment_id: str,
    payload: dict = Body(...),
):
    """Run submitted code against the selected problem's public test cases."""
    assessment = assessments.get(assessment_id)

    if not assessment:
        raise HTTPException(
            status_code=404,
            detail="Assessment not found",
        )

    question_id = (
        payload.get("coding_question")
        or payload.get("question_id")
        or payload.get("problem_id")
    )

    problem = get_coding_problem(assessment, question_id)

    if not problem:
        raise HTTPException(
            status_code=404,
            detail="Coding question not found",
        )

    code_str = payload.get("code", "")

    public_tests = [
        test_case
        for test_case in problem.get("test_cases", [])
        if not test_case.get("hidden", False)
    ]

    # Always evaluate the code received in this request.
    result = evaluate_code(
        code_str,
        public_tests,
        entry_function=problem.get(
            "entry_function",
            "find_target_pair",
        ),
    )

    return JSONResponse(result)


@app.post("/assessments/{assessment_id}/submit-code")
async def submit_coding_solution(
    request: Request,
    assessment_id: str,
    candidate_email: str = Form("bob.candidate@example.com"),
    code_solution: str = Form(...),
    coding_question: str = Form("prob-two-sum"),
):
    """Evaluate the latest submitted code for the selected coding question."""
    assessment = assessments.get(assessment_id)

    if not assessment:
        return RedirectResponse("/assessments", status_code=303)

    problem = get_coding_problem(assessment, coding_question)

    if not problem:
        raise HTTPException(
            status_code=404,
            detail="Coding question not found",
        )

    # Always evaluate the actual code received in this submission.
    # Both public and hidden test cases are included.
    eval_result = evaluate_code(
        code_solution,
        problem.get("test_cases", []),
        entry_function=problem.get(
            "entry_function",
            "find_target_pair",
        ),
    )

    coding_score_data = score_coding_submission(
        eval_result,
        problem,
    )

    history_key = (
        f"{candidate_email}_{assessment_id}_{problem['id']}"
    )
    history = coding_history_by_candidate.setdefault(history_key, [])

    history.append(
        {
            "attempt": len(history) + 1,
            "submitted_at": datetime.now().strftime("%H:%M:%S UTC"),
            "verdict": coding_score_data["verdict"],
            "score": coding_score_data["score"],
        }
    )

    sub_id = f"sub-{uuid4().hex[:6]}"

    candidate_info = candidates.get(candidate_email, {})
    candidate_name = candidate_info.get(
        "name",
        candidate_email.split("@")[0].replace(".", " ").title(),
    )

    new_submission = {
        "id": sub_id,
        "assessment_id": assessment_id,
        "assessment_title": assessment["title"],
        "coding_question_id": problem["id"],
        "coding_question_title": problem["title"],
        "candidate_email": candidate_email,
        "candidate_name": candidate_name,
        "status": "Completed",
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
        "mcq_results": None,
        "coding_results": coding_score_data,
        "total_score": coding_score_data["score"],
        "max_score": problem.get("points", 100),
        "percentage": coding_score_data["score"],
        "result_status": (
            "Qualified"
            if coding_score_data["score"] >= 70
            else "Review Needed"
        ),
    }

    submissions.insert(0, new_submission)

    return RedirectResponse(f"/results/{sub_id}", status_code=303)


# ==============================================================================
# RESULTS & REPORTING
# ==============================================================================

@app.get("/results/{submission_id}", response_class=HTMLResponse)
async def view_results(request: Request, submission_id: str):
    sub = next(
        (s for s in submissions if s["id"] == submission_id),
        None,
    )

    if not sub:
        sub = submissions[0] if submissions else None

    if not sub:
        return RedirectResponse("/dashboard", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={
            "active_page": "dashboard",
            "submission": sub,
        },
    )


# ==============================================================================
# DATA RESET
# ==============================================================================

@app.post("/reset")
async def reset_app():
    global assessments, candidates, submissions, contact_messages

    assessments = get_fresh_assessments()
    candidates = get_fresh_candidates()
    submissions = get_fresh_submissions()
    coding_history_by_candidate.clear()
    contact_messages.clear()

    return JSONResponse(
        {
            "status": "success",
            "message": "Sample app data reset",
        }
    )


@app.get("/reset", response_class=HTMLResponse)
async def reset_app_get():
    await reset_app()
    return RedirectResponse("/dashboard", status_code=303)


# ==============================================================================
# AUTHENTICATION & SUPPORT ROUTES
# ==============================================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"active_page": "login"},
    )


@app.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...),
):
    email = email.strip().lower()
    return RedirectResponse(
        f"/dashboard?email={email}",
        status_code=303,
    )


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="signup.html",
        context={"active_page": "signup"},
    )


@app.post("/signup")
async def signup(
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    email = email.strip().lower()

    candidates[email] = {
        "email": email,
        "name": email.split("@")[0].capitalize(),
        "role": "Candidate",
        "password": password,
    }

    return RedirectResponse("/login", status_code=303)


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="reset_password.html",
        context={},
    )


@app.post("/reset-password")
async def reset_password(email: str = Form(...)):
    return RedirectResponse("/login", status_code=303)


@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="contact.html",
        context={"active_page": "contact"},
    )


@app.post("/contact", response_class=HTMLResponse)
async def contact(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    message: str = Form(""),
):
    contact_messages.append(
        {
            "name": name,
            "email": email,
            "message": message,
        }
    )

    return templates.TemplateResponse(
        request=request,
        name="contact.html",
        context={
            "active_page": "contact",
            "success_message": (
                "Thank you! Your assessment support inquiry has been submitted."
            ),
        },
    )


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    email: str = "bob.candidate@example.com",
):
    email = email.strip().lower()

    user = candidates.get(
        email,
        {
            "name": email.split("@")[0].capitalize(),
            "email": email,
        },
    )

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "user": user,
            "email": email,
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "sample_app.app:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
    )
