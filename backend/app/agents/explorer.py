"""Assessment-Aware Rule-based BFS Explorer Agent for Code Apex.

Owner: Member C.
Discovers reachable web pages and interactive elements starting from
ctx.run.target_url, respecting maximum page count and depth limits.
Detects online assessment structures (instructions, questions, MCQ options,
sections, question palette, timer, code editor, navigation/submit controls,
and results) and synthesizes an AssessmentMap while preserving backward-compatible
Journey outputs for the QA pipeline.
"""

from __future__ import annotations

import asyncio
from collections import deque
import concurrent.futures
import logging
import re
from typing import Any
import urllib.parse

from app.agents.assessment_map import (
    AssessmentActionControl,
    AssessmentMap,
    AssessmentOption,
    AssessmentQuestion,
    AssessmentSection,
    CodeEditorInfo,
    PaletteItem,
    PaletteState,
)
from app.core.agent_interface import AgentContext
from app.core.constants import (
    AgentName,
    ElementType,
    EventLevel,
    EventType,
    GenerationMode,
)
from app.schemas.journey import DiscoveredPage, InteractiveElement, Journey
from app.services.browser_driver import BrowserDriver

logger = logging.getLogger("code_apex.agents.explorer")


def _run_async(coro: Any) -> Any:
    """Safely execute an asynchronous coroutine from synchronous code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class ExplorerAgent:
    """Autonomous explorer utilizing rule-based BFS to crawl a target application."""

    def __init__(self, driver: BrowserDriver | None = None) -> None:
        self._driver = driver
        self._last_assessment_map: AssessmentMap | None = None

    @property
    def last_assessment_map(self) -> AssessmentMap | None:
        """Access the most recently discovered AssessmentMap, if any."""
        return self._last_assessment_map

    def explore(self, ctx: AgentContext) -> list[Journey]:
        """Synchronously explore the application and return a list of Journeys."""
        return _run_async(self._async_explore(ctx))

    async def _async_explore(self, ctx: AgentContext) -> list[Journey]:
        run_id = ctx.run.id
        start_url = ctx.run.target_url.strip()
        max_pages = ctx.run.max_pages
        max_depth = ctx.run.max_depth
        self._last_assessment_map = None

        start_parsed = urllib.parse.urlparse(start_url)
        if not start_parsed.scheme or not start_parsed.netloc:
            raise ValueError(f"Invalid target URL: {start_url!r}")

        base_origin = f"{start_parsed.scheme}://{start_parsed.netloc}".lower()

        driver = self._driver or BrowserDriver(
            evidence_dir=ctx.evidence_dir, settings=ctx.settings
        )

        ctx.emit(
            EventType.AGENT_PROGRESS,
            AgentName.EXPLORER,
            f"Explorer started exploration at {start_url} (max pages: {max_pages}, max depth: {max_depth}).",
            level=EventLevel.INFO,
            data={"target_url": start_url, "max_pages": max_pages, "max_depth": max_depth},
        )

        discovered_pages: list[DiscoveredPage] = []
        normalized_start = self._normalize_url(start_url, start_url, base_origin) or start_url
        visited_urls: set[str] = {normalized_start}
        queue: deque[tuple[str, int]] = deque([(normalized_start, 0)])

        try:
            await driver.start(headless=True)

            while queue and len(discovered_pages) < max_pages:
                current_url, depth = queue.popleft()

                try:
                    page_info = await driver.open(current_url)
                    status_code = page_info.get("status", 200)
                    if status_code and status_code >= 400:
                        ctx.emit(
                            EventType.AGENT_PROGRESS,
                            AgentName.EXPLORER,
                            f"HTTP {status_code} encountered on {current_url}",
                            level=EventLevel.WARNING,
                            data={"url": current_url, "status": status_code},
                        )
                except Exception as exc:
                    ctx.emit(
                        EventType.AGENT_PROGRESS,
                        AgentName.EXPLORER,
                        f"Navigation failed for {current_url}: {exc}",
                        level=EventLevel.WARNING,
                        data={"url": current_url, "error": str(exc)},
                    )
                    continue

                dom_summary = await driver.get_dom_summary()
                title = dom_summary.get("title") or page_info.get("title") or current_url

                # Attempt assessment discovery
                assessment_map = await self._discover_assessment(driver, current_url, dom_summary)

                if assessment_map.is_assessment:
                    self._last_assessment_map = assessment_map
                    elements = self._convert_assessment_to_elements(assessment_map, dom_summary)
                    ctx.emit(
                        EventType.AGENT_PROGRESS,
                        AgentName.EXPLORER,
                        f"Assessment detected on {current_url}: "
                        f"{len(assessment_map.questions)} question(s), "
                        f"{len(assessment_map.sections)} section(s), "
                        f"{len(assessment_map.palette_items)} palette item(s).",
                        level=EventLevel.INFO,
                        data={
                            "url": current_url,
                            "questions_count": len(assessment_map.questions),
                            "sections_count": len(assessment_map.sections),
                            "palette_count": len(assessment_map.palette_items),
                            "has_timer": assessment_map.timer_selector is not None,
                            "has_code_editor": assessment_map.code_editor is not None,
                        },
                    )
                else:
                    elements = self._extract_interactive_elements(dom_summary)

                page = DiscoveredPage(
                    url=current_url[:1000],
                    title=title[:300] if title else None,
                    depth=depth,
                    elements=elements,
                )
                discovered_pages.append(page)

                ctx.emit(
                    EventType.AGENT_PROGRESS,
                    AgentName.EXPLORER,
                    f"Discovered page: {current_url} (depth {depth}) with {len(elements)} interactive element(s).",
                    level=EventLevel.INFO,
                    data={"url": current_url, "depth": depth, "elements_count": len(elements)},
                )

                # Enqueue internal links if depth limit allows
                if depth < max_depth:
                    for link_data in dom_summary.get("links", []):
                        raw_href = link_data.get("href")
                        if not raw_href:
                            continue
                        normalized = self._normalize_url(raw_href, current_url, base_origin)
                        if normalized and normalized not in visited_urls:
                            visited_urls.add(normalized)
                            if len(visited_urls) <= max_pages * 3:
                                queue.append((normalized, depth + 1))

        finally:
            await driver.close()

        if not discovered_pages:
            raise RuntimeError(f"Explorer could not discover any reachable pages at {start_url}.")

        journeys = self._build_journeys(
            run_id, start_url, discovered_pages, ctx.run.max_tests, self._last_assessment_map
        )

        ctx.emit(
            EventType.AGENT_PROGRESS,
            AgentName.EXPLORER,
            f"Exploration finished: {len(discovered_pages)} page(s) discovered, {len(journeys)} journey(s) formed.",
            level=EventLevel.INFO,
            data={"pages_count": len(discovered_pages), "journeys_count": len(journeys)},
        )

        return journeys

    def _normalize_url(self, raw_url: str, current_page_url: str, base_origin: str) -> str | None:
        """Resolve, validate origin, and normalize a URL to prevent duplicate visits."""
        if not raw_url:
            return None

        stripped_lower = raw_url.strip().lower()
        if stripped_lower.startswith(("javascript:", "mailto:", "tel:", "data:", "#")):
            return None

        # Reject unpopulated template or JavaScript null/undefined interpolations
        if stripped_lower in ("null", "/null", "undefined", "/undefined", "none", "/none", "[object object]", "false", "true"):
            return None

        resolved = urllib.parse.urljoin(current_page_url, raw_url.strip())
        parsed = urllib.parse.urlparse(resolved)

        if parsed.scheme not in ("http", "https"):
            return None

        hostname = (parsed.hostname or "").lower().strip()
        if hostname in ("169.254.169.254", "metadata.google.internal", "instance-data", "169.254.169.253"):
            return None

        # Reject path segments that are unpopulated null/undefined
        path_segments = [s.strip().lower() for s in parsed.path.split("/") if s.strip()]
        if any(seg in ("null", "undefined", "[object object]", "none") for seg in path_segments):
            return None

        resolved_origin = f"{parsed.scheme}://{parsed.netloc}".lower()
        if resolved_origin != base_origin:
            return None

        path = parsed.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")

        return urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            parsed.query,
            "",
        ))

    # ---------- Assessment Discovery ----------

    async def _discover_assessment(
        self,
        driver: BrowserDriver,
        url: str,
        dom_summary: dict[str, Any],
    ) -> AssessmentMap:
        """Inspect page to identify assessment structures via DOM evaluation or DOM summary."""
        page = getattr(driver, "page", None)
        if page is not None and not getattr(page, "is_closed", lambda: True)():
            try:
                raw_data = await page.evaluate(self._assessment_discovery_script())
                return self._parse_assessment_eval_data(url, dom_summary.get("title"), raw_data)
            except Exception as exc:
                logger.debug(f"In-page assessment evaluation failed; falling back to DOM summary: {exc}")

        # Offline / Mock fallback using dom_summary structure
        return self._detect_assessment_from_dom_summary(url, dom_summary)

    @staticmethod
    def _assessment_discovery_script() -> str:
        """Client-side JavaScript to inspect assessment elements without clicking controls."""
        return """() => {
            // 1. Instructions
            const instructionEls = Array.from(document.querySelectorAll(
                '.instruction, .instructions, #instructions, [data-testid*="instruction" i], .rules, #rules, .exam-rules, .guidelines, [aria-label*="instruction" i]'
            ));
            const instructions = instructionEls.map(el => (el.innerText || el.textContent || '').trim()).filter(t => t.length > 0).slice(0, 10);
            const instructionSelectors = instructionEls.map(el => el.id ? `#${el.id}` : (el.className ? `.${el.className.split(' ')[0]}` : '')).filter(Boolean);

            // 2. Sections
            const sectionEls = Array.from(document.querySelectorAll(
                '[data-testid*="section" i], .section-tab, .section-header, .exam-section, [role="tab"], .nav-tabs .nav-link'
            ));
            const sections = sectionEls.map((el, i) => ({
                title: (el.innerText || el.textContent || '').trim(),
                selector: el.id ? `#${el.id}` : (el.getAttribute('data-testid') ? `[data-testid="${el.getAttribute('data-testid')}"]` : (el.className ? `.${el.className.split(' ')[0]}:nth-of-type(${i+1})` : `[role="tab"]:nth-of-type(${i+1})`)),
                id: el.id || null,
                is_active: el.classList.contains('active') || el.getAttribute('aria-selected') === 'true'
            })).filter(s => s.title.length > 0 && s.selector);

            // 3. Questions and MCQ options
            const questionEls = Array.from(document.querySelectorAll(
                '.question, .question-container, .question-block, [data-testid*="question" i], [id^="question-"], .exam-question'
            ));
            const questions = [];
            questionEls.forEach((qEl, qIdx) => {
                const textEl = qEl.querySelector('.question-text, .question-title, .q-text, h3, h4, p') || qEl;
                const text = (textEl.innerText || textEl.textContent || '').trim();
                const numMatch = text.match(/(?:Question|Q\\.?)\\s*(\\d+)/i) || (qEl.getAttribute('data-question-number') ? [null, qEl.getAttribute('data-question-number')] : null);
                const qNum = numMatch ? numMatch[1] : String(qIdx + 1);
                const qSelector = qEl.id ? `#${qEl.id}` : (qEl.getAttribute('data-testid') ? `[data-testid="${qEl.getAttribute('data-testid')}"]` : `.question:nth-of-type(${qIdx + 1})`);

                const optionEls = Array.from(qEl.querySelectorAll('input[type="radio"], input[type="checkbox"], .option, .choice'));
                const options = [];
                optionEls.forEach((optEl, optIdx) => {
                    const isInput = optEl.tagName.toLowerCase() === 'input';
                    const input = isInput ? optEl : optEl.querySelector('input');
                    const isRadio = input ? input.type === 'radio' : true;
                    let labelText = '';
                    if (input && input.id) {
                        const labelTag = document.querySelector(`label[for="${input.id}"]`);
                        if (labelTag) labelText = (labelTag.innerText || labelTag.textContent || '').trim();
                    }
                    if (!labelText) {
                        const parentLabel = optEl.closest('label') || optEl;
                        labelText = (parentLabel.innerText || parentLabel.textContent || '').trim();
                    }
                    const selector = input && input.id ? `#${input.id}` : (optEl.id ? `#${optEl.id}` : `${qSelector} input:nth-of-type(${optIdx + 1})`);
                    options.push({
                        selector: selector,
                        label: labelText,
                        value: input ? (input.value || null) : null,
                        is_radio: isRadio,
                        input_selector: selector,
                        is_checked: input ? Boolean(input.checked) : false
                    });
                });

                const hasCode = !!qEl.querySelector('.monaco-editor, .ace_editor, textarea.code-editor, [data-testid*="editor" i]');
                questions.push({
                    number: qNum,
                    text: text.slice(0, 500),
                    selector: qSelector,
                    question_type: hasCode ? 'coding' : (options.length > 0 ? 'mcq' : 'text'),
                    options: options
                });
            });

            // 4. Question palette
            const paletteEls = Array.from(document.querySelectorAll(
                '.question-palette .palette-item, .palette-item, .palette-btn, .q-btn, [data-testid*="palette-item" i], .question-grid button'
            ));
            const palette_items = paletteEls.map((pEl, pIdx) => {
                const text = (pEl.innerText || pEl.textContent || '').trim();
                const pSelector = pEl.id ? `#${pEl.id}` : (pEl.getAttribute('data-testid') ? `[data-testid="${pEl.getAttribute('data-testid')}"]` : `.palette-item:nth-child(${pIdx + 1})`);
                
                let state = 'unknown';
                const classList = pEl.classList;
                const dataStatus = (pEl.getAttribute('data-status') || '').toLowerCase();
                const ariaCurrent = pEl.getAttribute('aria-current');

                if (dataStatus === 'unanswered' || classList.contains('unanswered') || classList.contains('btn-danger')) {
                    state = 'unanswered';
                } else if (dataStatus === 'answered' || classList.contains('answered') || classList.contains('btn-success')) {
                    state = 'answered';
                } else if (dataStatus === 'marked' || classList.contains('marked') || classList.contains('review') || classList.contains('btn-warning') || classList.contains('btn-purple')) {
                    state = 'marked_for_review';
                } else if (ariaCurrent === 'true' || classList.contains('current') || classList.contains('active')) {
                    state = 'current';
                } else if (dataStatus === 'not_visited' || dataStatus === 'unvisited' || classList.contains('not-visited') || classList.contains('unvisited')) {
                    state = 'not_visited';
                }

                return {
                    number: text || String(pIdx + 1),
                    selector: pSelector,
                    state: state,
                    label: text
                };
            });

            // 5. Timer
            const timerEl = document.querySelector('#timer, .timer, [data-testid*="timer" i], .countdown, .time-left');
            let timer_selector = null;
            let timer_text = null;
            if (timerEl) {
                timer_selector = timerEl.id ? `#${timerEl.id}` : (timerEl.className ? `.${timerEl.className.split(' ')[0]}` : '[data-testid*="timer"]');
                timer_text = (timerEl.innerText || timerEl.textContent || '').trim();
            }

            // 6. Code editor
            const editorEl = document.querySelector('.monaco-editor, .ace_editor, .CodeMirror, textarea.code-editor, [data-testid*="editor" i]');
            let code_editor = null;
            if (editorEl) {
                const container_selector = editorEl.id ? `#${editorEl.id}` : (editorEl.className ? `.${editorEl.className.split(' ')[0]}` : '[data-testid*="editor"]');
                const inputEl = editorEl.querySelector('textarea, [contenteditable="true"]') || editorEl;
                const input_selector = inputEl.id ? `#${inputEl.id}` : `${container_selector} textarea`;
                const langEl = document.querySelector('select.language, select[name*="lang" i], [data-testid*="lang" i]');
                const lang_selector = langEl ? (langEl.id ? `#${langEl.id}` : 'select[name*="lang"]') : null;
                const allButtons = Array.from(document.querySelectorAll('button, input[type="button"]'));
                const runBtn = allButtons.find(b => {
                    const t = (b.innerText || b.value || '').toLowerCase();
                    return t.includes('run') || (b.getAttribute('data-testid') || '').toLowerCase().includes('run') || b.classList.contains('btn-run');
                });
                const run_selector = runBtn ? (runBtn.id ? `#${runBtn.id}` : (runBtn.getAttribute('data-testid') ? `[data-testid="${runBtn.getAttribute('data-testid')}"]` : 'button.btn-run')) : null;
                code_editor = {
                    container_selector,
                    input_selector,
                    language_selector: lang_selector,
                    run_button_selector: run_selector,
                    detected_language: langEl ? langEl.value : null
                };
            }

            // 7. Assessment Action Controls
            const action_controls = [];
            const buttonEls = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"], a.btn'));
            buttonEls.forEach(btn => {
                const text = (btn.innerText || btn.value || '').trim();
                const lower = text.toLowerCase();
                let action_type = null;
                let is_consequential = false;

                if (lower.includes('submit') || lower.includes('finish') || lower.includes('end exam') || lower.includes('end test')) {
                    action_type = 'submit';
                    is_consequential = true;
                } else if (lower.includes('save') || lower.includes('record')) {
                    action_type = 'save';
                } else if (lower.includes('next') || text === '>') {
                    action_type = 'next';
                } else if (lower.includes('prev') || lower.includes('back') || text === '<') {
                    action_type = 'previous';
                } else if (lower.includes('review') || lower.includes('mark')) {
                    action_type = 'mark_review';
                } else if (lower.includes('clear')) {
                    action_type = 'clear';
                } else if (lower.includes('start') || lower.includes('begin')) {
                    action_type = 'start';
                }

                if (action_type) {
                    const selector = btn.id ? `#${btn.id}` : (btn.getAttribute('data-testid') ? `[data-testid="${btn.getAttribute('data-testid')}"]` : (btn.className ? `.${btn.className.split(' ')[0]}` : 'button'));
                    action_controls.push({
                        action_type: action_type,
                        selector: selector,
                        label: text,
                        is_consequential: is_consequential
                    });
                }
            });

            // 8. Results / Scorecard
            const resultEl = document.querySelector('.result, .results, .score, .scorecard, [data-testid*="result" i], .result-summary');
            let results_summary = null;
            let results_selector = null;
            if (resultEl) {
                results_summary = (resultEl.innerText || resultEl.textContent || '').trim().slice(0, 500);
                results_selector = resultEl.id ? `#${resultEl.id}` : (resultEl.className ? `.${resultEl.className.split(' ')[0]}` : '[data-testid*="result"]');
            }

            return {
                instructions,
                instructionSelectors,
                sections,
                questions,
                palette_items,
                timer_selector,
                timer_text,
                code_editor,
                action_controls,
                results_summary,
                results_selector
            };
        }"""

    def _parse_assessment_eval_data(
        self,
        url: str,
        title: str | None,
        data: dict[str, Any],
    ) -> AssessmentMap:
        """Convert JavaScript evaluation results into an AssessmentMap dataclass."""
        sections = [
            AssessmentSection(
                title=s["title"],
                selector=s["selector"],
                id=s.get("id"),
                is_active=bool(s.get("is_active")),
            )
            for s in data.get("sections", [])
        ]

        questions: list[AssessmentQuestion] = []
        for q in data.get("questions", []):
            options = [
                AssessmentOption(
                    selector=opt["selector"],
                    label=opt.get("label", ""),
                    value=opt.get("value"),
                    is_radio=bool(opt.get("is_radio", True)),
                    input_selector=opt.get("input_selector"),
                    is_checked=opt.get("is_checked"),
                )
                for opt in q.get("options", [])
            ]
            questions.append(
                AssessmentQuestion(
                    selector=q["selector"],
                    number=q.get("number"),
                    text=q.get("text", ""),
                    question_type=q.get("question_type", "mcq"),
                    section=q.get("section"),
                    options=options,
                )
            )

        palette_items = [
            PaletteItem(
                number=p["number"],
                selector=p["selector"],
                state=PaletteState(p.get("state", "unknown")),
                label=p.get("label", ""),
            )
            for p in data.get("palette_items", [])
        ]

        editor_data = data.get("code_editor")
        code_editor = (
            CodeEditorInfo(
                container_selector=editor_data["container_selector"],
                input_selector=editor_data["input_selector"],
                language_selector=editor_data.get("language_selector"),
                run_button_selector=editor_data.get("run_button_selector"),
                detected_language=editor_data.get("detected_language"),
            )
            if editor_data
            else None
        )

        action_controls = [
            AssessmentActionControl(
                action_type=a["action_type"],
                selector=a["selector"],
                label=a.get("label", ""),
                is_consequential=bool(a.get("is_consequential", False)),
            )
            for a in data.get("action_controls", [])
        ]

        # Determine assessment confidence score
        score = 0.0
        if questions:
            score += 0.4
        if palette_items:
            score += 0.25
        if data.get("timer_selector"):
            score += 0.15
        if code_editor:
            score += 0.2
        if sections and action_controls:
            score += 0.2

        is_assessment = (
            bool(questions)
            or bool(palette_items)
            or bool(data.get("timer_selector"))
            or bool(code_editor)
            or (bool(sections) and bool(action_controls))
        )

        return AssessmentMap(
            url=url,
            is_assessment=is_assessment,
            title=title,
            instructions=data.get("instructions", []),
            instruction_selectors=data.get("instructionSelectors", []),
            sections=sections,
            questions=questions,
            palette_items=palette_items,
            timer_selector=data.get("timer_selector"),
            timer_text=data.get("timer_text"),
            code_editor=code_editor,
            action_controls=action_controls,
            results_summary=data.get("results_summary"),
            results_selector=data.get("results_selector"),
            confidence_score=min(1.0, score),
        )

    def _detect_assessment_from_dom_summary(
        self,
        url: str,
        dom_summary: dict[str, Any],
    ) -> AssessmentMap:
        """Heuristic detection of assessment components when page.evaluate() is unavailable."""
        title = dom_summary.get("title") or url
        buttons = dom_summary.get("buttons", [])
        inputs = dom_summary.get("inputs", [])
        headings = dom_summary.get("headings", [])
        text_preview = dom_summary.get("text_preview", "")

        questions: list[AssessmentQuestion] = []
        palette_items: list[PaletteItem] = []
        action_controls: list[AssessmentActionControl] = []
        sections: list[AssessmentSection] = []

        # 1. Action Controls from buttons
        for btn in buttons:
            label = (btn.get("text") or "").strip()
            lower = label.lower()
            btn_id = btn.get("id")
            selector = f"#{btn_id}" if btn_id else f'button:has-text("{label}")'

            if any(term in lower for term in ("submit", "finish", "end exam", "end test")):
                action_controls.append(AssessmentActionControl("submit", selector, label, is_consequential=True))
            elif any(term in lower for term in ("next", "forward", ">")):
                action_controls.append(AssessmentActionControl("next", selector, label))
            elif any(term in lower for term in ("prev", "back", "<")):
                action_controls.append(AssessmentActionControl("previous", selector, label))
            elif any(term in lower for term in ("save", "record")):
                action_controls.append(AssessmentActionControl("save", selector, label))
            elif any(term in lower for term in ("review", "mark")):
                action_controls.append(AssessmentActionControl("mark_review", selector, label))
            elif any(term in lower for term in ("clear", "reset")):
                action_controls.append(AssessmentActionControl("clear", selector, label))
            elif re.match(r"^(?:q\d+|\d+)$", lower):
                # Palette item button
                palette_items.append(PaletteItem(number=label, selector=selector, state=PaletteState.UNKNOWN, label=label))

        # 2. Questions from headings
        for h in headings:
            text = (h.get("text") or "").strip()
            match = re.search(r"(?:Question|Q\.?)\s*(\d+)", text, re.I)
            if match:
                questions.append(
                    AssessmentQuestion(
                        selector=f"h2:has-text('{text}')",
                        number=match.group(1),
                        text=text,
                    )
                )
            elif "section" in text.lower():
                sections.append(
                    AssessmentSection(title=text, selector=f"h3:has-text('{text}')")
                )

        # 3. Radio inputs as MCQ options
        radio_inputs = [i for i in inputs if i.get("type") == "radio"]
        if radio_inputs and questions:
            for r in radio_inputs:
                r_id = r.get("id")
                selector = f"#{r_id}" if r_id else "input[type='radio']"
                questions[0].options.append(
                    AssessmentOption(selector=selector, label=r.get("name") or "Option", is_radio=True)
                )

        # 4. Timer detection from text preview
        timer_text: str | None = None
        timer_selector: str | None = None
        timer_match = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", text_preview)
        if timer_match:
            timer_text = timer_match.group(1)
            timer_selector = ".timer"

        is_assessment = bool(questions or palette_items or timer_selector or (sections and action_controls))

        return AssessmentMap(
            url=url,
            is_assessment=is_assessment,
            title=title,
            sections=sections,
            questions=questions,
            palette_items=palette_items,
            timer_selector=timer_selector,
            timer_text=timer_text,
            action_controls=action_controls,
            confidence_score=0.8 if is_assessment else 0.0,
        )

    def _convert_assessment_to_elements(
        self,
        assessment_map: AssessmentMap,
        dom_summary: dict[str, Any],
    ) -> list[InteractiveElement]:
        """Convert assessment map structures into standard InteractiveElements for Journey."""
        elements: list[InteractiveElement] = []

        # 1. Timer element
        if assessment_map.timer_selector:
            elements.append(
                InteractiveElement(
                    element_type=ElementType.OTHER,
                    selector=assessment_map.timer_selector[:500],
                    label=f"Timer ({assessment_map.timer_text or 'active'})"[:300],
                )
            )

        # 2. Section navigation elements
        for sec in assessment_map.sections:
            elements.append(
                InteractiveElement(
                    element_type=ElementType.BUTTON,
                    selector=sec.selector[:500],
                    label=f"Section: {sec.title}"[:300],
                )
            )

        # 3. Questions and MCQ options
        for q in assessment_map.questions:
            elements.append(
                InteractiveElement(
                    element_type=ElementType.OTHER,
                    selector=q.selector[:500],
                    label=f"Question {q.number or ''}: {q.text[:100]}"[:300],
                )
            )
            for opt in q.options:
                elements.append(
                    InteractiveElement(
                        element_type=ElementType.RADIO if opt.is_radio else ElementType.CHECKBOX,
                        selector=opt.selector[:500],
                        label=opt.label[:300] if opt.label else f"Option {opt.value or ''}",
                        input_type="radio" if opt.is_radio else "checkbox",
                    )
                )

        # 4. Question palette buttons
        for pal in assessment_map.palette_items:
            elements.append(
                InteractiveElement(
                    element_type=ElementType.BUTTON,
                    selector=pal.selector[:500],
                    label=f"Palette Item {pal.number} [{pal.state.value}]"[:300],
                )
            )

        # 5. Code Editor
        if assessment_map.code_editor:
            elements.append(
                InteractiveElement(
                    element_type=ElementType.TEXTAREA,
                    selector=assessment_map.code_editor.input_selector[:500],
                    label="Coding Area Editor"[:300],
                )
            )
            if assessment_map.code_editor.run_button_selector:
                elements.append(
                    InteractiveElement(
                        element_type=ElementType.BUTTON,
                        selector=assessment_map.code_editor.run_button_selector[:500],
                        label="Run Code Button"[:300],
                    )
                )

        # 6. Action Controls (Next, Previous, Submit, etc.)
        for act in assessment_map.action_controls:
            elements.append(
                InteractiveElement(
                    element_type=ElementType.BUTTON,
                    selector=act.selector[:500],
                    label=f"{act.action_type.capitalize()} Control ({act.label})"[:300],
                )
            )

        # 7. Merge generic interactive elements as supplementary
        generic_elements = self._extract_interactive_elements(dom_summary)
        existing_selectors = {e.selector for e in elements}
        for g in generic_elements:
            if g.selector not in existing_selectors:
                elements.append(g)

        return elements

    # ---------- Generic Web Element Extraction ----------

    def _extract_interactive_elements(self, dom_summary: dict[str, Any]) -> list[InteractiveElement]:
        """Convert elements from BrowserDriver.get_dom_summary() into InteractiveElements."""
        elements: list[InteractiveElement] = []

        # 1. Links
        for link in dom_summary.get("links", []):
            href = link.get("href")
            text = (link.get("text") or "").strip()
            if href:
                safe_href = href.replace('"', '\\"')[:200]
                selector = f'a[href="{safe_href}"]'
            elif text:
                safe_text = text.replace('"', '\\"')[:50]
                selector = f'a:has-text("{safe_text}")'
            else:
                selector = "a"

            elements.append(
                InteractiveElement(
                    element_type=ElementType.LINK,
                    selector=selector[:500],
                    label=text[:300] if text else None,
                    href=href[:1000] if href else None,
                )
            )

        # 2. Buttons
        for button in dom_summary.get("buttons", []):
            btn_id = button.get("id")
            btn_name = button.get("name")
            text = (button.get("text") or "").strip()

            if btn_id:
                selector = f"#{btn_id}"
            elif btn_name:
                selector = f'button[name="{btn_name}"]'
            elif text:
                safe_text = text.replace('"', '\\"')[:50]
                selector = f'button:has-text("{safe_text}")'
            else:
                selector = "button"

            elements.append(
                InteractiveElement(
                    element_type=ElementType.BUTTON,
                    selector=selector[:500],
                    label=text[:300] if text else None,
                )
            )

        # 3. Inputs & textareas
        for inp in dom_summary.get("inputs", []):
            tag = inp.get("tag", "input").lower()
            inp_id = inp.get("id")
            inp_name = inp.get("name")
            inp_type = inp.get("type", "text")

            if inp_id:
                selector = f"#{inp_id}"
            elif inp_name:
                selector = f'{tag}[name="{inp_name}"]'
            else:
                selector = f"{tag}[type='{inp_type}']" if inp_type else tag

            if tag == "textarea":
                elem_type = ElementType.TEXTAREA
            elif tag == "select":
                elem_type = ElementType.SELECT
            elif inp_type == "checkbox":
                elem_type = ElementType.CHECKBOX
            elif inp_type == "radio":
                elem_type = ElementType.RADIO
            else:
                elem_type = ElementType.INPUT

            elements.append(
                InteractiveElement(
                    element_type=elem_type,
                    selector=selector[:500],
                    label=inp.get("placeholder") or inp_name or inp_id,
                    input_type=inp_type,
                )
            )

        return elements

    # ---------- Journey Construction ----------

    def _build_journeys(
        self,
        run_id: str,
        start_url: str,
        discovered_pages: list[DiscoveredPage],
        max_tests: int,
        assessment_map: AssessmentMap | None = None,
    ) -> list[Journey]:
        """Construct validated Journey instances from discovered pages."""
        journeys: list[Journey] = []
        root_title = discovered_pages[0].title or "Home"

        if assessment_map and assessment_map.is_assessment:
            # Assessment-specific Journey
            desc = (
                f"Assessment journey with {len(assessment_map.questions)} question(s), "
                f"{len(assessment_map.sections)} section(s), "
                f"{len(assessment_map.palette_items)} palette item(s) on {start_url}."
            )
            primary_journey = Journey(
                run_id=run_id,
                name=f"Assessment Flow: {assessment_map.title or root_title}"[:200],
                description=desc[:1000],
                priority=1,
                start_url=start_url[:1000],
                pages=discovered_pages,
                generated_by=GenerationMode.RULE_BASED,
            )
            journeys.append(primary_journey)
        else:
            # Generic site Primary Journey
            primary_journey = Journey(
                run_id=run_id,
                name=f"Explore {root_title} and navigation flow"[:200],
                description=(
                    f"Rule-based crawl traversing {len(discovered_pages)} reachable page(s) "
                    f"starting from {start_url}."
                ),
                priority=1,
                start_url=start_url[:1000],
                pages=discovered_pages,
                generated_by=GenerationMode.RULE_BASED,
            )
            journeys.append(primary_journey)

        # Focused journeys for interactive/form pages
        for page in discovered_pages:
            interactive_inputs = [
                e for e in page.elements
                if e.element_type in (
                    ElementType.INPUT,
                    ElementType.TEXTAREA,
                    ElementType.BUTTON,
                    ElementType.SELECT,
                    ElementType.RADIO,
                    ElementType.CHECKBOX,
                )
            ]
            if interactive_inputs and page.url != start_url:
                page_title = page.title or page.url
                journey = Journey(
                    run_id=run_id,
                    name=f"User interaction flow: {page_title}"[:200],
                    description=f"Interact with fields on {page.url} ({len(interactive_inputs)} controls).",
                    priority=2,
                    start_url=page.url[:1000],
                    pages=[page],
                    generated_by=GenerationMode.RULE_BASED,
                )
                journeys.append(journey)
                if len(journeys) >= max_tests:
                    break

        return journeys
