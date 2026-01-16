from fastapi import FastAPI, Header, HTTPException, Depends, Query
from pydantic import BaseModel, Field
import sqlite3
import uuid
import yaml
from typing import Dict, List, Optional

app = FastAPI(
    title="Gita Exam API",
    description="API for a large-scale exam system.",
    version="0.1"
)

DB = "exam.db"

with open("secret.yml") as f:
    secrets = yaml.safe_load(f)
ADMIN_TOKEN = secrets["admin_token"]

# ---------------- DB ----------------

def get_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    c = db.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS tokens (
        token TEXT PRIMARY KEY,
        candidate_id TEXT,
        active INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS exams (
        id TEXT PRIMARY KEY,
        title TEXT,
        active INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS questions (
        id TEXT,
        exam_id TEXT,
        text TEXT,
        lang TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS options (
        id TEXT,
        question_id TEXT,
        text TEXT,
        is_correct INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS attempts (
        exam_id TEXT,
        candidate_id TEXT,
        submitted INTEGER,
        PRIMARY KEY (exam_id, candidate_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS answers (
        exam_id TEXT,
        candidate_id TEXT,
        question_id TEXT,
        option_id TEXT
    )""")

    db.commit()

    row = c.execute("SELECT COUNT(*) as c FROM exams").fetchone()
    if row["c"] == 0:
        exam_id = "exam1"
        c.execute("INSERT INTO exams VALUES (?, ?, ?)", (exam_id, "Sample Exam", 1))

        q1 = "q1"
        q2 = "q2"

        c.execute("INSERT INTO questions VALUES (?, ?, ?, ?)", (q1, exam_id, "What is 2+2?", "en"))
        c.execute("INSERT INTO questions VALUES (?, ?, ?, ?)", (q2, exam_id, "Select prime numbers", "en"))

        c.execute("INSERT INTO options VALUES (?, ?, ?, ?)", ("o1", q1, "3", 0))
        c.execute("INSERT INTO options VALUES (?, ?, ?, ?)", ("o2", q1, "4", 1))
        c.execute("INSERT INTO options VALUES (?, ?, ?, ?)", ("o3", q1, "5", 0))

        c.execute("INSERT INTO options VALUES (?, ?, ?, ?)", ("o4", q2, "2", 1))
        c.execute("INSERT INTO options VALUES (?, ?, ?, ?)", ("o5", q2, "3", 1))
        c.execute("INSERT INTO options VALUES (?, ?, ?, ?)", ("o6", q2, "4", 0))

        db.commit()

init_db()

# ---------------- AUTH ----------------

def require_admin(x_admin_token: str = Header(...)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(403, "Not admin")

def get_candidate(token: str = Query(..., description="Your access token")):
    db = get_db()
    row = db.execute("SELECT * FROM tokens WHERE token=?", (token,)).fetchone()
    if not row or row["active"] == 0:
        raise HTTPException(401, "Invalid or revoked token")
    return row["candidate_id"]

# ---------------- MODELS ----------------

class CreateExamReq(BaseModel):
    title: str

class CreateExamOut(BaseModel):
    exam_id: str

class ExamOut(BaseModel):
    id: str
    title: str
    active: int

class OptionOut(BaseModel):
    id: str
    text: str

class QuestionOut(BaseModel):
    id: str
    text: str
    options: List[OptionOut]

class ExamWithQuestionsOut(BaseModel):
    exam: ExamOut
    questions: List[QuestionOut]

class SelectAnswerIn(BaseModel):
    question_id: str = Field(..., example="q1")
    option_id: str = Field(..., example="o2")

class StateOut(BaseModel):
    answers: Dict[str, List[str]]
    submitted: bool

# ---------------- CANDIDATE APIS ----------------

@app.post(
    "/exam",
    summary="Create a new exam",
    description="""
    Creates a new exam in DRAFT state.

    The exam will not be visible to students until it is activated.
    """,
    response_model=CreateExamOut,
    tags=["Candidate"]
)
def create_exam(req: CreateExamReq, candidate_id: str = Depends(get_candidate)):
    db = get_db()
    exam_id = str(uuid.uuid4())
    db.execute("INSERT INTO exams VALUES (?, ?, 0)", (exam_id, req.title))
    db.commit()
    return {"exam_id": exam_id}

@app.post(
    "/exam/{exam_id}/activate",
    summary="Activate an exam",
    description="""
    Marks the given exam as active.

    Only one exam should be active at a time in the system.
    """,
    tags=["Candidate"]
)
def activate_exam(exam_id: str, candidate_id: str = Depends(get_candidate)):
    db = get_db()

    # INTENTIONAL: no check for multiple active exams
    db.execute("UPDATE exams SET active=1 WHERE id=?", (exam_id,))
    db.commit()
    return {"status": "activated"}

@app.get(
    "/exam/active",
    summary="Get currently active exam",
    description="Returns the currently active exams if any. Returns null if no active exam is available.",
    tags=["Candidate"]
)
def get_active_exam(candidate_id: str = Depends(get_candidate)):
    db = get_db()
    row = db.execute("SELECT * FROM exams WHERE active=1").fetchone()
    if not row:
        return {"exam": None}
    return dict(row)

@app.get(
    "/exam/{exam_id}",
    response_model=ExamWithQuestionsOut,
    summary="Load full exam definition",
    description="""
    Loads the full exam structure including all questions and options.

    If the exam has already been submitted by the candidate, this endpoint will return 403.
    """,
    tags=["Candidate"]
)
def load_exam(exam_id: str, candidate_id: str = Depends(get_candidate)):
    db = get_db()

    att = db.execute("SELECT * FROM attempts WHERE exam_id=? AND candidate_id=?", (exam_id, candidate_id)).fetchone()
    if att and att["submitted"]:
        raise HTTPException(403, "Exam already submitted")

    exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
    if not exam:
        raise HTTPException(404, "Exam not found")

    qs = db.execute("SELECT * FROM questions WHERE exam_id=?", (exam_id,)).fetchall()
    questions = []
    for q in qs:
        opts = db.execute("SELECT id, text FROM options WHERE question_id=?", (q["id"],)).fetchall()
        questions.append({
            "id": q["id"],
            "text": q["text"],
            "options": [dict(o) for o in opts]
        })

    return {
        "exam": dict(exam),
        "questions": questions
    }

@app.post(
    "/exam/{exam_id}/select",
    summary="Save an answer selection",
    description="""
    Saves the user's selected option for a question.

    This endpoint is designed for low-connectivity environments:
    the client should call this every time a user selects an option.

    The server persists the answer immediately.
    """,
    tags=["Candidate"]
)
def select_option(exam_id: str, payload: SelectAnswerIn, candidate_id: str = Depends(get_candidate)):
    db = get_db()

    att = db.execute("SELECT * FROM attempts WHERE exam_id=? AND candidate_id=?", (exam_id, candidate_id)).fetchone()
    if att and att["submitted"]:
        raise HTTPException(403, "Exam already submitted")

    db.execute("INSERT OR IGNORE INTO attempts VALUES (?, ?, 0)", (exam_id, candidate_id))

    # INTENTIONAL: missing many validations
    db.execute("INSERT INTO answers VALUES (?, ?, ?, ?)", (exam_id, candidate_id, payload.question_id, payload.option_id))
    db.commit()

    return {"status": "saved"}

@app.get(
    "/exam/{exam_id}/state",
    response_model=StateOut,
    summary="Get current exam state",
    description="""
    Returns the currently saved answers for this candidate and whether the exam is already submitted.

    This is used when the device comes back online after connectivity loss.
    """,
    tags=["Candidate"]
)
def get_state(exam_id: str, candidate_id: str = Depends(get_candidate)):
    db = get_db()

    # INTENTIONAL: isolation bug
    rows = db.execute("SELECT question_id, option_id FROM answers WHERE exam_id=?", (exam_id,)).fetchall()

    answers = {}
    for r in rows:
        answers.setdefault(r["question_id"], []).append(r["option_id"])

    att = db.execute("SELECT * FROM attempts WHERE exam_id=? AND candidate_id=?", (exam_id, candidate_id)).fetchone()

    return {
        "answers": answers,
        "submitted": bool(att["submitted"]) if att else False
    }

@app.post(
    "/exam/{exam_id}/submit",
    summary="Submit the exam",
    description="""
    Marks the exam as submitted.

    After submission:
    - The exam becomes locked.
    - No further answers should be accepted.
    - The exam cannot be loaded again.
    """,
    tags=["Candidate"]
)
def submit_exam(exam_id: str, candidate_id: str = Depends(get_candidate)):
    db = get_db()
    db.execute("INSERT OR IGNORE INTO attempts VALUES (?, ?, 0)", (exam_id, candidate_id))
    # INTENTIONAL: no completeness or idempotency checks
    db.execute("UPDATE attempts SET submitted=1 WHERE exam_id=? AND candidate_id=?", (exam_id, candidate_id))
    db.commit()
    return {"status": "submitted"}

# ---------------- ADMIN APIS (HIDDEN) ----------------

class CreateTokenReq(BaseModel):
    candidate_name: str

@app.post("/admin/tokens", include_in_schema=False, dependencies=[Depends(require_admin)])
def create_token(req: CreateTokenReq):
    token = str(uuid.uuid4())
    candidate_id = req.candidate_name + "_" + token[:6]
    db = get_db()
    db.execute("INSERT INTO tokens VALUES (?, ?, 1)", (token, candidate_id))
    db.commit()
    return {"token": token, "candidate_id": candidate_id}

@app.get("/admin/tokens", include_in_schema=False, dependencies=[Depends(require_admin)])
def list_tokens():
    db = get_db()
    rows = db.execute("SELECT * FROM tokens").fetchall()
    return [dict(r) for r in rows]

@app.delete("/admin/tokens/{token}", include_in_schema=False, dependencies=[Depends(require_admin)])
def revoke_token(token: str):
    db = get_db()
    db.execute("UPDATE tokens SET active=0 WHERE token=?", (token,))
    db.commit()
    return {"status": "revoked"}
