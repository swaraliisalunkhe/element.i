"""What the Explorer discovers: pages, interactive elements, and journeys (user flows)."""

from datetime import datetime

from pydantic import Field

from app.core.constants import ElementType, GenerationMode
from app.schemas.common import ContractModel, new_id, utc_now


class InteractiveElement(ContractModel):
    element_type: ElementType
    selector: str = Field(min_length=1, max_length=500, description="CSS selector Playwright can use.")
    label: str | None = Field(default=None, max_length=300)
    href: str | None = Field(default=None, max_length=1000)
    input_type: str | None = Field(default=None, max_length=50, description="e.g. text, email, password")
    required: bool = False


class DiscoveredPage(ContractModel):
    url: str = Field(min_length=1, max_length=1000)
    title: str | None = Field(default=None, max_length=300)
    depth: int = Field(default=0, ge=0, description="Clicks away from the start page.")
    elements: list[InteractiveElement] = Field(default_factory=list)


class Journey(ContractModel):
    """A user flow such as 'Log in' or 'Add item to cart'."""

    id: str = Field(default_factory=lambda: new_id("jny"), min_length=1, max_length=64)
    run_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: int = Field(default=3, ge=1, le=5, description="1 = most important")
    start_url: str = Field(min_length=1, max_length=1000)
    pages: list[DiscoveredPage] = Field(min_length=1)
    generated_by: GenerationMode = GenerationMode.MOCK
    created_at: datetime = Field(default_factory=utc_now)