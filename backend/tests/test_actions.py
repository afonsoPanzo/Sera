from urllib.parse import unquote

from app.actions import extract_actions, hungarian_draft

EMAIL_REPLY = """Here is a polite email for your landlord.

**Tárgy:** Elromlott a fűtés (Heating broken)

Tisztelt Főbérlő Úr! (Dear Landlord,)
Értesítem, hogy a lakásban elromlott a fűtés. Kérem, intézkedjen.
Üdvözlettel,
[Név]

**English translation:**
Dear Landlord, the heating is broken.
"""


def types(actions):
    return [a["type"] for a in actions]


def test_draft_becomes_mailto_and_copy():
    acts = extract_actions(EMAIL_REPLY, "translation", "en")
    assert types(acts)[:2] == ["email_draft", "copy"]
    href = unquote(acts[0]["href"])
    assert href.startswith("mailto:?subject=Elromlott a fűtés")
    assert "Tisztelt Főbérlő Úr!" in href and "Dear Landlord" not in href
    assert "English" not in acts[1]["text"] and "Üdvözlettel" in acts[1]["text"]


def test_emails_phones_links_maps():
    reply = ("Call 112 for emergencies or 104 for an ambulance. The GP is at Egyetem tér 1. "
             "Write to neptun@unideb.hu. Where to check: https://biztositas.unideb.hu/medical-treatments and oif.gov.hu.")
    acts = extract_actions(reply, "healthcare", "en")
    t = types(acts)
    assert "email" in t and t.count("call") == 2 and "map" in t
    assert any(a["href"] == "tel:112" for a in acts)
    assert any(a["href"] == "mailto:neptun@unideb.hu" for a in acts)
    assert len(acts) <= 5


def test_links_when_room():
    acts = extract_actions("Apply on enterhungary.gov.hu, see https://oif.gov.hu/students.", "immigration", "en")
    hrefs = [a["href"] for a in acts if a["type"] == "link"]
    assert "https://oif.gov.hu/students" in hrefs and "https://enterhungary.gov.hu" in hrefs


def test_no_false_phone_numbers():
    acts = extract_actions("The fee is 1120 HUF and the code is 106-2-12345/2026, dated 2026.11.04.", "general", "en")
    assert "call" not in types(acts)


def test_hungarian_labels():
    acts = extract_actions("Hívd a 112-t. Hol ellenőrizd: oif.gov.hu", "healthcare", "hu")
    assert any("hívása" in a["label"] for a in acts)


def test_no_draft_without_tisztelt():
    assert hungarian_draft("Just some English text.") is None
    assert "email_draft" not in types(extract_actions(EMAIL_REPLY, "explain", "en"))


def test_chat_response_has_actions(client):
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 200 and isinstance(r.json()["actions"], list)


REAL_REPLY = ("Here is a polite email to your landlord about the broken heating:\n\n"
              "Tisztelt Főbérlő! / Dear Landlord,\n\n"
              "Sajnos a lakásban a fűtés elromlott, ezért szeretném kérni mielőbbi segítségét a javításhoz. Köszönöm szépen!\n\n"
              "(Unfortunately, the heating in the flat is broken, so I would like to ask for your prompt assistance. Thank you!)\n\n"
              "Where to check: Your lease agreement for the landlord's contact details.")


def test_real_reply_draft_is_hungarian_only():
    subject, body = hungarian_draft(REAL_REPLY)
    assert body.startswith("Tisztelt Főbérlő!")
    assert "Dear" not in body and "Unfortunately" not in body and "Where to check" not in body
    assert "Köszönöm szépen!" in body


def test_email_domain_is_not_a_link_and_one_clinic_map():
    acts = extract_actions("Write to neptun@unideb.hu.", "university", "en")
    assert [a["type"] for a in acts] == ["email"]
    acts = extract_actions("Go to the Emergency Clinic at the University's Clinical Center.", "healthcare", "en")
    assert [a["type"] for a in acts].count("map") == 1
