from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TaskPlan(BaseModel):
    """Normalized user request used by planning and site selection."""

    task_type: Literal["search", "compare", "extract", "book", "navigate", "unknown"] = "unknown"
    subject: str
    preferred_sites: List[str] = Field(default_factory=list)
    candidate_sites: List[str] = Field(default_factory=list)
    country: Optional[str] = None
    currency: Optional[str] = None
    constraints: Dict[str, str] = Field(default_factory=dict)
    clarification_question: Optional[str] = None
    clarification_options: List[str] = Field(default_factory=list)

    @property
    def needs_clarification(self) -> bool:
        return bool(self.clarification_question)


# Status labels, compared lowercased, meaning an offer cannot be bought now.
UNAVAILABLE_STATUSES = (
    "coming soon",
    "currently unavailable",
    "temporarily unavailable",
    "out of stock",
    "sold out",
)


class ProductOffer(BaseModel):
    """Normalized offer returned by a site adapter."""

    site: str
    title: str
    product_url: str
    price: Optional[float] = None
    currency: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    # The site's own status label when it shows one, e.g. "Coming Soon";
    # None when the card states nothing.
    availability: Optional[str] = None
    condition: Optional[str] = None
    source_timestamp: str

    @property
    def is_available(self) -> bool:
        return (self.availability or "").strip().lower() not in UNAVAILABLE_STATUSES


class SiteRunResult(BaseModel):
    """Result of one approved site worker in a multi-site task."""

    site: str
    status: Literal["completed", "blocked", "failed"]
    offers: List[ProductOffer] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ClarificationRequest(BaseModel):
    question: str
    options: List[str] = Field(default_factory=list)
    field: str
