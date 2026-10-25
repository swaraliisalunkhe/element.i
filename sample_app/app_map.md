# Code Apex Talent Assessment — Application Map

## 1. Overview
Code Apex Talent Assessment is an enterprise-grade online skills assessment and testing platform designed for technical evaluation, multiple-choice screening, and hands-on coding assessments.

---

## 2. Route Specification

| Method | Route | Description | Template / Return |
|---|---|---|---|
| `GET` | `/` | Platform landing page with hero, Start Assessment CTA, and platform feature highlights. Title and heading contain `Code Apex`. | `home.html` |
| `GET` | `/dashboard` | Recruiter & Candidate assessment dashboard with active assessments, statistics, and submission records. | `dashboard.html` |
| `GET` | `/assessments` | Assessment catalog listing test names, technical skills, duration, question count, and test format. | `assessments.html` |
| `GET` | `/assessments/{id}/mcq` | Interactive multiple-choice assessment interface with question palette, option selector, timer, and marking rules. | `mcq_assessment.html` |
| `POST` | `/assessments/{id}/submit-mcq` | Handles submission of MCQ answer selections and records assessment score. Contains **MCQ-03** duplicate submission mutation bug. | Redirect to `/results/{submission_id}` |
| `GET` | `/assessments/{id}/coding` | Hands-on coding environment with problem description, constraints, Python code editor, test runner, and submission history. | `coding_assessment.html` |
| `POST` | `/assessments/{id}/run-code` | Real-time public test case execution engine (returns stdout, status, execution time in JSON). Does not create permanent submission. | JSON execution response |
| `POST` | `/assessments/{id}/submit-code` | Official coding submission evaluator. Evaluates test cases and records score. Contains **CODE-02** previous submission reuse bug and **CODE-01** hidden test case omission bug. | Redirect to `/results/{submission_id}` |
| `GET` | `/results/{submission_id}` | Detailed assessment results breakdown with MCQ score, negative marking penalty, coding test matrix, and final recommendation. | `results.html` |
| `POST` | `/reset` | System reset endpoint. Restores fresh seed assessments, candidates, submissions, and clears submission cache. | JSON `{"status": "success", "message": "Sample app data reset"}` |
| `GET` | `/login` | Authentication page for candidate and recruiter access. | `login.html` |
| `POST` | `/login` | Authentication handler redirecting to `/dashboard`. | Redirect to `/dashboard?email={email}` |
| `GET` | `/contact` | Candidate support and inquiry submission page. | `contact.html` |
| `POST` | `/contact` | Support submission handler. | `contact.html` with confirmation |
| `GET` | `/profile` | Candidate profile view. | `profile.html` |

---

## 3. Candidate User Journeys

### Journey A: Multiple Choice Question (MCQ) Assessment
1. Candidate opens `/` or `/dashboard`.
2. Clicks **Start MCQ Assessment** on `assessment-python-se`.
3. Navigates questions using the numbered question palette or Next/Previous buttons.
4. Reads stated marking scheme (+4 for correct, -1 for incorrect, 0 for unattempted).
5. On Question 2, selects Option B (*triggers MCQ-01 value mismatch*).
6. Clicks **Submit Assessment** (*triggers MCQ-02 negative marking calculation*).
7. Arrives at `/results/{sub_id}` displaying score breakdown.
8. Re-submitting the test triggers *MCQ-03 score mutation*.

### Journey B: Hands-On Coding Assessment
1. Candidate opens `/assessments/assessment-python-se/coding`.
2. Reads problem specification, constraints, and sample test cases for *Two-Sum Target Indices*.
3. Writes code in the editor area.
4. Clicks **Run Code** to execute against public test cases.
5. Clicks **Submit Solution**.
   - If submitting code that passes only public test cases, *CODE-01* awards full 100/100 points, ignoring hidden edge cases.
   - If submitting a second updated solution, *CODE-02* reuses the previous submission's cached result.
