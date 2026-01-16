# Gita Exam API — QA Interview Server

This is a **FastAPI + SQLite** server used as a **black-box QA interview exercise**.  
Candidates test the API using Swagger and a token. They never see the code.

## ⚠️ Important

- This system intentionally contains bugs for QA evaluation. 
- Do NOT use in production. 
- Do NOT expose admin token to candidates. 
- Admin APIs are hidden from Swagger but still accessible via HTTP and require the admin token.

## 🧪 Interview Flow

1. Start server

2. Create candidate token
```bash
curl -X POST '{host}/admin/tokens' \
  --header 'X-ADMIN-TOKEN: {your secret admin token here}' \
  --header 'Content-Type: application/json' \
  --data '{
  "candidate_name": "{candidate name}"
}'
```

3. Give candidate:
   - Base URL 
   - Candidate token 
   - /docs link
   
4. After interview, revoke token
```bash
curl -X DELETE '{host}/admin/tokens/{token}' \
  --header 'X-ADMIN-TOKEN: {your secret admin token here}'
```

---

# Running this project locally

## ✅ Requirements

- Python **3.10+**
- pip
- (Recommended) virtualenv

Check:

```bash
python3 --version
```

## 📦 Setup
1. Create virtualenv (recommended)
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. 🔐 Admin Secret
Create a file called secret.yml in the project root:

```yaml
admin_token: "PUT_A_LONG_RANDOM_SECRET_HERE"
```

## 🚀 Run the Server
```bash
uvicorn exam_api:app --host 0.0.0.0 --port 8000
```

## Open Swagger:
http://localhost:8000/docs

