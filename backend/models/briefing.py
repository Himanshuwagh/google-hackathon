from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class TalkingPoint(BaseModel):
    point: str
    citation: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    source_label: Optional[str] = None
    source_url: Optional[str] = None


class Briefing(BaseModel):
    briefing_id: str
    generated_at: Optional[datetime | str] = None
    compliance_loops: Optional[int] = None
    compliance_status: Optional[str] = None
    talking_points: list[Any] = []
    anticipated_objection: Optional[Any] = None
    supporting_evidence: list[dict[str, Any]] = []
    actions_taken: Optional[dict[str, Any]] = None

