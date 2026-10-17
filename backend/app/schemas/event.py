"""Live events sent to the dashboard over SSE (Server-Sent Events)."""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.constants import AgentName, EventLevel, EventType
from app.schemas.common import ContractModel, new_id, utc_now


class AgentEvent(ContractModel):
    """One thing that happened during a run.

    seq: 0, 1, 2, ... counted per run. The SSE 'id:' line uses it so a client can resume.
    type: the SSE 'event:' name.
    data: free-form extra details (for example {"bug_id": "...", "severity": "high"}).
    """

    id: str = Field(default_factory=lambda: new_id("evt"), min_length=1, max_length=64)
    run_id: str = Field(min_length=1, max_length=64)
    seq: int = Field(default=0, ge=0)
    type: EventType
    agent: AgentName
    level: EventLevel = EventLevel.INFO
    message: str = Field(min_length=1, max_length=1000)
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)