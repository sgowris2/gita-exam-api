# Gita Exam API — Interviewer Guide (PRIVATE)

## Purpose

This is a **black-box QA exercise**. The candidate never sees the code. They only get:
- Base URL (of deployed API Server)
- Token (Generated per candidate via admin API)
- Swagger docs (available at `/docs`)
- candidate_instructions.md

They must:
- Understand the system
- Design test cases
- Explore
- Find bugs
- Report issues
- Identify spec holes

---

## What This Test Evaluates

- Test design ability
- Curiosity and exploration
- Understanding of stateful systems
- API testing skills
- Data correctness & isolation thinking
- Product thinking
- Communication clarity

---

## How To Run The Interview

1. Create a token for the candidate (admin API).
2. Give them:
   - Base URL
   - Token
   - Link to `/docs`
   - Candidate.md
3. Do NOT tell them:
   - Admin APIs exist
   - How the system is implemented
4. Timebox: 75–90 minutes.

---

## How To Evaluate

Do NOT count bugs.

Look at:
- What *categories* of bugs they find
- Whether they test:
  - Invalid inputs
  - State transitions
  - Repeated calls
  - Cross-flow behavior
- How they write bug reports
- Whether they question the spec

---

## Expected Bug Categories (Private Checklist)

### 🟢 Basic / Junior-Level

- Can submit exam without answering anything
- Can submit exam multiple times
- Can answer with invalid `question_id` or `option_id`
- Can activate a non-existent exam
- Can create unlimited exams
- Duplicate answers appear in state
- Can answer draft / inactive exam

---

### 🟡 Mid-Level

- Multiple active exams allowed
- `/exam/active` returns arbitrary exam if multiple active
- No validation that option belongs to question
- No validation that question belongs to exam
- No concept of single-select vs multi-select
- No completeness checks before submit
- No proper exam lifecycle (draft/active/closed)
- State becomes inconsistent after repeated operations

---

### 🔴 Senior-Level

- 🚨 **Data isolation bug**: `/exam/{id}/state` leaks other users’ answers
- Race condition between submit and select
- No idempotency (double submit / double select)
- No transaction boundaries → partial writes possible
- Token revocation does not invalidate in-flight sessions
- Permission model is broken (any user can create/activate exams)
- No concurrency safety in SQLite usage
- No audit / ownership validation of attempts

---

## Senior-Level Spec Questions You Want To Hear

Strong candidates will ask:

- Can there be multiple active exams?
- Who is allowed to create/activate exams?
- Are questions single-select or multi-select?
- Can exams be closed globally?
- What happens if network retries the same request?
- What happens if two devices answer the same exam?
- What is the source of truth: client or server?
- How is cheating prevented?
- What is the lifecycle of an exam?

---

## Scoring Guide (1–5 each)

- Test case quality
- Bug report clarity
- Depth of issues found
- Product/system thinking
- Communication clarity

---

## Signals

### Weak
- Only tests happy path
- Only finds superficial validation issues
- Poorly written bug reports
- No questions about spec

### Good
- Tests negative cases and state transitions
- Finds multiple logic issues
- Writes clear repro steps
- Questions ambiguities

### Excellent
- Finds isolation / race / idempotency issues
- Thinks in terms of system behavior
- Questions product model and permissions
- Thinks like an owner, not just a tester
