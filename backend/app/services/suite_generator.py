"""LLM-assisted assessment test-case generation service using Google Gemini 3.8 Flash.

Owner: Member C.
Coordinates test-suite generation from an AssessmentMap and relevant DOM evidence,
validates LLM proposals against deterministic schemas and whitelisted selectors,
and provides a rule-based fallback when Gemini is unconfigured or unavailable.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
import urllib.parse

from pydantic import BaseModel, Field

from app.agents.assessment_map import AssessmentMap
from app.core.agent_interface import AgentContext
from app.core.config import Settings
from app.core.constants import (
    AgentName,
    BrowserAction,
    ElementType,
    EventLevel,
    EventType,
    GenerationMode,
    LLMProvider,
)
from app.schemas.journey import Journey
from app.schemas.test_case import TestCase, TestStep

logger = logging.getLogger("code_apex.services.suite_generator")

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
MAX_SUITE_CASES = 5
MAX_STEPS_PER_CASE = 15


class LLMTestStep(BaseModel):
    """Schema for a single step proposed by the LLM."""

    index: int = Field(ge=1)
    action: str
    selector: str | None = None
    value: str | None = None
    url: str | None = None
    description: str | None = None


class LLMTestCase(BaseModel):
    """Schema for a test case proposed by the LLM."""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: int = Field(default=3, ge=1, le=5)
    steps: list[LLMTestStep] = Field(min_length=1, max_length=MAX_STEPS_PER_CASE)
    expected_result: str = Field(min_length=1, max_length=1000)


class LLMTestSuite(BaseModel):
    """Schema for the overall suite response expected from Gemini."""

    cases: list[LLMTestCase] = Field(default_factory=list, max_length=MAX_SUITE_CASES)


def get_gemini_api_key(settings: Settings | None = None) -> str:
    """Retrieve Gemini API key from settings or environment without logging secrets."""
    if settings:
        try:
            if hasattr(settings, "resolved_gemini_api_key") and settings.resolved_gemini_api_key:
                return settings.resolved_gemini_api_key
            val = settings.gemini_api_key.get_secret_value()
            if val:
                return val.strip().strip('"').strip("'")
        except Exception:
            pass
    for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env_var, "").strip().strip('"').strip("'")
        if val:
            return val
    return ""


def get_gemini_model() -> str:
    """Retrieve configured Gemini model ID with fallback to gemini-3.8-flash."""
    return os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


DEFAULT_NVIDIA_MODEL = "meta/llama-3.1-70b-instruct"
DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


def get_nvidia_api_key(settings: Settings | None = None) -> str:
    """Retrieve NVIDIA API key from settings or environment without logging secrets."""
    if settings and hasattr(settings, "resolved_nvidia_api_key") and settings.resolved_nvidia_api_key:
        return settings.resolved_nvidia_api_key
    return os.environ.get("NVIDIA_API_KEY", "").strip().strip('"').strip("'")


def get_nvidia_model(settings: Settings | None = None) -> str:
    """Retrieve configured NVIDIA model ID with fallback to meta/llama-3.1-70b-instruct."""
    if settings and hasattr(settings, "nvidia_model") and settings.nvidia_model:
        return settings.nvidia_model.strip()
    return os.environ.get("NVIDIA_MODEL", DEFAULT_NVIDIA_MODEL).strip() or DEFAULT_NVIDIA_MODEL


def get_nvidia_base_url(settings: Settings | None = None) -> str:
    """Retrieve configured NVIDIA Base URL."""
    if settings and hasattr(settings, "nvidia_base_url") and settings.nvidia_base_url:
        return settings.nvidia_base_url.strip()
    return os.environ.get("NVIDIA_BASE_URL", DEFAULT_NVIDIA_BASE_URL).strip() or DEFAULT_NVIDIA_BASE_URL


class SuiteGenerator:
    """Generates validated assessment test cases using NVIDIA NIM, Gemini, or deterministic fallback."""

    def __init__(
        self,
        model: str | None = None,
        client: Any = None,
    ) -> None:
        self.model = model
        self._client = client

    def _get_client(self, api_key: str) -> Any:
        if self._client is not None:
            return self._client
        from google import genai
        return genai.Client(api_key=api_key)

    def generate_suite(
        self,
        ctx: AgentContext,
        assessment_map: AssessmentMap | None,
        journeys: list[Journey],
    ) -> list[TestCase]:
        """Generate test cases via NVIDIA NIM or Gemini if configured, falling back to deterministic templates."""
        # 1. Resolve AssessmentMap (reconstructing from journeys if None)
        if assessment_map is None:
            assessment_map = AssessmentMap.from_journeys(journeys)

        if assessment_map is None or not assessment_map.is_assessment:
            logger.info("No assessment detected; using generic test generation.")
            return self._generate_generic_fallback(ctx, journeys)

        # 2. Determine active provider
        active_provider = (
            getattr(ctx.settings, "resolved_llm_provider", LLMProvider.NONE)
            if ctx.settings
            else LLMProvider.NONE
        )
        if active_provider == LLMProvider.NONE:
            if get_nvidia_api_key(ctx.settings):
                active_provider = LLMProvider.NVIDIA
            elif get_gemini_api_key(ctx.settings):
                active_provider = LLMProvider.GEMINI

        # 3. Collect whitelisted selectors and consequential controls
        whitelisted_selectors, consequential_selectors = self._extract_selectors(
            assessment_map, journeys
        )

        # 4. Handle NVIDIA provider
        if active_provider == LLMProvider.NVIDIA:
            nvidia_key = get_nvidia_api_key(ctx.settings)
            if not nvidia_key:
                ctx.emit(
                    EventType.AGENT_PROGRESS,
                    AgentName.TESTER,
                    "NVIDIA_API_KEY is not configured; using deterministic rule-based assessment test suite.",
                    level=EventLevel.INFO,
                    data={"reason": "missing_api_key", "provider": "nvidia"},
                )
                return self._generate_assessment_fallback(ctx, assessment_map, journeys)

            nvidia_model = self.model or get_nvidia_model(ctx.settings)
            base_url = get_nvidia_base_url(ctx.settings)
            attempts = 0
            last_error: Exception | None = None
            while attempts < 2:
                attempts += 1
                try:
                    ctx.emit(
                        EventType.AGENT_PROGRESS,
                        AgentName.TESTER,
                        f"Generating assessment test suite with NVIDIA NIM ({nvidia_model}, attempt {attempts}/2)...",
                        level=EventLevel.INFO,
                        data={"attempt": attempts, "model": nvidia_model, "provider": "nvidia"},
                    )

                    prompt = self._build_prompt(ctx.run.target_url, assessment_map, whitelisted_selectors)
                    raw_json = self._call_nvidia(nvidia_key, base_url, nvidia_model, prompt)

                    test_cases = self._validate_and_build_cases(
                        ctx=ctx,
                        raw_json=raw_json,
                        journeys=journeys,
                        whitelisted_selectors=whitelisted_selectors,
                        consequential_selectors=consequential_selectors,
                    )

                    if test_cases:
                        ctx.emit(
                            EventType.AGENT_PROGRESS,
                            AgentName.TESTER,
                            f"NVIDIA generated {len(test_cases)} valid assessment test case(s).",
                            level=EventLevel.INFO,
                            data={"test_cases_count": len(test_cases), "source": "nvidia"},
                        )
                        return test_cases
                    else:
                        raise ValueError("NVIDIA returned zero valid test cases after schema validation.")

                except Exception as exc:
                    last_error = exc
                    logger.warning(f"NVIDIA suite generation attempt {attempts} failed: {exc}")

            ctx.emit(
                EventType.AGENT_PROGRESS,
                AgentName.TESTER,
                f"NVIDIA test generation failed ({last_error}); activating deterministic assessment fallback.",
                level=EventLevel.WARNING,
                data={"error": str(last_error), "provider": "nvidia"},
            )
            return self._generate_assessment_fallback(ctx, assessment_map, journeys)

        # 5. Handle Gemini provider
        if active_provider == LLMProvider.GEMINI:
            api_key = get_gemini_api_key(ctx.settings)
            if not api_key:
                ctx.emit(
                    EventType.AGENT_PROGRESS,
                    AgentName.TESTER,
                    "GEMINI_API_KEY is not configured; using deterministic rule-based assessment test suite.",
                    level=EventLevel.INFO,
                    data={"reason": "missing_api_key", "provider": "gemini"},
                )
                return self._generate_assessment_fallback(ctx, assessment_map, journeys)

            gemini_model = self.model or get_gemini_model()
            attempts = 0
            last_error = None
            while attempts < 2:
                attempts += 1
                try:
                    ctx.emit(
                        EventType.AGENT_PROGRESS,
                        AgentName.TESTER,
                        f"Generating assessment test suite with Gemini ({gemini_model}, attempt {attempts}/2)...",
                        level=EventLevel.INFO,
                        data={"attempt": attempts, "model": gemini_model, "provider": "gemini"},
                    )

                    prompt = self._build_prompt(ctx.run.target_url, assessment_map, whitelisted_selectors)
                    raw_json = self._call_gemini(api_key, gemini_model, prompt)

                    test_cases = self._validate_and_build_cases(
                        ctx=ctx,
                        raw_json=raw_json,
                        journeys=journeys,
                        whitelisted_selectors=whitelisted_selectors,
                        consequential_selectors=consequential_selectors,
                    )

                    if test_cases:
                        ctx.emit(
                            EventType.AGENT_PROGRESS,
                            AgentName.TESTER,
                            f"Gemini generated {len(test_cases)} valid assessment test case(s).",
                            level=EventLevel.INFO,
                            data={"test_cases_count": len(test_cases), "source": "gemini"},
                        )
                        return test_cases
                    else:
                        raise ValueError("Gemini returned zero valid test cases after schema validation.")

                except Exception as exc:
                    last_error = exc
                    logger.warning(f"Gemini suite generation attempt {attempts} failed: {exc}")

            ctx.emit(
                EventType.AGENT_PROGRESS,
                AgentName.TESTER,
                f"Gemini test generation failed ({last_error}); activating deterministic assessment fallback.",
                level=EventLevel.WARNING,
                data={"error": str(last_error), "provider": "gemini"},
            )
            return self._generate_assessment_fallback(ctx, assessment_map, journeys)

        # 6. Fallback if no provider / key
        ctx.emit(
            EventType.AGENT_PROGRESS,
            AgentName.TESTER,
            "No LLM API key configured (NVIDIA_API_KEY or GEMINI_API_KEY); using deterministic rule-based assessment test suite.",
            level=EventLevel.INFO,
            data={"reason": "no_llm_key"},
        )
        return self._generate_assessment_fallback(ctx, assessment_map, journeys)

    def _call_nvidia(
        self,
        api_key: str,
        base_url: str,
        model: str,
        prompt: str,
    ) -> str:
        """Call NVIDIA OpenAI-compatible API to generate structured test cases."""
        import httpx

        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        system_msg = (
            "You are an assessment QA test-suite generator. You must return ONLY a JSON object "
            "matching the schema with a 'cases' array of test cases, each with 'title', 'description', "
            "'priority', 'steps' (index, action, selector, value, url, description), and 'expected_result'. "
            "Do NOT wrap output in markdown code blocks. Output raw JSON only."
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("NVIDIA API returned no choices in response.")
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                raise ValueError("NVIDIA API returned empty message content.")
            return content

    def _call_gemini(self, api_key: str, model: str, prompt: str) -> str:
        """Execute request via Google GenAI client with JSON output configuration."""
        client = self._get_client(api_key)
        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMTestSuite,
            temperature=0.2,
        )

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )

        text = getattr(response, "text", None)
        if not text:
            raise ValueError("Gemini returned an empty response.")
        return text

    def _extract_selectors(
        self,
        assessment_map: AssessmentMap,
        journeys: list[Journey],
    ) -> tuple[set[str], set[str]]:
        """Collect all known, observable selectors and consequential submit selectors."""
        whitelisted: set[str] = set()
        consequential: set[str] = set()

        if assessment_map.timer_selector:
            whitelisted.add(assessment_map.timer_selector)

        for sec in assessment_map.sections:
            if sec.selector:
                whitelisted.add(sec.selector)

        for q in assessment_map.questions:
            if q.selector:
                whitelisted.add(q.selector)
            for opt in q.options:
                if opt.selector:
                    whitelisted.add(opt.selector)
                if opt.input_selector:
                    whitelisted.add(opt.input_selector)

        for p in assessment_map.palette_items:
            if p.selector:
                whitelisted.add(p.selector)

        if assessment_map.code_editor:
            whitelisted.add(assessment_map.code_editor.container_selector)
            whitelisted.add(assessment_map.code_editor.input_selector)
            if assessment_map.code_editor.language_selector:
                whitelisted.add(assessment_map.code_editor.language_selector)
            if assessment_map.code_editor.run_button_selector:
                whitelisted.add(assessment_map.code_editor.run_button_selector)

        for act in assessment_map.action_controls:
            if act.selector:
                whitelisted.add(act.selector)
                if act.is_consequential:
                    consequential.add(act.selector)

        # Supplement with discovered elements from journeys
        for jny in journeys:
            for page in jny.pages:
                for elem in page.elements:
                    if elem.selector:
                        whitelisted.add(elem.selector)

        return whitelisted, consequential

    def _build_prompt(
        self,
        target_url: str,
        assessment_map: AssessmentMap,
        whitelisted_selectors: set[str],
    ) -> str:
        """Construct a compact, sanitized prompt detailing observable assessment facts."""
        summary = {
            "target_url": target_url,
            "has_timer": bool(assessment_map.timer_selector),
            "timer_selector": assessment_map.timer_selector,
            "timer_text": assessment_map.timer_text,
            "sections": [
                {"title": s.title, "selector": s.selector, "active": s.is_active}
                for s in assessment_map.sections
            ],
            "questions": [
                {
                    "number": q.number,
                    "text": q.text[:120],
                    "selector": q.selector,
                    "type": q.question_type,
                    "options": [
                        {"selector": o.selector, "label": o.label, "is_radio": o.is_radio}
                        for o in q.options
                    ],
                }
                for q in assessment_map.questions[:5]
            ],
            "palette": [
                {"number": p.number, "selector": p.selector, "state": p.state.value}
                for p in assessment_map.palette_items[:8]
            ],
            "code_editor": (
                {
                    "editor_selector": assessment_map.code_editor.input_selector,
                    "run_selector": assessment_map.code_editor.run_button_selector,
                    "lang_selector": assessment_map.code_editor.language_selector,
                }
                if assessment_map.code_editor
                else None
            ),
            "actions": [
                {"type": a.action_type, "selector": a.selector, "consequential": a.is_consequential}
                for a in assessment_map.action_controls
            ],
            "allowed_selectors": sorted(list(whitelisted_selectors))[:60],
        }

        return f"""You are a QA automation engineer testing an online assessment / exam web application.
