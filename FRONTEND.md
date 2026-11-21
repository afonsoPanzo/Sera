# Frontend Guide — Sera

This guide is for whoever builds the frontend. The backend is ready for the demo. This is what you need to connect to it.

## 1. Run the backend (5 minutes)

You need Python 3.11 or newer. From the repository root:

```bash
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt      # Windows
# macOS/Linux: .venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

- **Base URL:** `http://localhost:8000`
- **Using the backend running on a teammate's laptop (same Wi-Fi):** use `http://<their-IP>:8000` instead (ask them for the IP; they start the server with `--host 0.0.0.0`). In Vite, put it in `.env.local` as `VITE_API_URL=http://<their-IP>:8000` and read it with `import.meta.env.VITE_API_URL`. First check that `http://<their-IP>:8000/health` opens in your browser.
- **Interactive docs:** http://localhost:8000/docs. You can try every endpoint there and see the exact formats.
- **CORS:** open (`*`), so Vite on `localhost:5173` works without any setup.
- **No OpenAI key:** the chat runs in mock mode (`"mock": true`).
- **Demo student:** always use `stu-demo`. There is no login yet.

> ⚠️ Data lives **in memory**. Restarting the server resets everything to the demo data. Handy for rehearsing the presentation.

## ⭐ Start here: the chat (main deliverable)

This is the endpoint for the chat screen, the language selector and the topic buttons. Languages are **English and Hungarian** only.

```ts
// Topic buttons + example questions (labels in EN and HU)
const topics = await api<{ id: Topic; label: { en: string; hu: string };
                           examples: { en: string[]; hu?: string[] } }[]>(`/api/topics`);

type Topic = "general" | "healthcare" | "university" | "immigration" | "translation";

interface ChatRequest {
  message: string;                        // 1–2000 chars
  language?: "auto" | "en" | "hu";        // "auto" = answer in the language the student wrote in
  topic?: Topic;                          // set by the button the student clicked; default "general"
  history?: { role: "user" | "assistant"; content: string }[];   // oldest first, last 10 used
}
interface ChatResponse {
  reply: string;                          // plain text with line breaks and numbered steps
  language: "en" | "hu";                  // language actually used
  topic: Topic;
  model: string;                          // "mock" when there is no API key
  mock: boolean;
}

const r = await post<ChatResponse>(`/api/chat`, {
  message: "How do I get a TAJ card?", language: "auto", topic: "healthcare", history,
});
history.push({ role: "user", content: input }, { role: "assistant", content: r.reply });
```

- **Translation button:** the reply has the Hungarian text first, then a short English version. Show it so it's easy to copy.
- **Errors:** `422` = invalid input (empty message, unknown language or topic). `502` = the AI failed, show "try again". `503` = AI unavailable (no credits).
- Render `reply` keeping line breaks (`white-space: pre-wrap`), or use a small markdown renderer.

Everything below (documents, missions, impact) is the **extended Sera API**. Use it only if there is time.

## 2. The demo story (what the screens must tell)

The SDD says the point is **not the chat**. The point is showing that the system connects documents → missions → impact. The demo goes like this:

1. **Dashboard:** the student Amara has 3 documents, 3 missions and deadlines.
2. **Red alert:** her passport expires before the residence permit renewal needs it (**critical**). Because of that, the address card mission is also at risk (**high**).
3. **Upload a Hungarian letter.** The system classifies it and pulls out the dates. Those dates show as **"pending confirmation"**.
4. **The student confirms the date.** Only then does the value become `confirmed`.
5. **Create a mission** from the letter.
6. **"What if?" simulator:** "what if I renew my passport until 2032?" → the risk disappears. The real data does not change.
7. **Email to the office:** it is drafted and needs **explicit approval**. The result is `simulated`, because nothing is really sent.

For the demo letter, save this as `letter.txt`:

```
Országos Idegenrendészeti Főigazgatóság
Tisztelt Amara Demo!
Értesítjük, hogy tartózkodási engedélye 2027. január 20. napján lejár.
A hosszabbítási kérelmet legkésőbb 2027.01.10. határidőig nyújtsa be.
```

## 3. Suggested screens → endpoints

