from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class NewMeetingRequest(BaseModel):
    rep_id: str
    hcp_id: str
    drug_id: str
    meeting_date: datetime
    location: str
    duration_mins: int = 20


class NewMeetingResponse(BaseModel):
    meeting_id: str
    status: str
    message: str


class MeetingListItem(BaseModel):
    meeting_id: str
    hcp_name: str
    hcp_specialty: str
    hospital: str
    drug_name: str
    meeting_date: datetime
    meeting_date_key: str
    meeting_time_display: str
    duration_mins: int
    status: str
    briefing_id: Optional[str] = None
    error_message: Optional[str] = None


class MeetingDetailResponse(BaseModel):
    meeting_id: str
    status: str
    hcp: dict[str, Any]
    drug: dict[str, Any]
    meeting_date: datetime
    meeting_date_key: str
    meeting_time_display: str
    duration_mins: int
    location: Optional[str] = None
    briefing: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: bool = True
    code: str
    message: str


class MeetingDocument(BaseModel):
    id: str = Field(alias="_id")
    rep_id: str
    hcp_id: str
    drug_id: Optional[str] = None
    drug_ids: Optional[list[str]] = None
    meeting_date: datetime
    location: Optional[str] = None
    duration_mins: int = 20
    status: str
    briefing_id: Optional[str] = None
