from fastapi import FastAPI, Header, HTTPException, Depends, Query
from pydantic import BaseModel, Field, constr
import sqlite3
import uuid
import yaml
from typing import Dict, List
from contextlib import contextmanager
import os

# ---------------- APP ----------------

app = FastAPI(
    title="Gita Exam API",
    description="API for a large-scale exam system.",
    version="0.2"
)

DB = "exam.db"

# ---------------- SAFE STARTUP ----------------

if not os.path.exists("secret.yml"):
    raise RuntimeError("secret.yml missing")

with open("secret.yml") as f:
    secrets = yaml.safe_load(f)

if "admin_token" not in secrets:
    raise RuntimeError("admin_token missing in secret.yml")

ADMIN_TOKEN = secrets["admin_token"]

# ---------------- DB ----------------

@contextmanager
def get_db():
    conn = sqlite3.connect(DB, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Pragmas for SQLite concurrency safety
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA max_page_count = 500000;")

    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        c = db.cursor()

        c.execute("""CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            candidate_id TEXT,
            active INTEGER
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS exams (
            id TEXT PRIMARY KEY,
            title TEXT,
            active INTEGER,
            creator_id TEXT
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            exam_id TEXT,
            text TEXT,
            lang TEXT,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS options (
            id TEXT PRIMARY KEY,
            question_id TEXT,
            text TEXT,
            is_correct INTEGER,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS attempts (
            exam_id TEXT,
            candidate_id TEXT,
            submitted INTEGER,
            PRIMARY KEY (exam_id, candidate_id),
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        )""")

        # Prevent infinite growth
        c.execute("""CREATE TABLE IF NOT EXISTS answers (
            exam_id TEXT,
            candidate_id TEXT,
            question_id TEXT,
            option_id TEXT,
            PRIMARY KEY (exam_id, candidate_id, question_id),
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
            FOREIGN KEY (option_id) REFERENCES options(id) ON DELETE CASCADE
        )""")

        row = c.execute("SELECT COUNT(*) as c FROM exams").fetchone()
        if row["c"] == 0:
            exam_id = "exam1"
            c.execute("INSERT INTO exams VALUES (?, ?, ?, ?)", (exam_id, "Sample Exam", 1, "test_candidate"))

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


init_db()

# ---------------- AUTH ----------------

def require_admin(x_admin_token: str = Header(...)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(403, "Not admin")

def get_candidate(token: str = Query(..., description="Your access token")):
    with get_db() as db:
        row = db.execute("SELECT * FROM tokens WHERE token=?", (token,)).fetchone()
        if not row or row["active"] == 0:
            raise HTTPException(401, "Invalid or revoked token")
        return row["candidate_id"]

# ---------------- MODELS ----------------

SafeStr = constr(max_length=200)

class CreateExamReq(BaseModel):
    title: SafeStr

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
    answers: Dict[str, str]
    submitted: bool

class CreateOptionIn(BaseModel):
    text: SafeStr
    is_correct: bool = False

class CreateQuestionWithOptionsReq(BaseModel):
    text: SafeStr
    lang: SafeStr = "en"
    options: List[CreateOptionIn]

class CreateQuestionWithOptionsOut(BaseModel):
    question_id: str


# ---------------- CANDIDATE APIS ----------------

@app.get("/exam/all",
        response_model=List[ExamOut],
         summary="List all exams",
         description="Lists all exams created in the system by the user.",
         tags=["Candidate"]
         )
def list_exams(candidate_id: str = Depends(get_candidate)):
    with get_db() as db:
        rows = db.execute("SELECT * FROM exams WHERE creator_id=?", (candidate_id,)).fetchall()
        return [dict(r) for r in rows]

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
    with get_db() as db:
        rows = db.execute(
            "SELECT question_id, option_id FROM answers WHERE exam_id=? AND candidate_id=?",
            (exam_id, candidate_id)
        ).fetchall()

        answers = {r["question_id"]: r["option_id"] for r in rows}

        att = db.execute("SELECT * FROM attempts WHERE exam_id=? AND candidate_id=?", (exam_id, candidate_id)).fetchone()

        return {
            "answers": answers,
            "submitted": bool(att["submitted"]) if att else False
        }

@app.get(
    "/exam/active",
    summary="Get currently active exam",
    description="Returns the currently active exams if any. Returns null if no active exam is available.",
    tags=["Candidate"]
)
def get_active_exam(candidate_id: str = Depends(get_candidate)):
    with get_db() as db:
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
    with get_db() as db:
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

        return {"exam": dict(exam), "questions": questions}

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
    with get_db() as db:
        no_of_exams = db.execute("SELECT COUNT(*) as c FROM exams WHERE creator_id=?", (candidate_id,)).fetchone()["c"]
        if no_of_exams >= 25:
            raise HTTPException(400, "Exam creation limit reached (25)")
        exam_id = str(uuid.uuid4())[:6]
        db.execute("INSERT INTO exams VALUES (?, ?, 0, ?)", (exam_id, req.title, candidate_id))
        return {"exam_id": exam_id}

@app.post(
    "/exam/{exam_id}/questions",
    summary="Add a question (with options) to an exam",
    description="""
    Adds a new question to the given exam together with all its options in one atomic operation.

    Rules:
    - At least 2 options are required.
    - At least 1 option must be marked as correct.
    - If any insert fails, nothing is written.
    """,
    response_model=CreateQuestionWithOptionsOut,
    tags=["Candidate"]
)
def add_question_with_options(
    exam_id: str,
    req: CreateQuestionWithOptionsReq,
    candidate_id: str = Depends(get_candidate)
):
    if exam_id == "exam1":
        raise HTTPException(400, "Modifications to the sample exam are not allowed")

    if len(req.options) < 2:
        raise HTTPException(400, "A question must have at least 2 options")

    if len(req.options) > 6:
        raise HTTPException(400, "A question can have at most 6 options")

    if not any(o.is_correct for o in req.options):
        raise HTTPException(400, "At least one option must be marked as correct")

    with get_db() as db:

        no_of_questions = db.execute("SELECT COUNT(*) as c FROM questions WHERE exam_id=?", (exam_id,)).fetchone()["c"]
        if no_of_questions >= 25:
            raise HTTPException(400, "Question limit reached for this exam (25)")

        exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
        if not exam:
            raise HTTPException(404, "Exam not found")

        qid = str(uuid.uuid4())
        db.execute(
            "INSERT INTO questions (id, exam_id, text, lang) VALUES (?, ?, ?, ?)",
            (qid, exam_id, req.text, req.lang)
        )

        for opt in req.options:
            oid = str(uuid.uuid4())
            db.execute(
                "INSERT INTO options (id, question_id, text, is_correct) VALUES (?, ?, ?, ?)",
                (oid, qid, opt.text, int(opt.is_correct))
            )

    return {"question_id": qid}

@app.delete(
    "/questions/{question_id}",
    summary="Delete a question",
    description="""
    Deletes a question and:

    - All its options
    - All answers given for this question

    This operation is irreversible.
    """,
    tags=["Candidate"]
)
def delete_question(
    question_id: str,
    candidate_id: str = Depends(get_candidate)
):
    with get_db() as db:
        row = db.execute(
            "SELECT exam_id FROM questions WHERE id=?",
            (question_id,)
        ).fetchone()

        if not row:
            raise HTTPException(404, "Question not found")

        if row["exam_id"] == "exam1":
            raise HTTPException(400, "Modifications to the sample exam are not allowed")

        q = db.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
        if not q:
            raise HTTPException(404, "Question not found")

        db.execute("DELETE FROM answers WHERE question_id=?", (question_id,))
        db.execute("DELETE FROM options WHERE question_id=?", (question_id,))
        db.execute("DELETE FROM questions WHERE id=?", (question_id,))

    return {"status": "deleted"}



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

    if exam_id == "exam1":
        raise HTTPException(400, "Modifications to the sample exam are not allowed")

    with get_db() as db:
        db.execute("UPDATE exams SET active=0")
        db.execute("UPDATE exams SET active=1 WHERE id=?", (exam_id,))
    return {"status": "activated"}

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

    if exam_id == "exam1":
        raise HTTPException(400, "Modifications to the sample exam are not allowed")

    with get_db() as db:
        att = db.execute("SELECT * FROM attempts WHERE exam_id=? AND candidate_id=?", (exam_id, candidate_id)).fetchone()
        if att and att["submitted"]:
            raise HTTPException(403, "Exam already submitted")

        db.execute("INSERT OR IGNORE INTO attempts VALUES (?, ?, 0)", (exam_id, candidate_id))

        db.execute("""
            INSERT INTO answers (exam_id, candidate_id, question_id, option_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(exam_id, candidate_id, question_id)
            DO UPDATE SET option_id=excluded.option_id
        """, (exam_id, candidate_id, payload.question_id, payload.option_id))

    return {"status": "saved"}

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

    if exam_id == "exam1":
        raise HTTPException(400, "Modifications to the sample exam are not allowed")

    with get_db() as db:
        db.execute("INSERT OR IGNORE INTO attempts VALUES (?, ?, 0)", (exam_id, candidate_id))
        db.execute("UPDATE attempts SET submitted=1 WHERE exam_id=? AND candidate_id=?", (exam_id, candidate_id))
    return {"status": "submitted"}

# ---------------- ADMIN ----------------

class CreateTokenReq(BaseModel):
    candidate_name: SafeStr

@app.post("/admin/tokens", include_in_schema=False, dependencies=[Depends(require_admin)])
def create_token(req: CreateTokenReq):
    token = str(uuid.uuid4())
    candidate_id = req.candidate_name + "_" + token[:6]
    with get_db() as db:
        db.execute("INSERT INTO tokens VALUES (?, ?, 1)", (token, candidate_id))
    return {"token": token, "candidate_id": candidate_id}

@app.get("/admin/tokens", include_in_schema=False, dependencies=[Depends(require_admin)])
def list_tokens():
    with get_db() as db:
        rows = db.execute("SELECT * FROM tokens").fetchall()
        return [dict(r) for r in rows]

@app.delete("/admin/tokens/{token}", include_in_schema=False, dependencies=[Depends(require_admin)])
def revoke_token(token: str):
    with get_db() as db:
        rows = db.execute("UPDATE tokens SET active=0 WHERE token=?", (token,)).fetchall()
        if db.total_changes == 0:
            raise HTTPException(404, "Token not found")
    return {"status": "revoked"}

@app.delete("/admin/candidates/{candidate_id}/data", include_in_schema=False, dependencies=[Depends(require_admin)])
def delete_candidate_data(candidate_id: str):
    with get_db() as db:
        rows = db.execute("SELECT * FROM tokens WHERE candidate_id=?", (candidate_id,)).fetchall()
        if not rows:
            raise HTTPException(404, "Candidate not found")
        db.execute("DELETE FROM exams WHERE creator_id=?", (candidate_id,))
        db.execute("DELETE FROM tokens WHERE candidate_id=?", (candidate_id,))
    return {"status": "deleted"}
