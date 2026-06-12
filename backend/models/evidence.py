from __future__ import annotations
from typing import Literal, Optional

from pydantic import BaseModel


SourceType = Literal["project", "experience", "summary", "skills", "education", "jd"]
EvidenceStrength = Literal["high", "medium", "low"]


class EvidenceRef(BaseModel):
    evidence_id: str
    source_type: SourceType
    source_label: str


class EvidenceSnippet(EvidenceRef):
    snippet: str
    evidence_strength: EvidenceStrength
    retrieval_score: Optional[float] = None
