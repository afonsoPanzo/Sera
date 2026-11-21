"""Domain models for CampusBridge (SDD §5, §6)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Provenance (SDD §5.1 Data Confidence Model, §6.4) ----------

class Verification(str, Enum):
    CONFIRMED = "confirmed"
    EXTRACTED = "extracted_pending_confirmation"
    INFERRED = "inferred"
    MISSING = "missing"
    EXPIRED = "expired"
    REJECTED = "rejected"


class SourceReference(BaseModel):
    title: str
    url: Optional[str] = None
    retrieved_at: Optional[date] = None
    official: bool = False
    note: Optional[str] = None


class Fact(BaseModel):
    """A single piece of information with its origin and verification state."""
    value: Any = None
    status: Verification = Verification.MISSING
    source: str = "unknown"          # e.g. "user", "document:doc-passport", "system"
    confidence: Optional[float] = None
    updated_at: datetime = Field(default_factory=now)
    updated_by: str = "system"


# ---------- Student / Digital Twin ----------

class Student(BaseModel):
    id: str
    name: str
    nationality: Optional[str] = None
    university: Optional[str] = None
    program: Optional[str] = None
    academic_year: Optional[str] = None
    preferred_language: str = "en"


# ---------- Documents ----------

class DocumentType(str, Enum):
    PASSPORT = "passport"
    ENROLLMENT_CERTIFICATE = "enrollment_certificate"
    ACCOMMODATION = "accommodation_document"
    RESIDENCE_PERMIT = "residence_permit"
    OFFICIAL_LETTER = "official_letter"
    OTHER = "other"


class Document(BaseModel):
    id: str
    student_id: str
    type: DocumentType
    title: str
    original_filename: Optional[str] = None
    storage_key: Optional[str] = None       # private path, never a public URL
    extracted_text: Optional[str] = None
    extraction_error: Optional[str] = None  # extraction failures are visible (SDD §5.2)
    fields: dict[str, Fact] = Field(default_factory=dict)
    uploaded_at: datetime = Field(default_factory=now)

    def expiry(self) -> Fact:
        return self.fields.get("expiry_date", Fact())


# ---------- Missions ----------

class MissionStatus(str, Enum):
    CREATED = "CREATED"
    ANALYSIS = "ANALYSIS"
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    WAITING_FOR_INSTITUTION = "WAITING_FOR_INSTITUTION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
    EXPIRED = "EXPIRED"


# Allowed transitions (SDD Figure 5). Terminal states have none.
MISSION_TRANSITIONS: dict[MissionStatus, set[MissionStatus]] = {
    MissionStatus.CREATED: {MissionStatus.ANALYSIS, MissionStatus.CANCELLED},
    MissionStatus.ANALYSIS: {MissionStatus.PLANNED, MissionStatus.BLOCKED, MissionStatus.CANCELLED},
    MissionStatus.PLANNED: {MissionStatus.IN_PROGRESS, MissionStatus.BLOCKED, MissionStatus.CANCELLED},
    MissionStatus.IN_PROGRESS: {MissionStatus.WAITING_FOR_USER, MissionStatus.WAITING_FOR_INSTITUTION,
                                MissionStatus.COMPLETED, MissionStatus.BLOCKED, MissionStatus.CANCELLED,
                                MissionStatus.EXPIRED},
    MissionStatus.WAITING_FOR_USER: {MissionStatus.IN_PROGRESS, MissionStatus.CANCELLED, MissionStatus.EXPIRED},
    MissionStatus.WAITING_FOR_INSTITUTION: {MissionStatus.IN_PROGRESS, MissionStatus.CANCELLED,
                                            MissionStatus.EXPIRED},
    MissionStatus.BLOCKED: {MissionStatus.ANALYSIS, MissionStatus.IN_PROGRESS, MissionStatus.CANCELLED},
    MissionStatus.COMPLETED: set(),
    MissionStatus.CANCELLED: set(),
    MissionStatus.EXPIRED: set(),
}


class Requirement(BaseModel):
    id: str
    description: str
    document_type: DocumentType
    # The document must stay valid this many days after the mission deadline.
    min_validity_days_after_deadline: int = 0
    satisfied_by: Optional[str] = None      # document id
    source: SourceReference
    verified: bool = False                  # is the requirement itself confirmed by an official source?


class MissionTask(BaseModel):
    id: str
    title: str
    done: bool = False


class Mission(BaseModel):
    id: str
    student_id: str
    title: str
    description: str = ""
    institution: str = ""
    status: MissionStatus = MissionStatus.CREATED
    deadline: Optional[date] = None
    depends_on: list[str] = Field(default_factory=list)   # mission ids
    requirements: list[Requirement] = Field(default_factory=list)
    tasks: list[MissionTask] = Field(default_factory=list)
    completion_criteria: str = ""


# ---------- Impact (SDD §5.4) ----------

class ImpactLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


IMPACT_ORDER = [ImpactLevel.LOW, ImpactLevel.UNKNOWN, ImpactLevel.MEDIUM, ImpactLevel.HIGH, ImpactLevel.CRITICAL]


class Evidence(BaseModel):
    kind: str             # "fact" | "requirement" | "mission" | "dependency"
    description: str
    status: Optional[str] = None
    source: Optional[str] = None


class ImpactItem(BaseModel):
    level: ImpactLevel
    mission_id: str
    mission_title: str
    requirement_id: Optional[str] = None
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class ImpactReport(BaseModel):
    student_id: str
    event: dict
    as_of: date
    overall_level: ImpactLevel
    items: list[ImpactItem]
    disclaimer: str = ("This is a system assessment based on the information available, "
                       "not an official legal or institutional decision. Confirm with the official source.")


# ---------- Approvals (SDD §5.5, FR-11) ----------

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    SIMULATED = "simulated"   # demo adapter: nothing was actually sent
    FAILED = "failed"


class ApprovalRequest(BaseModel):
    id: str
    student_id: str
    mission_id: Optional[str] = None
    action_type: str                       # e.g. "send_email"
    summary: str                           # what will happen, in plain words
    payload: dict = Field(default_factory=dict)   # exactly what will be transmitted
    status: ApprovalStatus = ApprovalStatus.PENDING
    result: Optional[str] = None
    created_at: datetime = Field(default_factory=now)
    decided_at: Optional[datetime] = None
