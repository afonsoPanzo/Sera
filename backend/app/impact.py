"""Predictive Impact Engine — deterministic, rule-based (SDD §5.4, principle 6).

No LLM here: the engine only uses stored facts, requirements and mission
dependencies, so it is testable and every conclusion carries its evidence.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from .models import (
    IMPACT_ORDER, Document, DocumentType, Evidence, Fact, ImpactItem, ImpactLevel,
    ImpactReport, Mission, MissionStatus, Requirement, Verification,
)
from .store import Store

SAFETY_MARGIN_DAYS = 30
CLOSED = {MissionStatus.COMPLETED, MissionStatus.CANCELLED, MissionStatus.EXPIRED}

RENEW_HINT = {
    DocumentType.PASSPORT: "Check how long renewing your passport takes at your embassy/consulate and start early.",
    DocumentType.ACCOMMODATION: "Ask your landlord or dormitory office for an extended or new contract.",
    DocumentType.ENROLLMENT_CERTIFICATE: "Request an updated enrollment certificate from the university (Neptun / Student Office).",
    DocumentType.RESIDENCE_PERMIT: "Check the renewal procedure on the immigration office's official website.",
}


def max_level(levels: list[ImpactLevel]) -> ImpactLevel:
    if not levels:
        return ImpactLevel.LOW
    return max(levels, key=IMPACT_ORDER.index)


def _fact_evidence(doc: Document, fact: Fact) -> Evidence:
    return Evidence(kind="fact", description=f"{doc.title} expiry date: {fact.value or 'unknown'}",
                    status=fact.status.value, source=fact.source)


def _req_evidence(req: Requirement) -> Evidence:
    return Evidence(kind="requirement", description=req.description,
                    status="verified" if req.verified else "unverified", source=req.source.title)


def assess_requirement(mission: Mission, req: Requirement, doc: Optional[Document],
                       expiry: Fact, as_of: date) -> ImpactItem:
    item = ImpactItem(level=ImpactLevel.LOW, mission_id=mission.id, mission_title=mission.title,
                      requirement_id=req.id, explanation="", evidence=[_req_evidence(req)])
    hint = RENEW_HINT.get(req.document_type, "Check the official source for this requirement.")

    if doc is None:
        item.level = ImpactLevel.HIGH if req.verified else ImpactLevel.MEDIUM
        item.explanation = f"No {req.document_type.value} is linked to this requirement."
        item.recommended_actions = [f"Upload or link your {req.document_type.value}."]
        return item

    item.evidence.insert(0, _fact_evidence(doc, expiry))

    if expiry.status in (Verification.MISSING, Verification.REJECTED) or expiry.value is None:
        item.level = ImpactLevel.UNKNOWN
        item.explanation = f"The expiry date of '{doc.title}' is not known, so the impact cannot be assessed."
        item.recommended_actions = [f"Add or confirm the expiry date of '{doc.title}'."]
        return item

    if mission.deadline is None:
        item.level = ImpactLevel.UNKNOWN
        item.explanation = "The mission has no deadline, so validity cannot be compared."
        item.recommended_actions = ["Add the mission deadline."]
        return item

    needed_until = mission.deadline + timedelta(days=req.min_validity_days_after_deadline)
    item.evidence.append(Evidence(kind="mission", description=(
        f"Deadline {mission.deadline}; document must be valid until {needed_until}"
        f" ({req.min_validity_days_after_deadline} days after deadline)."), source=f"mission:{mission.id}"))

    exp: date = expiry.value
    unconfirmed = expiry.status != Verification.CONFIRMED
    if unconfirmed:
        item.assumptions.append(f"The expiry date {exp} was {expiry.status.value}, not confirmed by you.")
    if not req.verified:
        item.assumptions.append("The requirement itself is not confirmed by an official source.")

    if exp < needed_until:
        certain = not unconfirmed and req.verified
        item.level = ImpactLevel.CRITICAL if certain else ImpactLevel.HIGH
        already = " It is already expired." if exp < as_of else ""
        item.explanation = (f"'{doc.title}' expires on {exp}, before the required {needed_until} "
                            f"for '{mission.title}'.{already}")
        item.recommended_actions = [hint]
        if unconfirmed:
            item.recommended_actions.insert(0, f"Confirm the expiry date of '{doc.title}'.")
        if not req.verified:
            item.recommended_actions.append("Verify this requirement with the institution.")
    elif exp < needed_until + timedelta(days=SAFETY_MARGIN_DAYS):
        item.level = ImpactLevel.MEDIUM
        item.explanation = (f"'{doc.title}' is valid until {exp}, less than {SAFETY_MARGIN_DAYS} days "
                            f"after the required {needed_until}.")
        item.recommended_actions = ["Prepare in advance in case processing is delayed.", hint]
    else:
        item.level = ImpactLevel.LOW
        item.explanation = f"'{doc.title}' is valid until {exp}, which covers '{mission.title}'."
    return item


def _propagate(store: Store, items: list[ImpactItem]) -> list[ImpactItem]:
    """Missions that DEPEND_ON an at-risk mission are also affected."""
    out: list[ImpactItem] = []
    seen: set[str] = {i.mission_id for i in items}
    frontier = [i for i in items if i.level in (ImpactLevel.CRITICAL, ImpactLevel.HIGH)]
    while frontier:
        src = frontier.pop()
        for dep in store.dependents_of(src.mission_id):
            if dep.id in seen or dep.status in CLOSED:
                continue
            seen.add(dep.id)
            it = ImpactItem(
                level=ImpactLevel.HIGH, mission_id=dep.id, mission_title=dep.title,
                explanation=f"'{dep.title}' depends on '{src.mission_title}', which is at risk.",
                evidence=[Evidence(kind="dependency", description=f"{dep.id} DEPENDS_ON {src.mission_id}",
                                   source=f"mission:{dep.id}")],
                recommended_actions=[f"Resolve '{src.mission_title}' first."],
            )
            out.append(it)
            frontier.append(it)
    return out


def analyze(store: Store, student_id: str, event: dict, as_of: Optional[date] = None) -> ImpactReport:
    """
    Supported events:
      {"type": "check"}                                       — current situation, all documents
      {"type": "document_expiry_change", "document_id": ..., "new_expiry_date": "YYYY-MM-DD"}  — what-if
      {"type": "document_removed", "document_id": ...}        — what-if
    What-if events never modify stored data.
    """
    as_of = as_of or date.today()
    etype = event.get("type", "check")
    target = event.get("document_id")

    if etype != "check":
        doc = store.documents.get(target)
        if doc is None or doc.student_id != student_id:
            raise KeyError(f"document {target} not found for student")

    docs = {d.id: d for d in store.student_documents(student_id)}
    items: list[ImpactItem] = []

    for mission in store.student_missions(student_id):
        if mission.status in CLOSED:
            continue
        for req in mission.requirements:
            if etype != "check" and req.satisfied_by != target:
                continue
            doc = docs.get(req.satisfied_by) if req.satisfied_by else None
            expiry = doc.expiry() if doc else Fact()

            if etype == "document_expiry_change":
                expiry = Fact(value=date.fromisoformat(event["new_expiry_date"]),
                              status=Verification.CONFIRMED, source="scenario")
            elif etype == "document_removed":
                doc, expiry = None, Fact()

            item = assess_requirement(mission, req, doc, expiry, as_of)
            if etype != "check":
                item.assumptions.insert(0, f"Hypothetical scenario: {etype} for {target}. Nothing was changed.")
            items.append(item)

    items += _propagate(store, items)
    items.sort(key=lambda i: IMPACT_ORDER.index(i.level), reverse=True)
    return ImpactReport(student_id=student_id, event=event, as_of=as_of,
                        overall_level=max_level([i.level for i in items]), items=items)
