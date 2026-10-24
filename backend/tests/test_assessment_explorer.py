"""Focused tests for assessment-aware ExplorerAgent discovery.

Owner: Member C.
Verifies discovery of online assessment elements:
- MCQ questions and options
- Sections and action controls
- Timer and question palette (with evidence-backed state assignment)
- Code editor detection
- Graceful handling of missing/partial elements
- Generic website fallback
- Non-consequential execution (submit buttons never clicked)
- Clean browser resource management and Journey contract compliance.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from app.agents.assessment_map import PaletteState
from app.agents.explorer import ExplorerAgent
from app.core.agent_interface import AgentContext
from app.core.config import get_settings
from app.core.constants import ElementType, GenerationMode
from app.schemas.journey import Journey
from app.schemas.run import RunResponse
from app.services.browser_driver import BrowserDriver


def _make_context(
    tmp_path: Path,
    target_url: str = "http://test.local",
    max_pages: int = 1,
    max_depth: int = 1,
) -> tuple[AgentContext, list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []

    def mock_emit(event_type: Any, agent: Any, message: str, level: Any = None, data: Any = None) -> None:
        events.append({"event_type": event_type, "agent": agent, "message": message, "data": data})

    run = RunResponse(
        target_url=target_url,
        max_pages=max_pages,
        max_depth=max_depth,
        max_tests=5,
    )
    ctx = AgentContext(
        run=run,
        settings=get_settings(),
        evidence_dir=tmp_path,
        emit=mock_emit,
    )
    return ctx, events


def test_assessment_mcq_and_questions(tmp_path: Path) -> None:
    """Verify discovery of instructions, question text, number, and MCQ options."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        await driver.start(headless=True)
        html = """<!DOCTYPE html>
        <html>
        <head><title>Exam: Software Engineering</title></head>
        <body>
            <div id="instructions" class="exam-rules">
                <h3>General Instructions</h3>
                <p>Read all questions carefully before submitting.</p>
            </div>
            <div id="question-1" class="question">
                <h3 class="question-text">Question 1: Which data structure uses LIFO?</h3>
                <div class="options">
                    <label><input type="radio" name="q1" id="q1-opt1" value="Queue"> Queue</label>
                    <label><input type="radio" name="q1" id="q1-opt2" value="Stack"> Stack</label>
                    <label><input type="radio" name="q1" id="q1-opt3" value="Array"> Array</label>
                    <label><input type="radio" name="q1" id="q1-opt4" value="Tree"> Tree</label>
                </div>
            </div>
        </body>
        </html>"""
        await driver.page.set_content(html)

        explorer = ExplorerAgent(driver=driver)
        dom_summary = await driver.get_dom_summary()
        amap = await explorer._discover_assessment(driver, "http://test.local", dom_summary)

        assert amap.is_assessment is True
        assert len(amap.instructions) >= 1
        assert "General Instructions" in amap.instructions[0]

        assert len(amap.questions) == 1
        q = amap.questions[0]
        assert q.number == "1"
        assert "Which data structure uses LIFO?" in q.text
        assert q.question_type == "mcq"

        assert len(q.options) == 4
        assert q.options[0].value == "Queue"
        assert q.options[1].value == "Stack"
        assert all(opt.is_radio for opt in q.options)

        await driver.close()

    asyncio.run(_test())


