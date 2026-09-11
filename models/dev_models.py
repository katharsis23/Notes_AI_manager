from typing import Literal

from pydantic import BaseModel, Field

IssueSeverity = Literal[
    "critical",
    "major",
    "minor",
]

IssueType = Literal[
    "factual_error",
    "contextual_error",
    "user_request",
    "grammar",
    "terminology",
    "structure",
    "missing_content",
    "wikilink",
    "markdown",
    "diagram",
    "asr_hallucination",
]


class QualityIssue(BaseModel):
    severity: IssueSeverity
    type: IssueType
    description: str
    section: str | None = None


class QualityJudgement(BaseModel):
    valid: bool
    score: float = Field(ge=0.0, le=10.0)
    issues: list[QualityIssue] = Field(default_factory=list)
    recommendation: str
