from datetime import date

from app.impact import analyze
from app.models import ImpactLevel

SID = "stu-demo"
TODAY = date(2026, 11, 21)


def levels(report):
    return {(i.mission_id, i.requirement_id): i.level for i in report.items}


def test_current_situation_passport_is_critical(fresh_store):
    r = analyze(fresh_store, SID, {"type": "check"}, TODAY)
    lv = levels(r)
    # passport 2027-03-10 < deadline 2027-01-20 + 180 days (demo rule)
    assert lv[("mis-permit", "req-permit-passport")] == ImpactLevel.CRITICAL
    assert r.overall_level == ImpactLevel.CRITICAL
    item = next(i for i in r.items if i.requirement_id == "req-permit-passport")
    assert any(e.kind == "fact" and e.status == "confirmed" for e in item.evidence)


def test_dependency_propagates_to_address_card(fresh_store):
    r = analyze(fresh_store, SID, {"type": "check"}, TODAY)
    assert levels(r)[("mis-addresscard", None)] == ImpactLevel.HIGH


def test_unconfirmed_fact_is_never_critical(fresh_store):
    # housing expiry is only EXTRACTED; registration rule is unverified
    r = analyze(fresh_store, SID, {"type": "document_expiry_change", "document_id": "doc-housing",
                                   "new_expiry_date": "2026-12-01"}, TODAY)
    lv = levels(r)
    assert lv[("mis-permit", "req-permit-housing")] == ImpactLevel.CRITICAL  # scenario value + verified rule
    assert lv[("mis-registration", "req-reg-housing")] == ImpactLevel.HIGH   # rule not verified
    r2 = analyze(fresh_store, SID, {"type": "check"}, TODAY)
    # real stored value 2027-01-31 covers the 2027-01-20 deadline by only 11 days -> medium
    item = next(i for i in r2.items if i.requirement_id == "req-permit-housing")
    assert item.level == ImpactLevel.MEDIUM
    assert any("not confirmed" in a for a in item.assumptions)


def test_what_if_does_not_modify_data(fresh_store):
    before = fresh_store.documents["doc-passport"].expiry().value
    analyze(fresh_store, SID, {"type": "document_expiry_change", "document_id": "doc-passport",
                               "new_expiry_date": "2030-01-01"}, TODAY)
    assert fresh_store.documents["doc-passport"].expiry().value == before


def test_renewed_passport_removes_risk(fresh_store):
    r = analyze(fresh_store, SID, {"type": "document_expiry_change", "document_id": "doc-passport",
                                   "new_expiry_date": "2032-01-01"}, TODAY)
    assert r.overall_level == ImpactLevel.LOW
    assert all(i.mission_id != "mis-addresscard" for i in r.items)


def test_missing_expiry_is_unknown(fresh_store):
    fresh_store.documents["doc-enrollment"].fields.pop("expiry_date")
    r = analyze(fresh_store, SID, {"type": "check"}, TODAY)
    assert levels(r)[("mis-permit", "req-permit-enroll")] == ImpactLevel.UNKNOWN


def test_removed_document(fresh_store):
    r = analyze(fresh_store, SID, {"type": "document_removed", "document_id": "doc-enrollment"}, TODAY)
    assert levels(r)[("mis-permit", "req-permit-enroll")] == ImpactLevel.HIGH
