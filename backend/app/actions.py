"""Proactive action buttons for Sera replies.

Actions are found deterministically in the reply text (emails, phone numbers,
official websites, known places, Hungarian message drafts) — the AI never
invents them. Nothing is executed by the backend: the frontend only opens the
student's own email app, phone dialer, map or browser, and the student decides.
"""

from __future__ import annotations

import re
from urllib.parse import quote

MAX_ACTIONS = 5

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"https?://[^\s)\]>\"'*]+")
# Official domains the model often writes without https://
BARE_DOMAINS = ["enterhungary.gov.hu", "oif.gov.hu", "nav.gov.hu", "neak.gov.hu", "studyinhungary.hu",
                "kormanyablak.hu", "neptun.unideb.hu", "biztositas.unideb.hu", "insurance.unideb.hu", "unideb.hu"]

EMERGENCY_NUMBERS = {
    "112": {"en": "Call 112 (emergency)", "hu": "112 hívása (segélyhívó)"},
    "104": {"en": "Call 104 (ambulance)", "hu": "104 hívása (mentők)"},
    "107": {"en": "Call 107 (police)", "hu": "107 hívása (rendőrség)"},
    "105": {"en": "Call 105 (fire)", "hu": "105 hívása (tűzoltók)"},
}

# Places we can safely point to on a map (search queries, not invented exact addresses).
PLACES = [
    (re.compile(r"Egyetem t[ée]r 1", re.I), "Egyetem tér 1, 4032 Debrecen", "UniDeb GP office", "Egyetemi háziorvos"),
    (re.compile(r"Coordinating Cent(er|re) for International Education|Nemzetközi Oktatási Koordinációs", re.I),
     "Coordinating Center for International Education, University of Debrecen", "International Education Center", "Nemzetközi Oktatási Központ"),
    (re.compile(r"Emergency and Gastroenterology|Emergency Clinic|sürgősségi", re.I),
     "Sürgősségi Klinika, Debreceni Egyetem Klinikai Központ, Debrecen", "Emergency Clinic", "Sürgősségi klinika"),
    (re.compile(r"Clinical Cent(er|re)|Klinikai Központ", re.I),
     "Debreceni Egyetem Klinikai Központ, Debrecen", "Clinical Center", "Klinikai Központ"),
    (re.compile(r"kormányablak|government (office|window)|kormányhivatal", re.I),
     "Kormányablak Debrecen", "Government office (Kormányablak)", "Kormányablak"),
    (re.compile(r"\bOIF\b|Idegenrendészeti|immigration office", re.I),
     "Országos Idegenrendészeti Főigazgatóság Debrecen", "Immigration office (OIF)", "Idegenrendészet (OIF)"),
    (re.compile(r"\bNAV\b|tax office|adóhivatal", re.I),
     "NAV ügyfélszolgálat Debrecen", "Tax office (NAV)", "NAV ügyfélszolgálat"),
    (re.compile(r"gyógyszertár|pharmacy|patika", re.I),
     "gyógyszertár Debrecen", "Pharmacies nearby", "Gyógyszertárak"),
]

LABELS = {
    "draft": {"en": "Open in email app", "hu": "Megnyitás e-mailben"},
    "copy": {"en": "Copy Hungarian text", "hu": "Magyar szöveg másolása"},
    "email": {"en": "Email {x}", "hu": "E-mail: {x}"},
    "link": {"en": "Open {x}", "hu": "{x} megnyitása"},
    "map": {"en": "Show {x} on map", "hu": "{x} a térképen"},
}


def _label(kind: str, lang: str, x: str = "") -> str:
    return LABELS[kind]["hu" if lang == "hu" else "en"].format(x=x)


def hungarian_draft(reply: str) -> tuple[str, str] | None:
    """Find a Hungarian formal message ('Tisztelt ...') in the reply. Returns (subject, body)."""
    lines = reply.replace("\r", "").split("\n")
    start = next((i for i, l in enumerate(lines) if re.search(r"\bTisztelt\b", l)), None)
    if start is None:
        return None
    subject = ""
    for l in lines[max(0, start - 4):start]:
        m = re.search(r"T[áa]rgy\s*:\s*(.+)", l.replace("*", ""))
        if m:
            subject = re.sub(r"\s*\(.*?\)\s*$", "", m.group(1)).strip()
    body = []
    for l in lines[start:]:
        clean = l.strip().lstrip(">").strip().replace("**", "")
        if re.match(r"^\s*(English|Angol|Dear\b|Translation|Where to check|Hol ellenőrizd|Note\b|Megjegyzés|\*{3}|---)",
                    clean, re.I):
            break
        # "Tisztelt Főbérlő! / Dear Landlord," -> keep only the Hungarian side
        if " / " in clean:
            left, right = clean.split(" / ", 1)
            if not _HU_CHARS.search(right):
                clean = left.rstrip()
        # a whole line that is an English gloss in parentheses
        if re.fullmatch(r"\(.*\)", clean) and not _HU_CHARS.search(clean):
            continue
        body.append(clean)
    text = "\n".join(body).strip()
    # inline English glosses in parentheses: "(Dear Landlord,)"
    text = re.sub(r"\s*\((?=[^)]*[A-Za-z])[^)áéíóöőúüűÁÉÍÓÖŐÚÜŰ]*\)", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return (subject, text) if len(text) > 15 else None


_HU_CHARS = re.compile(r"[áéíóöőúüűÁÉÍÓÖŐÚÜŰ]")


def extract_actions(reply: str, topic: str, language: str) -> list[dict]:
    actions: list[dict] = []
    seen: set[str] = set()

    def add(action: dict) -> None:
        key = action.get("href") or action.get("text", "")
        if key and key not in seen and len(actions) < MAX_ACTIONS:
            seen.add(key)
            actions.append(action)

    emails = list(dict.fromkeys(EMAIL_RE.findall(reply)))
    draft = hungarian_draft(reply) if topic in ("translation", "general", "immigration", "university") else None
    if draft:
        subject, body = draft
        to = emails[0] if emails else ""
        href = f"mailto:{to}?subject={quote(subject)}&body={quote(body)}"
        add({"type": "email_draft", "label": _label("draft", language), "href": href})
        add({"type": "copy", "label": _label("copy", language), "text": body})

    for e in emails:
        add({"type": "email", "label": _label("email", language, e), "href": f"mailto:{e}"})

    for num, labels in EMERGENCY_NUMBERS.items():
        # allow Hungarian suffixes ("112-t", "104-es") but not codes/dates ("106-2-123", "2026.11.04")
        if re.search(rf"(?<![\d./-]){num}(?!\d|[./-]\d)", reply):
            add({"type": "call", "label": labels["hu" if language == "hu" else "en"], "href": f"tel:{num}"})

    emergency_clinic = PLACES[2][0].search(reply)
    for pattern, query, en, hu in PLACES:
        if pattern is PLACES[3][0] and emergency_clinic:
            continue  # the Emergency Clinic is inside the Clinical Center: one map button is enough
        if pattern.search(reply):
            href = "https://www.google.com/maps/search/?api=1&query=" + quote(query)
            add({"type": "map", "label": _label("map", language, hu if language == "hu" else en), "href": href})

    urls = [u.rstrip(".,;:") for u in URL_RE.findall(reply)]
    for d in BARE_DOMAINS:
        if re.search(rf"(?<![\w/.@]){re.escape(d)}", reply) and not any(d in u for u in urls):
            urls.append(f"https://{d}")
    for u in dict.fromkeys(urls):
        host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
        add({"type": "link", "label": _label("link", language, host), "href": u})

    return actions