Based on the verified DOM evidence below, propose up to {MAX_SUITE_CASES} high-value test cases.

DOM EVIDENCE:
{json.dumps(summary, indent=2)}

STRICT REQUIREMENTS:
1. ONLY propose test steps using selectors from 'allowed_selectors'. DO NOT invent any selectors.
2. ALLOWED ACTIONS: navigate, click, fill, select, check, uncheck, wait, assert_visible, assert_text, assert_url.
3. CONTEXT SAFETY: You MUST NEVER click submit or finish controls. Only assert their visibility.
4. TEST FOCUS AREAS:
   - MCQ option selection and mutually exclusive option checks (check option A, then check option B).
   - Question palette visibility and navigation.
   - Timer countdown visibility and formatting.
   - Code editor presence, language selection, and run button presence (if present).
   - Section switching or Save & Next / Mark for Review actions.
   - Submission control visibility without submitting.
5. Each test case must have numbered steps starting from 1 (1, 2, 3...).
6. Output MUST strictly match the requested JSON schema.
"""

    def _validate_and_build_cases(
        self,
        ctx: AgentContext,
        raw_json: str,
        journeys: list[Journey],
        whitelisted_selectors: set[str],
        consequential_selectors: set[str],
    ) -> list[TestCase]:
        clean_json = raw_json.strip()
        if clean_json.startswith("```"):
            clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json, flags=re.MULTILINE)
            clean_json = re.sub(r"\s*```$", "", clean_json, flags=re.MULTILINE).strip()
        data = json.loads(clean_json)
        suite = LLMTestSuite.model_validate(data)

        validated_cases: list[TestCase] = []
        journey_id = journeys[0].id if journeys else None
        target_url = ctx.run.target_url
        max_tests = min(ctx.run.max_tests, MAX_SUITE_CASES)

        for case_idx, llm_case in enumerate(suite.cases):
            if len(validated_cases) >= max_tests:
                break

            valid_steps: list[TestStep] = []
            for step_idx, s in enumerate(llm_case.steps, start=1):
                if len(valid_steps) >= MAX_STEPS_PER_CASE:
                    break

                try:
                    action = BrowserAction(s.action.strip().lower())
                except ValueError:
                    logger.debug(f"Discarding step with unknown action: {s.action}")
                    continue

                selector = s.selector.strip() if s.selector else None
                url = s.url.strip() if s.url else None
                value = s.value

                # Filter unknown selectors
                if action in (
                    BrowserAction.CLICK,
                    BrowserAction.FILL,
                    BrowserAction.CHECK,
                    BrowserAction.UNCHECK,
                    BrowserAction.SELECT,
                    BrowserAction.ASSERT_VISIBLE,
                    BrowserAction.ASSERT_TEXT,
                ):
                    if not selector or selector not in whitelisted_selectors:
                        logger.debug(f"Discarding step targeting unwhitelisted selector: {selector}")
                        continue

                # Safety: prevent clicks on consequential submit buttons
                if selector in consequential_selectors and action in (
                    BrowserAction.CLICK,
                    BrowserAction.CHECK,
                    BrowserAction.FILL,
                ):
                    action = BrowserAction.ASSERT_VISIBLE
                    s.description = f"Verify submit button visibility ({selector})"

                # Provide URL if navigate action
                if action == BrowserAction.NAVIGATE and not url:
                    url = target_url

                # Validate step creation
                try:
                    step = TestStep(
                        index=len(valid_steps) + 1,
                        action=action,
                        selector=selector,
                        value=str(value) if value is not None else None,
                        url=url,
                        description=s.description or f"Execute {action.value}",
                    )
                    valid_steps.append(step)
                except Exception as step_err:
                    logger.debug(f"Step validation failed: {step_err}")
                    continue

            # Case must have at least 1 valid step
            if not valid_steps:
                continue

            # Ensure navigation exists as first step if not present
            if valid_steps[0].action != BrowserAction.NAVIGATE:
                nav_step = TestStep(
                    index=1,
                    action=BrowserAction.NAVIGATE,
                    url=target_url,
                    description=f"Open {target_url}",
                )
                # Re-index existing steps
                reindexed: list[TestStep] = [nav_step]
                for idx, st in enumerate(valid_steps, start=2):
                    st_copy = st.model_copy(update={"index": idx})
                    reindexed.append(st_copy)
                valid_steps = reindexed[:MAX_STEPS_PER_CASE]

            test_case = TestCase(
                run_id=ctx.run.id,
                journey_id=journey_id,
                title=llm_case.title[:200],
                description=llm_case.description,
                priority=llm_case.priority,
                steps=valid_steps,
                expected_result=llm_case.expected_result[:1000],
                generated_by=GenerationMode.LLM,
            )
            validated_cases.append(test_case)

        return validated_cases

    # ---------- Deterministic Fallbacks ----------

    def _generate_assessment_fallback(
        self,
        ctx: AgentContext,
        assessment_map: AssessmentMap,
        journeys: list[Journey],
    ) -> list[TestCase]:
        """Deterministic, rule-based fallback generating assessment test cases."""
        cases: list[TestCase] = []
        run_id = ctx.run.id
        journey_id = journeys[0].id if journeys else None
        target_url = ctx.run.target_url

        def _find_url(sel: str | None, hint: str = "") -> str:
            if sel:
                for j in journeys:
                    for p in j.pages:
                        for elem in p.elements:
                            if elem.selector == sel:
                                return p.url
            if hint:
                for j in journeys:
                    for p in j.pages:
                        if hint.lower() in p.url.lower():
                            return p.url
            return assessment_map.url or target_url

        # 1. Timer & Header verification
        if assessment_map.timer_selector:
            timer_url = _find_url(assessment_map.timer_selector, "assessment")
            steps = [
                TestStep(index=1, action=BrowserAction.NAVIGATE, url=timer_url, description=f"Open {timer_url}"),
                TestStep(index=2, action=BrowserAction.ASSERT_VISIBLE, selector=assessment_map.timer_selector, description="Verify timer visibility"),
                TestStep(index=3, action=BrowserAction.ASSERT_TEXT, selector=assessment_map.timer_selector, value=":", description="Verify timer shows countdown format"),
            ]
            cases.append(
                TestCase(
                    run_id=run_id,
                    journey_id=journey_id,
                    title="Verify Assessment Timer and Header Controls",
                    description="Checks that the countdown timer is visible and formatted properly.",
                    priority=1,
                    steps=steps,
                    expected_result="Timer is visible and actively displaying countdown format.",
                    generated_by=GenerationMode.RULE_BASED,
                )
            )

        # 2. MCQ Option selection & interaction
        if assessment_map.questions and assessment_map.questions[0].options:
            q = assessment_map.questions[0]
            opt = q.options[0]
            mcq_url = _find_url(opt.selector, "mcq")
            steps = [
                TestStep(index=1, action=BrowserAction.NAVIGATE, url=mcq_url, description=f"Open {mcq_url}"),
                TestStep(index=2, action=BrowserAction.ASSERT_VISIBLE, selector=opt.selector, description=f"Verify option {opt.label}"),
                TestStep(index=3, action=BrowserAction.CHECK if opt.is_radio else BrowserAction.CLICK, selector=opt.selector, description=f"Select option {opt.label}"),
            ]
            cases.append(
                TestCase(
                    run_id=run_id,
                    journey_id=journey_id,
                    title="Verify MCQ Option Selection",
                    description=f"Select option '{opt.label}' on question {q.number or 1}.",
                    priority=2,
                    steps=steps,
                    expected_result="Option is selectable without error.",
                    generated_by=GenerationMode.RULE_BASED,
                )
            )

        # 3. Question Palette verification
        if assessment_map.palette_items:
            pal = assessment_map.palette_items[0]
            pal_url = _find_url(pal.selector, "mcq")
            steps = [
                TestStep(index=1, action=BrowserAction.NAVIGATE, url=pal_url, description=f"Open {pal_url}"),
                TestStep(index=2, action=BrowserAction.ASSERT_VISIBLE, selector=pal.selector, description=f"Verify palette item {pal.number}"),
            ]
            cases.append(
                TestCase(
                    run_id=run_id,
                    journey_id=journey_id,
                    title="Verify Question Palette Display",
                    description=f"Ensure question palette item {pal.number} is rendered.",
                    priority=3,
                    steps=steps,
                    expected_result="Palette item is visible and interactive.",
                    generated_by=GenerationMode.RULE_BASED,
                )
            )

        # 4. Code Editor verification (if present)
        if assessment_map.code_editor:
            editor = assessment_map.code_editor
            editor_url = _find_url(editor.container_selector, "coding")
            steps = [
                TestStep(index=1, action=BrowserAction.NAVIGATE, url=editor_url, description=f"Open {editor_url}"),
                TestStep(index=2, action=BrowserAction.ASSERT_VISIBLE, selector=editor.container_selector, description="Verify code editor container"),
            ]
            if editor.run_button_selector:
                steps.append(
                    TestStep(index=3, action=BrowserAction.ASSERT_VISIBLE, selector=editor.run_button_selector, description="Verify run code button")
                )
            cases.append(
                TestCase(
                    run_id=run_id,
                    journey_id=journey_id,
                    title="Verify Code Editor Environment",
                    description="Ensure coding challenge container and run controls are visible.",
                    priority=2,
                    steps=steps,
                    expected_result="Code editor is loaded and accessible.",
                    generated_by=GenerationMode.RULE_BASED,
                )
            )

        # 5. Safe Submission Control visibility (never click)
        submit_ctrl = next((a for a in assessment_map.action_controls if a.is_consequential), None)
        if submit_ctrl:
            submit_url = _find_url(submit_ctrl.selector, "mcq")
            steps = [
                TestStep(index=1, action=BrowserAction.NAVIGATE, url=submit_url, description=f"Open {submit_url}"),
                TestStep(index=2, action=BrowserAction.ASSERT_VISIBLE, selector=submit_ctrl.selector, description="Verify submit button visibility"),
            ]
            cases.append(
                TestCase(
                    run_id=run_id,
                    journey_id=journey_id,
                    title="Verify Submission Controls Without Submitting",
                    description="Ensure submission control is present and visible without triggering submission.",
                    priority=1,
                    steps=steps,
                    expected_result="Submission button is rendered and visible.",
                    generated_by=GenerationMode.RULE_BASED,
                )
            )

        # Ensure at least 1 baseline case exists
        if not cases:
            cases = self._generate_generic_fallback(ctx, journeys)

        return cases[:ctx.run.max_tests]

    def _generate_generic_fallback(
        self,
        ctx: AgentContext,
        journeys: list[Journey],
    ) -> list[TestCase]:
        """Generic fallback for non-assessment web pages."""
        cases: list[TestCase] = []
        target_url = ctx.run.target_url
        path = urllib.parse.urlparse(target_url).path or "/"

        steps = [
            TestStep(index=1, action=BrowserAction.NAVIGATE, url=target_url, description=f"Navigate to {target_url}"),
            TestStep(index=2, action=BrowserAction.ASSERT_URL, value=path, description=f"Assert URL path contains '{path}'"),
        ]
        cases.append(
            TestCase(
                run_id=ctx.run.id,
                journey_id=journeys[0].id if journeys else None,
                title=f"Smoke navigation to {target_url}"[:200],
                description="Verify that the root target URL loads successfully.",
                priority=1,
                steps=steps,
                expected_result="Page loads with valid URL path.",
                generated_by=GenerationMode.RULE_BASED,
            )
        )
        return cases
