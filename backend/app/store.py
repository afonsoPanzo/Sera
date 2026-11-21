"""In-memory repository + fictional demo data (SDD §11.1).

Relational-style storage (dicts keyed by id). Swap for PostgreSQL later without
changing the rest of the app: everything goes through this class.
"""

from __future__ import annotations

import uuid
from datetime import date

from .models import (
    ApprovalRequest, Document, DocumentType, Fact, Mission, MissionStatus, MissionTask,
    Requirement, SourceReference, Student, Verification,
)

DEMO_STUDENT_ID = "stu-demo"

# Fictional rules for the demo. They are NOT real immigration rules.
DEMO_KB = SourceReference(
    title="CampusBridge demo knowledge base (fictional rules)",
    official=False,
    note="Replace with the official immigration office / university source before real use.",
)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class Store:
    def __init__(self) -> None:
        self.students: dict[str, Student] = {}
        self.documents: dict[str, Document] = {}
        self.missions: dict[str, Mission] = {}
        self.approvals: dict[str, ApprovalRequest] = {}

    # ----- queries -----
    def student_documents(self, student_id: str) -> list[Document]:
        return [d for d in self.documents.values() if d.student_id == student_id]

    def student_missions(self, student_id: str) -> list[Mission]:
        return [m for m in self.missions.values() if m.student_id == student_id]

    def dependents_of(self, mission_id: str) -> list[Mission]:
        return [m for m in self.missions.values() if mission_id in m.depends_on]

    # ----- demo seed -----
    def seed_demo(self) -> None:
        sid = DEMO_STUDENT_ID
        self.students[sid] = Student(
            id=sid, name="Amara Demo", nationality="Nigerian (fictional)",
            university="University of Debrecen", program="BSc Computer Science",
            academic_year="2026/2027", preferred_language="en",
        )

        def confirmed(value, doc_id):
            return Fact(value=value, status=Verification.CONFIRMED, source=f"document:{doc_id}", updated_by="user")

        self.documents["doc-passport"] = Document(
            id="doc-passport", student_id=sid, type=DocumentType.PASSPORT, title="Passport",
            fields={
                "holder": confirmed("Amara Demo", "doc-passport"),
                "expiry_date": confirmed(date(2027, 3, 10), "doc-passport"),
                "issuing_authority": confirmed("Fictional Passport Office", "doc-passport"),
            },
        )
        self.documents["doc-enrollment"] = Document(
            id="doc-enrollment", student_id=sid, type=DocumentType.ENROLLMENT_CERTIFICATE,
            title="Enrollment certificate 2026/27",
            fields={"expiry_date": confirmed(date(2027, 8, 31), "doc-enrollment")},
        )
        self.documents["doc-housing"] = Document(
            id="doc-housing", student_id=sid, type=DocumentType.ACCOMMODATION,
            title="Dormitory contract",
            fields={
                "address": confirmed("4032 Debrecen, Demo utca 1.", "doc-housing"),
                # extracted by the system but not yet confirmed by the student
                "expiry_date": Fact(value=date(2027, 1, 31), status=Verification.EXTRACTED,
                                    source="document:doc-housing", confidence=0.8),
            },
        )

        self.missions["mis-permit"] = Mission(
            id="mis-permit", student_id=sid, title="Renew residence permit",
            description="Submit the residence permit renewal before the current permit expires.",
            institution="Immigration office (OIF)", status=MissionStatus.IN_PROGRESS,
            deadline=date(2027, 1, 20),
            requirements=[
                Requirement(id="req-permit-passport", description="Valid passport (demo rule: 180 days after deadline)",
                            document_type=DocumentType.PASSPORT, min_validity_days_after_deadline=180,
                            satisfied_by="doc-passport", source=DEMO_KB, verified=True),
                Requirement(id="req-permit-housing", description="Accommodation document valid at submission",
                            document_type=DocumentType.ACCOMMODATION, satisfied_by="doc-housing",
                            source=DEMO_KB, verified=True),
                Requirement(id="req-permit-enroll", description="Current enrollment certificate",
                            document_type=DocumentType.ENROLLMENT_CERTIFICATE, satisfied_by="doc-enrollment",
                            source=DEMO_KB, verified=True),
            ],
            tasks=[
                MissionTask(id="t1", title="Collect required documents"),
                MissionTask(id="t2", title="Book appointment on Enter Hungary portal"),
                MissionTask(id="t3", title="Submit application"),
            ],
            completion_criteria="Immigration office confirms the application was received.",
        )
        self.missions["mis-registration"] = Mission(
            id="mis-registration", student_id=sid, title="Spring semester registration",
            institution="University of Debrecen", status=MissionStatus.PLANNED,
            deadline=date(2027, 2, 5),
            requirements=[
                Requirement(id="req-reg-enroll", description="Enrollment certificate",
                            document_type=DocumentType.ENROLLMENT_CERTIFICATE, satisfied_by="doc-enrollment",
                            source=DEMO_KB, verified=True),
                Requirement(id="req-reg-housing", description="Proof of address (unconfirmed demo rule)",
                            document_type=DocumentType.ACCOMMODATION, satisfied_by="doc-housing",
                            source=DEMO_KB, verified=False),
            ],
            completion_criteria="Registration visible in Neptun.",
        )
        self.missions["mis-addresscard"] = Mission(
            id="mis-addresscard", student_id=sid, title="Update address card (lakcímkártya)",
            institution="Government office (Kormányablak)", status=MissionStatus.CREATED,
            deadline=date(2027, 3, 1), depends_on=["mis-permit"],
            completion_criteria="New address card received.",
        )


store = Store()
store.seed_demo()
