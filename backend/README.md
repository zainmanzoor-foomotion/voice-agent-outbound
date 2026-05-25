# AI Voice Call Agent — Backend

FastAPI + Vapi + Groq backend that places outbound AI phone calls.

See the [root README](../README.md) for the full project documentation,
architecture, and setup instructions.

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # then fill in Vapi + Groq + BASE_URL
python app.py              # or: uvicorn app:app --reload --port 5000
```

In a second terminal, expose port 5000 with ngrok and paste the https
URL into `BASE_URL` in `.env`, then restart the backend:

```bash
ngrok http 5000
```

Once running, FastAPI exposes an interactive API browser at
`http://localhost:5000/docs` (Swagger UI) and `/redoc`.
