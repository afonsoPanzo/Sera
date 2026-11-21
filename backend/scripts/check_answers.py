"""Run test questions through the live /api/chat and write a review report.

Usage (backend running on :8000):
    .venv/Scripts/python backend/scripts/check_answers.py
    .venv/Scripts/python backend/scripts/check_answers.py --url http://127.0.0.1:8000

Questions come from backend/knowledge/test-questions.md (Person 4). If that file
does not exist yet, the example questions from /api/topics are used.
Report: backend/knowledge/answers-report.md (ignored by the prompt and by git).

test-questions.md format — one block per question:

    ## How do I get a TAJ card?
    topic: healthcare
    language: en
    Expected answer / key facts the reply must contain...
    Source: https://... (checked 2026-11-21)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

KNOWLEDGE = Path(__file__).resolve().parent.parent / "knowledge"
QUESTIONS_FILE = KNOWLEDGE / "test-questions.md"
REPORT_FILE = KNOWLEDGE / "answers-report.md"
TOPICS = {"general", "healthcare", "university", "immigration", "translation"}


def parse_questions(text: str) -> list[dict]:
    items = []
    for block in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        lines = block.strip().splitlines()
        q = {"question": lines[0].strip(), "topic": "general", "language": "auto", "expected": []}
        for line in lines[1:]:
            low = line.strip().lower()
            if low.startswith("topic:"):
                q["topic"] = low.split(":", 1)[1].strip()
            elif low.startswith("language:"):
                q["language"] = low.split(":", 1)[1].strip()
            else:
                q["expected"].append(line.rstrip())
        if q["topic"] not in TOPICS:
            print(f"! unknown topic '{q['topic']}' for: {q['question']} -> using general", file=sys.stderr)
            q["topic"] = "general"
        q["expected"] = "\n".join(q["expected"]).strip()
        items.append(q)
    return items


def request(url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def example_questions(base: str) -> list[dict]:
    _, topics = request(f"{base}/api/topics")
    out = []
    for t in topics:
        for lang, qs in t["examples"].items():
            out += [{"question": q, "topic": t["id"], "language": lang, "expected": ""} for q in qs]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    base = args.url.rstrip("/")

    try:
        _, health = request(f"{base}/health")
    except urllib.error.URLError:
        print(f"Backend not reachable at {base}. Start it first.", file=sys.stderr)
        return 1

    if QUESTIONS_FILE.exists():
        questions, origin = parse_questions(QUESTIONS_FILE.read_text(encoding="utf-8")), QUESTIONS_FILE.name
    else:
        questions, origin = example_questions(base), "example questions from /api/topics"

    lines = ["# Sera — answer check", "",
             f"- Questions: {len(questions)} ({origin})",
             f"- Model: {health.get('model')} · mock: {health.get('mock')}",
             f"- Run: {time.strftime('%Y-%m-%d %H:%M')}", "",
             "Review each answer: correct? matches the expected facts? right language? "
             "tells the student to check the official source where needed?", ""]
    failures = 0
    for i, q in enumerate(questions, 1):
        t0 = time.time()
        status, body = request(f"{base}/api/chat", {"message": q["question"], "topic": q["topic"],
                                                    "language": q["language"]})
        secs = time.time() - t0
        ok = status == 200
        failures += not ok
        print(f"[{i}/{len(questions)}] {'OK ' if ok else 'ERR'} {status} {secs:4.1f}s  {q['question'][:70]}")
        lines += [f"## {i}. {q['question']}", "",
                  f"topic `{q['topic']}` · asked `{q['language']}` · answered `{body.get('language', '-')}` · "
                  f"HTTP {status} · {secs:.1f}s", ""]
        if q["expected"]:
            lines += ["**Expected (Person 4):**", "", q["expected"], ""]
        lines += ["**Sera answered:**", "", body.get("reply") or f"ERROR: {body.get('detail')}", "", "---", ""]

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {REPORT_FILE}  ({failures} errors)")
    if health.get("mock"):
        print("Note: backend is in MOCK mode, so answers are placeholders.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
