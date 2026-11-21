# Sera

Administrative intelligence for international students in Hungary: documents → missions → impact analysis → approved actions.

- **Backend:** [`backend/`](backend/README.md) (FastAPI). Run with `uvicorn app.main:app --app-dir backend --port 8000`.
- **Frontend:** [`frontend/`](frontend/README.md) (React + Vite). Run with `npm --prefix frontend install` then `npm --prefix frontend run dev` → http://localhost:5173. API contract: **[FRONTEND.md](FRONTEND.md)**.
- **API docs:** http://localhost:8000/docs while the backend is running.

`main.py`, `prompts.py` and `studentmate-backend.zip` in the root are the old chatbot prototype. They are kept for reference only.
