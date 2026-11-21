# CampusBridge — Backend (MVP)

FastAPI backend for the CampusBridge SDD v1.0. It implements the MVP workflow:

**document upload → extraction → student confirms → mission → impact analysis → recommended actions → approval**

The core is deterministic. Facts, deadlines, mission status and the impact engine never depend on the LLM, so everything runs and is testable without an API key (`MOCK_MODE=1`).

## Run

```bash
cd backend
python -m venv ../.venv && ../.venv/Scripts/pip install -r requirements.txt
cp .env.example .env
../.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs. The demo student id is `stu-demo`.

```bash
../.venv/Scripts/python -m pytest -q
```

## Structure

| File | SDD | What it does |
|---|---|---|
| `app/models.py` | §5, §6 | Domain models, `Fact` with verification status + provenance, mission lifecycle |
| `app/store.py` | §6, §11.1 | In-memory repository (swap for PostgreSQL later) + fictional demo student |
| `app/documents.py` | §5.2, §10.1 | Upload validation, private storage, text extraction, HU/EN classification and date extraction |
| `app/impact.py` | §5.4 | Rule-based Impact Engine: critical / high / medium / low / unknown, with evidence and dependency propagation |
| `app/agent.py` | §5.5, §7 | LLM assistant fed with filtered student context (mock mode without key) |
| `app/main.py` | §9 | API routes |

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/students/{id}` | Digital Twin: profile, documents, missions |
| GET | `/api/students/{id}/deadlines` | Mission deadlines + document expiries, sorted |
| POST | `/api/students/{id}/documents` | Upload (pdf, txt, png, jpg) → classified, fields `extracted_pending_confirmation` |
| POST | `/api/documents/{doc}/fields/{field}` | Student confirms / corrects / rejects an extracted fact |
| POST | `/api/students/{id}/missions` | Create mission (linked documents, dependencies, tasks) |
| GET | `/api/missions/{id}` | Mission, missing requirements, progress |
| POST | `/api/missions/{id}/status` | Status change, only along allowed lifecycle transitions |
| POST | `/api/students/{id}/impact` | Impact report. Events: `check`, `document_expiry_change` (what-if), `document_removed` |
| POST | `/api/students/{id}/approvals` | Prepare an external action (email); nothing runs yet |
| POST | `/api/approvals/{id}/approve` or `/reject` | Human decision. No email provider yet → result `simulated`, never `executed` |
| POST | `/api/students/{id}/agent/chat` | Assistant answer grounded on the student context |

## Demo scenario

Passport valid until 2027-03-10; the residence permit mission (deadline 2027-01-20) needs it valid 180 days longer (a **fictional** demo rule) → **critical**. The address-card mission depends on the permit → **high**. What-if: `{"type":"document_expiry_change","document_id":"doc-passport","new_expiry_date":"2032-01-01"}` → **low**.

## Not done yet

- OCR for images and scanned PDFs (errors are shown to the user).
- LLM extraction/explanation of uploaded letters and agent tool-calling.
- Auth, persistence (PostgreSQL), real email adapter, frontend.
- Real requirement rules: the demo rules are fictional and must be replaced by official sources.
