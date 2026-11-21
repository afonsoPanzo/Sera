"""Document Vault: validation, private storage, text extraction, deterministic
classification and date extraction (SDD §5.2, workflow §10.1).

Extracted values are stored as EXTRACTED (pending confirmation); only the
student can turn them into CONFIRMED facts. Document text is untrusted data.
"""

from __future__ import annotations

import io
import os
import re
from datetime import date
from pathlib import Path

from .models import Document, DocumentType, Fact, Verification
from .store import Store, new_id

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", Path(__file__).resolve().parent.parent / "data" / "uploads"))
MAX_BYTES = 10 * 1024 * 1024
ALLOWED = {".pdf": "application/pdf", ".txt": "text/plain", ".png": "image/png",
           ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

HU_MONTHS = {"január": 1, "február": 2, "március": 3, "április": 4, "május": 5, "június": 6, "július": 7,
             "augusztus": 8, "szeptember": 9, "október": 10, "november": 11, "december": 12}

CLASS_KEYWORDS: list[tuple[DocumentType, tuple[str, ...]]] = [
    (DocumentType.RESIDENCE_PERMIT, ("residence permit", "tartózkodási engedély")),
    (DocumentType.PASSPORT, ("passport", "útlevél")),
    (DocumentType.ACCOMMODATION, ("lease", "rental agreement", "dormitory", "bérleti szerződés", "kollégium")),
    (DocumentType.ENROLLMENT_CERTIFICATE, ("enrollment", "enrolment", "hallgatói jogviszony")),
    (DocumentType.OFFICIAL_LETTER, ("idegenrendészeti", "bevándorlási", "országos idegenrendészeti főigazgatóság",
                                    "tisztelt", "értesítjük", "hivatal", "immigration office")),
]

EXPIRY_WORDS = ("lejár", "érvényes", "valid until", "expir", "érvényességi")
DEADLINE_WORDS = ("határidő", "határidőn", "deadline", "napjáig", "-ig", "until")

_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})[.\-/]\s?(\d{1,2})[.\-/]\s?(\d{1,2})\.?"), "num"),
    (re.compile(r"\b(\d{4})\.\s?(" + "|".join(HU_MONTHS) + r")\s?(\d{1,2})\.?", re.IGNORECASE), "hu"),
]


class UploadError(ValueError):
    pass


def validate(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise UploadError(f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED)}")
    if not content:
        raise UploadError("Empty file")
    if len(content) > MAX_BYTES:
        raise UploadError("File larger than 10 MB")
    if ext == ".pdf" and not content.startswith(b"%PDF"):
        raise UploadError("File does not look like a real PDF")
    return ext


def extract_text(ext: str, content: bytes) -> tuple[str | None, str | None]:
    """Returns (text, error). Errors are shown to the user, never hidden."""
    if ext == ".txt":
        return content.decode("utf-8", errors="replace"), None
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return None, "PDF text extraction unavailable (pypdf not installed)"
        try:
            text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(content)).pages).strip()
        except Exception as e:  # malformed PDF
            return None, f"Could not read PDF: {type(e).__name__}"
        return (text, None) if text else (None, "No text layer found (scanned PDF needs OCR)")
    return None, "OCR for images is not implemented yet; please enter the details manually"


def classify(text: str) -> DocumentType:
    t = text.lower()
    for dtype, words in CLASS_KEYWORDS:
        if any(w in t for w in words):
            return dtype
    return DocumentType.OTHER


def find_dates(text: str) -> list[tuple[date, int]]:
    """All dates in the text with their character position."""
    found: list[tuple[date, int]] = []
    for pat, kind in _DATE_PATTERNS:
        for m in pat.finditer(text):
            y, mo, d = m.group(1), m.group(2), m.group(3)
            month = HU_MONTHS[mo.lower()] if kind == "hu" else int(mo)
            try:
                found.append((date(int(y), month, int(d)), m.start()))
            except ValueError:
                continue
    return sorted(set(found), key=lambda x: x[1])


def extract_fields(text: str, doc_id: str) -> dict[str, Fact]:
    fields: dict[str, Fact] = {}
    low = text.lower()
    src = f"document:{doc_id}"
    for d, pos in find_dates(text):
        window = low[max(0, pos - 60): pos + 40]
        if "expiry_date" not in fields and any(w in window for w in EXPIRY_WORDS):
            fields["expiry_date"] = Fact(value=d, status=Verification.EXTRACTED, source=src, confidence=0.6)
        elif "deadline" not in fields and any(w in window for w in DEADLINE_WORDS):
            fields["deadline"] = Fact(value=d, status=Verification.EXTRACTED, source=src, confidence=0.6)
    dates = [d for d, _ in find_dates(text)]
    if dates:
        fields["dates_found"] = Fact(value=[x.isoformat() for x in dates], status=Verification.EXTRACTED,
                                     source=src, confidence=0.9)
    return fields


def ingest(store: Store, student_id: str, filename: str, content: bytes, title: str | None = None) -> Document:
    ext = validate(filename, content)
    doc_id = new_id("doc")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    key = f"{student_id}/{doc_id}{ext}"
    path = UPLOAD_DIR / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)  # original preserved, private (never served by URL)

    text, error = extract_text(ext, content)
    doc = Document(
        id=doc_id, student_id=student_id,
        type=classify(text) if text else DocumentType.OTHER,
        title=title or Path(filename).stem, original_filename=Path(filename).name,
        storage_key=key, extracted_text=text, extraction_error=error,
        fields=extract_fields(text, doc_id) if text else {},
    )
    store.documents[doc_id] = doc
    return doc