def test_assessment_sections_and_navigation(tmp_path: Path) -> None:
    """Verify discovery of section headings/tabs and assessment navigation controls."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        await driver.start(headless=True)
        html = """<!DOCTYPE html>
        <html>
        <body>
            <nav class="nav-tabs" role="tablist">
                <button class="nav-link active" role="tab" id="sec-1" aria-selected="true">Section A: Aptitude</button>
                <button class="nav-link" role="tab" id="sec-2" aria-selected="false">Section B: Coding</button>
            </nav>
            <div class="question"><p>Question 1: Sample prompt</p></div>
            <div class="controls">
                <button id="btn-prev">Previous</button>
                <button id="btn-save">Save & Next</button>
                <button id="btn-mark">Mark for Review</button>
                <button id="btn-clear">Clear Response</button>
                <button id="btn-next">Next</button>
                <button id="btn-submit" class="btn-danger">Submit Exam</button>
            </div>
        </body>
        </html>"""
        await driver.page.set_content(html)

        explorer = ExplorerAgent(driver=driver)
        dom_summary = await driver.get_dom_summary()
        amap = await explorer._discover_assessment(driver, "http://test.local", dom_summary)

        assert amap.is_assessment is True
        assert len(amap.sections) == 2
        assert "Section A: Aptitude" in amap.sections[0].title
        assert amap.sections[0].is_active is True
        assert "Section B: Coding" in amap.sections[1].title
        assert amap.sections[1].is_active is False

        # Check action controls
        action_types = {act.action_type for act in amap.action_controls}
        assert "previous" in action_types
        assert "save" in action_types
        assert "mark_review" in action_types
        assert "clear" in action_types
        assert "next" in action_types
        assert "submit" in action_types

        submit_act = next(a for a in amap.action_controls if a.action_type == "submit")
        assert submit_act.is_consequential is True

        await driver.close()

    asyncio.run(_test())


def test_assessment_timer_and_palette_states(tmp_path: Path) -> None:
    """Verify timer display and palette items with strictly evidence-based states."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        await driver.start(headless=True)
        html = """<!DOCTYPE html>
        <html>
        <body>
            <div id="timer" class="countdown">Time Left: 45:30</div>
            <div class="question-palette">
                <button id="pal-1" class="palette-item answered" data-status="answered">1</button>
                <button id="pal-2" class="palette-item marked" data-status="marked">2</button>
                <button id="pal-3" class="palette-item current" aria-current="true">3</button>
                <button id="pal-4" class="palette-item unanswered" data-status="unanswered">4</button>
                <button id="pal-5" class="palette-item not-visited" data-status="unvisited">5</button>
                <button id="pal-6" class="palette-item">6</button>
            </div>
        </body>
        </html>"""
        await driver.page.set_content(html)

        explorer = ExplorerAgent(driver=driver)
        dom_summary = await driver.get_dom_summary()
        amap = await explorer._discover_assessment(driver, "http://test.local", dom_summary)

        assert amap.is_assessment is True
        assert amap.timer_selector is not None
        assert "45:30" in (amap.timer_text or "")

        assert len(amap.palette_items) == 6
        states = {item.number: item.state for item in amap.palette_items}
        assert states["1"] == PaletteState.ANSWERED
        assert states["2"] == PaletteState.MARKED_FOR_REVIEW
        assert states["3"] == PaletteState.CURRENT
        assert states["4"] == PaletteState.UNANSWERED
        assert states["5"] == PaletteState.NOT_VISITED
        # Item 6 has no observable status markers; must remain UNKNOWN without guessing
        assert states["6"] == PaletteState.UNKNOWN

        await driver.close()

    asyncio.run(_test())


def test_assessment_code_editor_detection(tmp_path: Path) -> None:
    """Verify detection of code editor container, language selector, and run button."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        await driver.start(headless=True)
        html = """<!DOCTYPE html>
        <html>
        <body>
            <div class="question" id="q-coding">
                <h3>Question 1: Implement binary search</h3>
                <select class="language" name="language_select">
                    <option value="python" selected>Python 3</option>
                    <option value="cpp">C++</option>
                </select>
                <div class="monaco-editor" id="monaco-container">
                    <textarea id="code-input" class="code-editor"></textarea>
                </div>
                <button id="btn-run-code" data-testid="run-btn" class="btn-run">Run Code</button>
            </div>
        </body>
        </html>"""
        await driver.page.set_content(html)

        explorer = ExplorerAgent(driver=driver)
        dom_summary = await driver.get_dom_summary()
        amap = await explorer._discover_assessment(driver, "http://test.local", dom_summary)

        assert amap.is_assessment is True
        assert amap.code_editor is not None
        editor = amap.code_editor
        assert "monaco" in editor.container_selector.lower()
        assert "code" in editor.input_selector.lower()
        assert editor.language_selector is not None
        assert editor.run_button_selector is not None
        assert editor.detected_language == "python"

        await driver.close()

    asyncio.run(_test())


def test_assessment_missing_elements_graceful(tmp_path: Path) -> None:
    """Ensure missing timer, code editor, or palette does not crash exploration."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        await driver.start(headless=True)
        # Minimal assessment page with only a question
        html = """<!DOCTYPE html>
        <html>
        <body>
            <div class="question">
                <p>Question 1: Simple trivia question?</p>
                <input type="radio" name="opt" value="yes"> Yes
            </div>
        </body>
        </html>"""
        await driver.page.set_content(html)

        explorer = ExplorerAgent(driver=driver)
        dom_summary = await driver.get_dom_summary()
        amap = await explorer._discover_assessment(driver, "http://test.local", dom_summary)

        assert amap.is_assessment is True
        assert amap.timer_selector is None
        assert amap.code_editor is None
        assert len(amap.sections) == 0
        assert len(amap.palette_items) == 0
        assert len(amap.questions) == 1

        await driver.close()

    asyncio.run(_test())


