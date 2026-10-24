"""Database tables (SQLAlchemy models). Owner: Member A.

Callers outside app/db should not use these classes. Use Repository (repository.py),
which returns the Pydantic contract objects instead.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db.types import UTCDateTime


class Base(DeclarativeBase):
    pass


# Links bugs to screenshots (many-to-many).
bug_evidence_table = Table(
    "bug_evidence",
    Base.metadata,
    Column("bug_id", String(64), ForeignKey("bug_reports.id", ondelete="CASCADE"), primary_key=True),
    Column("evidence_id", String(64), ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True),
)


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_url: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), index=True)
    agent_mode: Mapped[str] = mapped_column(String(10))
    mode: Mapped[str] = mapped_column(
        String(20), default="generic", server_default="generic"
    )
    max_pages: Mapped[int] = mapped_column(Integer)
    max_depth: Mapped[int] = mapped_column(Integer)
    max_tests: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class JourneyRow(Base):
    __tablename__ = "journeys"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer)
    start_url: Mapped[str] = mapped_column(String(1000))
    pages: Mapped[list[Any]] = mapped_column(JSON)
    generated_by: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class TestCaseRow(Base):
    __test__ = False  # not a pytest test class
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    journey_id: Mapped[str | None] = mapped_column(
        ForeignKey("journeys.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer)
    steps: Mapped[list[Any]] = mapped_column(JSON)
    expected_result: Mapped[str] = mapped_column(Text)
    generated_by: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    suite_id: Mapped[str | None] = mapped_column(
        ForeignKey("test_suites.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    scenario: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )

    covers: Mapped[list[Any] | None] = mapped_column(
        JSON, nullable=True
    )


class TestResultRow(Base):
    __test__ = False  # not a pytest test class
    __tablename__ = "test_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    # unique=True: a test case can have only one result.
    test_case_id: Mapped[str] = mapped_column(
        ForeignKey("test_cases.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_by: Mapped[str] = mapped_column(String(20))

    step_results: Mapped[list["StepResultRow"]] = relationship(
        cascade="all, delete-orphan", order_by="StepResultRow.step_index"
    )
    evidence: Mapped[list["EvidenceRow"]] = relationship(order_by="EvidenceRow.created_at")


class StepResultRow(Base):
    __tablename__ = "step_results"
    __table_args__ = (UniqueConstraint("test_result_id", "step_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_result_id: Mapped[str] = mapped_column(
        ForeignKey("test_results.id", ondelete="CASCADE"), index=True
    )
    step_index: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    duration_ms: Mapped[int] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Plain text on purpose (no foreign key): the evidence row is saved after the step rows.
    evidence_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observed: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )


class EvidenceRow(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    test_case_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_result_id: Mapped[str | None] = mapped_column(
        ForeignKey("test_results.id", ondelete="SET NULL"), nullable=True, index=True
    )
    step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    path: Mapped[str] = mapped_column(String(300))
    mime_type: Mapped[str] = mapped_column(String(100))
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caption: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class BugRow(Base):
    __tablename__ = "bug_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    test_case_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    journey_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    steps_to_reproduce: Mapped[list[Any]] = mapped_column(JSON)
    expected_behavior: Mapped[str] = mapped_column(Text)
    actual_behavior: Mapped[str] = mapped_column(Text)
    page_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    generated_by: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    assessment_context: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )

    reproducibility: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    evidence: Mapped[list["EvidenceRow"]] = relationship(
        secondary=bug_evidence_table, order_by="EvidenceRow.created_at"
    )


class AgentEventRow(Base):
    __tablename__ = "agent_events"
    __table_args__ = (UniqueConstraint("run_id", "seq"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(40))
    agent: Mapped[str] = mapped_column(String(20))
    level: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(String(1000))
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime)

class AssessmentMapRow(Base):
    __tablename__ = "assessment_maps"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        primary_key=True,
    )

    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class TestSuiteRow(Base):
    __tablename__ = "test_suites"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    