| Screen | Request |
|---|---|
| Dashboard | `GET /api/students/stu-demo` |
| Deadline timeline | `GET /api/students/stu-demo/deadlines` |
| Risk panel | `POST /api/students/stu-demo/impact` with `{"event":{"type":"check"}}` |
| "What if?" simulator | `POST /api/students/stu-demo/impact` with a scenario event (see §5) |
| Document upload | `POST /api/students/stu-demo/documents` (multipart) |
| Review extracted data | `POST /api/documents/{docId}/fields/{field}` |
| Mission detail | `GET /api/missions/{missionId}` |
| New mission | `POST /api/students/stu-demo/missions` |
| Change status / task | `POST /api/missions/{id}/status`, `POST /api/missions/{id}/tasks/{taskId}?done=true` |
| Approvals | `POST /api/students/stu-demo/approvals`, `GET .../approvals`, `POST /api/approvals/{id}/approve` or `/reject` |
| Chat (main) | `POST /api/chat` and `GET /api/topics` (see "Start here") |
| Chat with the student's context | `POST /api/students/stu-demo/agent/chat` |

## 4. Types (TypeScript)

Copy this into `src/api/types.ts`. Dates always arrive as `YYYY-MM-DD` strings and timestamps as ISO strings.

```ts
export type Verification =
  | "confirmed" | "extracted_pending_confirmation" | "inferred"
  | "missing" | "expired" | "rejected";

export interface Fact<T = unknown> {
  value: T | null;
  status: Verification;
  source: string;            // "document:doc-passport", "user", "scenario"...
  confidence: number | null;
  updated_at: string;
  updated_by: string;
}

export interface Student {
  id: string; name: string; nationality: string | null; university: string | null;
  program: string | null; academic_year: string | null; preferred_language: string;
}

export type DocumentType =
  | "passport" | "enrollment_certificate" | "accommodation_document"
  | "residence_permit" | "official_letter" | "other";

export interface StudentDocument {
  id: string; student_id: string; type: DocumentType; title: string;
  original_filename: string | null;
  extracted_text: string | null;
  extraction_error: string | null;   // if set, SHOW it to the user
  fields: Record<string, Fact>;      // e.g. expiry_date, deadline, address, dates_found
  uploaded_at: string;
}

export type MissionStatus =
  | "CREATED" | "ANALYSIS" | "PLANNED" | "IN_PROGRESS" | "WAITING_FOR_USER"
  | "WAITING_FOR_INSTITUTION" | "COMPLETED" | "CANCELLED" | "BLOCKED" | "EXPIRED";

export interface SourceReference {
  title: string; url: string | null; retrieved_at: string | null; official: boolean; note: string | null;
}

export interface Requirement {
  id: string; description: string; document_type: DocumentType;
  min_validity_days_after_deadline: number;
  satisfied_by: string | null;       // document id
  source: SourceReference; verified: boolean;
}

export interface Mission {
  id: string; student_id: string; title: string; description: string; institution: string;
  status: MissionStatus; deadline: string | null; depends_on: string[];
  requirements: Requirement[];
  tasks: { id: string; title: string; done: boolean }[];
  completion_criteria: string;
}

export interface Twin { student: Student; documents: StudentDocument[]; missions: Mission[]; }

export interface Deadline {
  kind: "mission" | "document_expiry"; id: string; title: string;
  date: string; days_left: number; status: Verification;
}

export type ImpactLevel = "critical" | "high" | "medium" | "low" | "unknown";

export interface ImpactItem {
  level: ImpactLevel; mission_id: string; mission_title: string; requirement_id: string | null;
  explanation: string;
  evidence: { kind: "fact" | "requirement" | "mission" | "dependency"; description: string;
              status: string | null; source: string | null }[];
  assumptions: string[];             // show as "assumptions / uncertainties"
  recommended_actions: string[];
}

export interface ImpactReport {
  student_id: string; event: Record<string, unknown>; as_of: string;
  overall_level: ImpactLevel; items: ImpactItem[];   // already sorted, most severe first
  disclaimer: string;                                // always show it
}

export type ApprovalStatus = "pending" | "approved" | "rejected" | "executed" | "simulated" | "failed";

export interface ApprovalRequest {
  id: string; student_id: string; mission_id: string | null; action_type: "send_email";
  summary: string; payload: { to: string; subject: string; body: string };
  status: ApprovalStatus; result: string | null; created_at: string; decided_at: string | null;
}

export interface ChatReply { reply: string; model: string; mock: boolean; }
```

## 5. Request examples

