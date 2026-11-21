# Knowledge base (Person 4)

Put verified information here. Every `*.md` file in this folder (except this README) is added to the AI's system prompt automatically on the next request. No restart is needed.

## Rules

- One file per topic: `healthcare.md`, `university.md`, `immigration.md`, `daily-life.md`.
- Short facts and steps, not long articles. The total is capped at about 12,000 characters.
- **Every fact needs a source line** (official URL + date checked). The AI is told to cite it.
- Only write what you verified. If something varies by city or university, say so.
- Write in English. The AI answers in English or Hungarian on its own.

## Template

```markdown
## How to get a TAJ card (health insurance number)
- Who: students with ...
- Where: ...
- Steps:
  1. ...
  2. ...
- Source: https://... (checked 2026-11-21)
```

## The 10 test questions

Put the 10 realistic questions and their verified answers in `test-questions.md`, using the same format. Person 1 uses them to check the AI's answers. That file is excluded from the prompt.
