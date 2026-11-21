# Sera Frontend

A React + TypeScript + Vite frontend for the Sera student command centre. It connects to the Python/FastAPI backend in `../backend` (see the root README to start it) and uses the fixed demo student ID `stu-demo`. Based on the original UI from github.com/chriscodes404/Sera.

## Requirements

- Node.js 20 or newer
- npm
- Sera backend running at `http://localhost:8000` (or another URL configured below)

## Run locally

From this directory:

```bash
npm install
cp .env.example .env
npm run dev
```

Open <http://localhost:5173>.

On Windows PowerShell, use:

```powershell
Copy-Item .env.example .env
npm install
npm run dev
```

## Configure the backend URL

The default API base URL is `http://localhost:8000`. To change it, edit `.env`:

```env
VITE_API_URL=http://localhost:8000
```

Restart the Vite development server after changing environment variables.

## Available scripts

```bash
npm run dev       # Start the Vite development server
npm run build     # Type-check and create the production build in dist/
npm run preview   # Preview the production build
npm run typecheck # Run the TypeScript project checks
```

## Implemented screens

- **Overview:** student snapshot, document and mission counts, deadlines, and current impact highlights.
- **My documents:** multipart upload, extracted field status, confirm/correct/reject actions, manual field entry, extraction errors, and extracted text.
- **Missions:** mission creation, mission detail retrieval, task completion, status progression, requirements, and document links.
- **Risk analysis:** current impact assessment, evidence and assumptions, disclaimer, and non-destructive “what if?” scenarios for changing document expiry or removing a document.
- **Approvals:** email approval request creation, complete recipient/subject/body review, approve/reject actions, and simulated-result messaging.
- **Ask Sera (AI assistant):** `POST /api/chat` with topic chips (Healthcare, University, Immigration, Translation), language switch (Auto/EN/HU), markdown rendering and a Listen button (`POST /api/speak`, ElevenLabs).
- **Explain a letter (Document Help):** on My documents, paste a letter or choose a PDF/TXT, or click "Explain with Sera" on a stored document (`POST /api/explain`).

## Backend routes used

| Feature | Endpoint |
|---|---|
| Student dashboard | `GET /api/students/stu-demo` |
| Deadlines | `GET /api/students/stu-demo/deadlines` |
| Current / scenario impact | `POST /api/students/stu-demo/impact` |
| Upload document | `POST /api/students/stu-demo/documents` |
| Verify extracted field | `POST /api/documents/{docId}/fields/{field}` |
| Mission details | `GET /api/missions/{missionId}` |
| Create mission | `POST /api/students/stu-demo/missions` |
| Mission status | `POST /api/missions/{id}/status` |
| Mission task | `POST /api/missions/{id}/tasks/{taskId}?done=true` |
| List/create approvals | `GET/POST /api/students/stu-demo/approvals` |
| Approve/reject | `POST /api/approvals/{id}/approve` or `/reject` |
| Chat | `POST /api/students/stu-demo/agent/chat` |

## Important demo constraints

- Login/authentication is not implemented. The frontend uses `stu-demo`.
- The backend stores data in memory; restarting it resets the demo data.
- Chat may return mock responses when no OpenAI API key is configured. The UI labels mock responses.
- Image OCR is not implemented. Extraction errors are shown and manual fields can be entered.
- Email sending is not implemented. An approval result with status `simulated` is explicitly shown as **not sent**.
- Impact simulations do not modify the stored student record.
- The additional 180-day passport validity rule in the demo is fictional.

## Project structure

```text
frontend/
├── .env.example
├── .gitignore
├── index.html
├── package.json
├── README.md
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── vite.config.ts
├── examples/
│   └── carta.txt
└── src/
    ├── api/
    │   ├── client.ts
    │   └── types.ts
    ├── components/
    │   ├── Shell.tsx
    │   └── UI.tsx
    ├── pages/
    │   ├── ApprovalsPage.tsx
    │   ├── AssistantPage.tsx
    │   ├── DashboardPage.tsx
    │   ├── DocumentsPage.tsx
    │   ├── MissionsPage.tsx
    │   └── RisksPage.tsx
    ├── App.tsx
    ├── index.css
    ├── main.tsx
    ├── utils.ts
    └── vite-env.d.ts
```

## Notes

The frontend follows the endpoint shapes and workflow contract in the supplied Sera Frontend Guide. If a backend response differs from that contract, check the route list at `http://localhost:8000/` before changing the frontend types or request payloads.
