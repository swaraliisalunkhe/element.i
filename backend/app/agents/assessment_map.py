"""AssessmentMap data structures representing online exam and testing elements.

Owner: Member C.
Stores structured domain information discovered by ExplorerAgent:
sections, questions, MCQ options, question palette, timer, code editor,
navigation controls, submission controls, and results summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.journey import Journey


class PaletteState(StrEnum):
    """Observable states of question buttons in an exam palette."""

    ANSWERED = "answered"
    UNANSWERED = "unanswered"
    CURRENT = "current"
    MARKED_FOR_REVIEW = "marked_for_review"
    NOT_VISITED = "not_visited"
    UNKNOWN = "unknown"


@dataclass
class AssessmentOption:
    """An option for a multiple-choice question."""

    selector: str
    label: str = ""
    value: str | None = None
    is_radio: bool = True
    input_selector: str | None = None
    is_checked: bool | None = None


@dataclass
class AssessmentQuestion:
    """A single exam question."""

    selector: str
    number: str | None = None
    text: str = ""
    question_type: str = "mcq"  # "mcq", "coding", "text", "unknown"
    section: str | None = None
    options: list[AssessmentOption] = field(default_factory=list)


@dataclass
class PaletteItem:
    """A single question item in the question palette grid."""

    number: str
    selector: str
    state: PaletteState = PaletteState.UNKNOWN
    label: str = ""


@dataclass
class CodeEditorInfo:
    """Discovered coding challenge editor controls."""

    container_selector: str
    input_selector: str
    language_selector: str | None = None
    run_button_selector: str | None = None
    detected_language: str | None = None


@dataclass
class AssessmentActionControl:
    """Buttons/controls for navigating or submitting the assessment."""

    action_type: str  # "next", "previous", "save", "mark_review", "clear", "submit", "finish", "start"
    selector: str
    label: str = ""
    is_consequential: bool = False  # True for submit/finish to prevent accidental execution


@dataclass
class AssessmentSection:
    """Exam section or subject tab."""

    title: str
    selector: str
    id: str | None = None
    is_active: bool = False


@dataclass
class AssessmentMap:
    """Comprehensive map of an online assessment's interactive UI."""

    url: str
    is_assessment: bool = False
    title: str | None = None
    instructions: list[str] = field(default_factory=list)
    instruction_selectors: list[str] = field(default_factory=list)
    sections: list[AssessmentSection] = field(default_factory=list)
    questions: list[AssessmentQuestion] = field(default_factory=list)
    palette_items: list[PaletteItem] = field(default_factory=list)
    timer_selector: str | None = None
    timer_text: str | None = None
    code_editor: CodeEditorInfo | None = None
    action_controls: list[AssessmentActionControl] = field(default_factory=list)
    results_summary: str | None = None
    results_selector: str | None = None
    confidence_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert AssessmentMap to a serializable dictionary."""
        return {
            "url": self.url,
            "is_assessment": self.is_assessment,
            "title": self.title,
            "instructions": list(self.instructions),
            "instruction_selectors": list(self.instruction_selectors),
            "sections": [
                {
                    "title": s.title,
                    "selector": s.selector,
                    "id": s.id,
                    "is_active": s.is_active,
                }
                for s in self.sections
            ],
            "questions": [
                {
                    "number": q.number,
                    "text": q.text,
                    "selector": q.selector,
                    "question_type": q.question_type,
                    "section": q.section,
                    "options": [
                        {
                            "selector": o.selector,
                            "label": o.label,
                            "value": o.value,
                            "is_radio": o.is_radio,
                            "input_selector": o.input_selector,
                            "is_checked": o.is_checked,
                        }
                        for o in q.options
                    ],
                }
                for q in self.questions
            ],
            "palette_items": [
                {
                    "number": p.number,
                    "selector": p.selector,
                    "state": p.state.value,
                    "label": p.label,
                }
                for p in self.palette_items
            ],
            "timer_selector": self.timer_selector,
            "timer_text": self.timer_text,
            "code_editor": (
                {
                    "container_selector": self.code_editor.container_selector,
                    "input_selector": self.code_editor.input_selector,
                    "language_selector": self.code_editor.language_selector,
                    "run_button_selector": self.code_editor.run_button_selector,
                    "detected_language": self.code_editor.detected_language,
                }
                if self.code_editor
                else None
            ),
            "action_controls": [
                {
                    "action_type": a.action_type,
                    "selector": a.selector,
                    "label": a.label,
                    "is_consequential": a.is_consequential,
                }
                for a in self.action_controls
            ],
            "results_summary": self.results_summary,
            "results_selector": self.results_selector,
            "confidence_score": self.confidence_score,
        }

    @classmethod
    def from_journeys(cls, journeys: list[Journey]) -> AssessmentMap | None:
        """Reconstruct an AssessmentMap from discovered Journeys."""
        if not journeys:
            return None

        primary_journey = journeys[0]
        journey_name = getattr(primary_journey, "name", "") or ""
        start_url = getattr(primary_journey, "start_url", "") or ""

        elements: list[Any] = []
        for j in journeys:
            for p in getattr(j, "pages", []):
                for e in getattr(p, "elements", []):
                    elements.append(e)

        if not elements and "assessment" not in journey_name.lower():
            return None

        questions: list[AssessmentQuestion] = []
        palette_items: list[PaletteItem] = []
        action_controls: list[AssessmentActionControl] = []
        sections: list[AssessmentSection] = []
        timer_selector: str | None = None
        timer_text: str | None = None
        code_editor: CodeEditorInfo | None = None

        current_options: list[AssessmentOption] = []

        for elem in elements:
            sel = getattr(elem, "selector", "")
            lbl = getattr(elem, "label", "") or ""
            etype = getattr(elem, "element_type", None)
            etype_val = getattr(etype, "value", str(etype)).lower() if etype else ""

            # Timer
            if "timer" in sel.lower() or "timer" in lbl.lower():
                if not timer_selector:
                    timer_selector = sel
                    match = re.search(r"Timer\s*\(([^)]+)\)", lbl)
                    if match:
                        timer_text = match.group(1)

            # Palette
            elif "palette item" in lbl.lower() or re.match(r"^#pal-\d+", sel):
                num_match = re.search(r"Palette Item (\w+)", lbl)
                p_num = num_match.group(1) if num_match else str(len(palette_items) + 1)
                state = PaletteState.UNKNOWN
                for ps in PaletteState:
                    if ps.value in lbl.lower():
                        state = ps
                        break
                palette_items.append(PaletteItem(number=p_num, selector=sel, state=state, label=lbl))

            # Code Editor
            elif "coding area" in lbl.lower() or "code editor" in lbl.lower() or etype_val == "textarea":
                if not code_editor:
                    code_editor = CodeEditorInfo(
                        container_selector=".code-editor, .editor-container",
                        input_selector=sel,
                    )

            # Action Controls
            elif any(act in lbl.lower() for act in ("control (", "next", "previous", "submit", "finish", "save", "mark")):
                lower_lbl = lbl.lower()
                is_conseq = any(w in lower_lbl for w in ("submit", "finish", "end exam", "end test"))
                act_type = "submit" if is_conseq else "next"
                if "prev" in lower_lbl:
                    act_type = "previous"
                elif "save" in lower_lbl:
                    act_type = "save"
                elif "mark" in lower_lbl:
                    act_type = "mark_review"

                action_controls.append(
                    AssessmentActionControl(
                        action_type=act_type,
                        selector=sel,
                        label=lbl,
                        is_consequential=is_conseq,
                    )
                )

            # MCQ Radio / Checkbox options
            elif etype_val in ("radio", "checkbox") or getattr(elem, "input_type", "") in ("radio", "checkbox"):
                is_radio = etype_val == "radio" or getattr(elem, "input_type", "") == "radio"
                current_options.append(
                    AssessmentOption(
                        selector=sel,
                        label=lbl,
                        is_radio=is_radio,
                    )
                )

            # Section tabs
            elif "section:" in lbl.lower():
                sec_title = lbl.split("Section:", 1)[-1].strip()
                sections.append(AssessmentSection(title=sec_title, selector=sel))

        # Group options into question
        if current_options:
            questions.append(
                AssessmentQuestion(
                    selector=".question, #question-1, [data-testid*='question']",
                    number="1",
                    text="Assessment Question 1",
                    options=current_options,
                )
            )

        is_assessment = bool(
            questions
            or palette_items
            or timer_selector
            or code_editor
            or "assessment" in journey_name.lower()
        )
        if not is_assessment:
            return None

        return cls(
            url=start_url,
            is_assessment=True,
            title=journey_name,
            questions=questions,
            palette_items=palette_items,
            timer_selector=timer_selector,
            timer_text=timer_text,
            code_editor=code_editor,
            action_controls=action_controls,
            sections=sections,
            confidence_score=0.9 if is_assessment else 0.0,
        )