```ts
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const SID = "stu-demo";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API + path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Invalid request");
  return data as T;
}
const post = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// Dashboard
const twin = await api<Twin>(`/api/students/${SID}`);

// Current risks
const report = await post<ImpactReport>(`/api/students/${SID}/impact`, { event: { type: "check" } });

// "What if?": change a document's expiry (nothing stored is changed)
await post<ImpactReport>(`/api/students/${SID}/impact`, {
  event: { type: "document_expiry_change", document_id: "doc-passport", new_expiry_date: "2032-01-01" },
});
// "What if?": lose a document
await post<ImpactReport>(`/api/students/${SID}/impact`, {
  event: { type: "document_removed", document_id: "doc-housing" },
});

// Upload (do NOT set Content-Type yourself)
const form = new FormData();
form.append("file", file);                  // .pdf .txt .png .jpg .jpeg, max 10 MB
form.append("title", "Immigration letter"); // optional
const doc = await api<StudentDocument>(`/api/students/${SID}/documents`, { method: "POST", body: form });

// Confirm, correct or reject an extracted field
await post(`/api/documents/${doc.id}/fields/expiry_date`, { decision: "confirm" });
await post(`/api/documents/${doc.id}/fields/expiry_date`, { decision: "confirm", value: "2027-01-25" });
await post(`/api/documents/${doc.id}/fields/expiry_date`, { decision: "reject" });

// New mission linked to the letter
await post<Mission>(`/api/students/${SID}/missions`, {
  title: "Answer the immigration letter", institution: "OIF", deadline: "2027-01-10",
  document_ids: [doc.id], depends_on: [], tasks: ["Read the letter", "Collect documents"],
});

// Email approval
const ap = await post<ApprovalRequest>(`/api/students/${SID}/approvals`, {
  mission_id: "mis-permit", to: "office@example.org", subject: "Kérdés", body: "Tisztelt ...",
});
await post<ApprovalRequest>(`/api/approvals/${ap.id}/approve`, {});   // or /reject

// Chat (history = recent messages, oldest first)
await post<ChatReply>(`/api/students/${SID}/agent/chat`, {
  message: "What should I fix first?", language: "auto", history: [],
});
```

## 6. UI rules that must not break

These come from the SDD, and a jury will notice them:

1. **Show the status of every fact.** An `extracted_pending_confirmation` value must look different (yellow "pending confirmation" badge) and have **Confirm / Correct / Reject** buttons.
2. **Show the evidence behind each impact.** Every risk should expand to its `evidence` and `assumptions`. The idea is "the system shows why".
3. **Always show the `disclaimer`** next to the impact report.
4. **Approvals.** The screen shows the `summary` and the full `payload` (recipient, subject, text) **before** the Approve / Reject buttons.
5. **Never write "Sent ✓" when the status is `simulated`.** Show the `result` text, which says nothing was really sent.
6. **If a document has `extraction_error`** (e.g. images, which have no OCR yet), show the error and let the user fill in the fields by hand. Use the fields endpoint with `value`.
7. **Suggested colours per level:** critical = red, high = orange, medium = yellow, low = green, unknown = grey.

## 7. Errors

- `400`: invalid upload (type, size, fake PDF). The message is in `detail` (a string).
- `404`: the id does not exist.
- `409`: transition not allowed, or approval already decided. Example: `"Cannot go from CREATED to COMPLETED"`.
- `422`: validation error. Here `detail` is a **list** of errors (FastAPI format), not a string.
- `502`: the AI service failed. Show "try again" and never make up an answer.
- `503`: the AI is unavailable (e.g. the OpenAI account has no credits). Show "assistant temporarily unavailable".

Allowed mission status transitions:
`CREATED → ANALYSIS → PLANNED → IN_PROGRESS → (WAITING_FOR_USER | WAITING_FOR_INSTITUTION ↔ IN_PROGRESS) → COMPLETED`.
Any active state can also go to `CANCELLED`. The `BLOCKED` and `EXPIRED` transitions are in `backend/app/models.py`.

## 8. Demo data (fixed ids)

| id | What it is |
|---|---|
| `doc-passport` | Passport, valid until 2027-03-10 (confirmed) |
| `doc-enrollment` | Enrollment certificate, until 2027-08-31 |
| `doc-housing` | Dormitory contract, until 2027-01-31 (**pending confirmation**) |
| `mis-permit` | Renew residence permit, deadline 2027-01-20 |
| `mis-registration` | Spring semester registration, deadline 2027-02-05 |
| `mis-addresscard` | Address card, depends on `mis-permit` |

> The rule "passport valid for 180 more days" is **fictional**, made up for the demo only.

## 9. Not available yet (don't rely on it)

- Login / authentication. Use `stu-demo`.
- Persistence: data resets with the server.
- OCR for images.
- Real email sending.
- LLM explanation of letters. It is planned and will appear as a new field on the document.

Backend questions: talk to whoever owns `backend/`, or see `backend/README.md`.
