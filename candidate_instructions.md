# Gita Exam API — QA Exercise

## Context

You are testing the API of an online exam system designed to work in environments with patchy internet connectivity.

Students can:
- Load an exam
- Select answers (each selection is synced immediately)
- Resume the exam after connectivity loss
- Submit the exam
- Once submitted, the exam should be locked

The system supports:
- Multiple exams
- Multiple-choice questions
- Some questions may have multiple correct answers

You are given:
- A base API URL
- Two API tokens
- API documentation via Swagger (`/docs`)
- A sample exam with the exam_id `exam1` (you should not modify this exam; it is only a sample for you understand the system)

---

## Your Tasks (90 minutes)

1. **Understand the system** from the API docs.
2. **Design test cases** for the core flows.
3. **Explore the API and find as many issues as you can.**
4. **Write a test report** describing:
   - The issues you found
   - Steps to reproduce
   - Expected vs actual behavior
   - Severity / impact
5. **List ambiguities or missing requirements** in the spec.

---

## Rules

- Treat this as a **black-box system**.
- Do not assume how it is implemented.
- Use any tool you like: browser, Swagger UI, Postman, curl, etc.
- Focus on **product correctness, data correctness, and system behavior**, not UI.

---

## Authentication

All requests must include the Authorization header like this: `Bearer <your_token>`

---

## Main Concepts

- An **exam** can be:
  - Created
  - Activated
  - Attempted
  - Submitted

- A **student**:
  - Loads exam
  - Saves answers incrementally
  - Can resume from saved state
  - Submits exam
  - After submission, the exam should be locked

---

## Available APIs (see Swagger for details)

- `POST /exam` → Create exam
- `POST /exam/{exam_id}/activate` → Activate exam
- `GET /exam/active` → Get currently active exam
- `GET /exam/{exam_id}` → Load full exam
- `POST /exam/{exam_id}/select` → Save answer selection
- `GET /exam/{exam_id}/state` → Get saved state
- `POST /exam/{exam_id}/submit` → Submit exam

---

## Expected High-Level Behavior

- Only **active** exams should be attempted.
- Answer selection should be **saved immediately**.
- State should be **restored correctly**.
- Once submitted:
  - Exam should be locked.
  - No further changes should be allowed.

---

## What To Submit

Please submit **one document (PDF or Markdown)** with the following sections:

### A) Test Cases

Write **10–15 test cases** covering:
- Happy paths
- Negative cases
- Edge cases
- State transitions

Suggested format:

| ID | Scenario | Steps | Expected Result |

---

### B) Bug Report

For each issue:

- Title
- Steps to reproduce
- Expected result
- Actual result
- Severity / impact

---

### C) Spec / Product Issues

List:
- Missing requirements
- Ambiguities
- Logical holes
- Questions you would ask the product team

---

## Evaluation Criteria

You are not evaluated on the number of bugs alone, but on:

- Depth of thinking
- Coverage of scenarios
- Quality and clarity of bug reports
- Product and system thinking
- Communication clarity

Good luck!