def test_generic_website_fallback(tmp_path: Path) -> None:
    """Ensure generic websites without assessment elements retain standard BFS crawl behavior."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        await driver.start(headless=True)
        html = """<!DOCTYPE html>
        <html>
        <head><title>Acme Corporation</title></head>
        <body>
            <h1>Welcome to Acme</h1>
            <p>We build tools and enterprise software.</p>
            <a href="http://test.local/about">About Us</a>
            <a href="http://test.local/contact">Contact Us</a>
        </body>
        </html>"""
        await driver.page.set_content(html)

        explorer = ExplorerAgent(driver=driver)
        dom_summary = await driver.get_dom_summary()
        amap = await explorer._discover_assessment(driver, "http://test.local", dom_summary)

        # Must not falsely flag standard website as an assessment
        assert amap.is_assessment is False
        assert len(amap.questions) == 0
        assert len(amap.sections) == 0

        await driver.close()

    asyncio.run(_test())


def test_consequential_controls_never_clicked(tmp_path: Path) -> None:
    """Guarantee that submit/finish buttons are never clicked during exploration."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        await driver.start(headless=True)
        html = """<!DOCTYPE html>
        <html>
        <body>
            <div class="question"><p>Question 1: Prompt</p></div>
            <button id="btn-submit" onclick="window.SUBMIT_CLICKED=true">Submit Exam</button>
            <button id="btn-finish" onclick="window.FINISH_CLICKED=true">Finish Test</button>
        </body>
        </html>"""
        await driver.page.set_content(html)

        explorer = ExplorerAgent(driver=driver)
        dom_summary = await driver.get_dom_summary()
        amap = await explorer._discover_assessment(driver, "http://test.local", dom_summary)

        assert amap.is_assessment is True
        # Verify submit actions detected as consequential
        for action in amap.action_controls:
            if action.action_type == "submit":
                assert action.is_consequential is True

        # Verify page state was never altered
        was_submitted = await driver.page.evaluate("() => window.SUBMIT_CLICKED || false")
        was_finished = await driver.page.evaluate("() => window.FINISH_CLICKED || false")
        assert was_submitted is False
        assert was_finished is False

        await driver.close()

    asyncio.run(_test())


def test_journey_contract_compliance_with_assessment(tmp_path: Path) -> None:
    """Verify that exploration produces a valid Journey adhering strictly to shared schemas."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        await driver.start(headless=True)
        html = """<!DOCTYPE html>
        <html>
        <head><title>Online Quiz</title></head>
        <body>
            <div id="timer">10:00</div>
            <div class="question">
                <p>Question 1: What is the capital of France?</p>
                <input type="radio" name="q1" id="opt-paris" value="Paris">
            </div>
            <div class="question-palette">
                <button class="palette-item answered">1</button>
            </div>
            <button id="btn-next">Next</button>
        </body>
        </html>"""
        await driver.page.set_content(html)

        ctx, events = _make_context(tmp_path, target_url="http://test.local")
        explorer = ExplorerAgent(driver=driver)

        # Direct journey construction check
        dom_summary = await driver.get_dom_summary()
        amap = await explorer._discover_assessment(driver, "http://test.local", dom_summary)
        elements = explorer._convert_assessment_to_elements(amap, dom_summary)
        from app.schemas.journey import DiscoveredPage

        page = DiscoveredPage(
            url="http://test.local",
            title="Online Quiz",
            depth=0,
            elements=elements,
        )
        journeys = explorer._build_journeys(ctx.run.id, "http://test.local", [page], max_tests=5, assessment_map=amap)

        assert len(journeys) == 1
        jny = journeys[0]
        assert isinstance(jny, Journey)
        assert jny.run_id == ctx.run.id
        assert "Assessment Flow" in jny.name
        assert jny.priority == 1
        assert jny.generated_by == GenerationMode.RULE_BASED
        assert len(jny.pages) == 1

        # Check interactive element types are standard ElementType enum members
        elem_types = {e.element_type for e in jny.pages[0].elements}
        assert ElementType.RADIO in elem_types
        assert ElementType.BUTTON in elem_types
        assert ElementType.OTHER in elem_types

        await driver.close()

    asyncio.run(_test())
