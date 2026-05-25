# AI Voice Call Agent

A complete demo of an **AI-powered outbound voice calling system**.
Upload a list of leads, click a button, and a Groq-powered AI agent
calls each person via **Vapi**, holds a natural conversation, extracts
useful information, and stores everything in a database that a React
dashboard visualizes in real time.

---

## 1. Project Overview

**Workflow:**

1. Admin uploads a CSV/XLSX of clients (name, phone, company, email).
2. Backend parses rows and inserts them as `Client` records.
3. Admin clicks **Start AI Calls** in the dashboard.
4. Backend tells **Vapi** to dial each client. Vapi bundles
   telephony + speech-to-text + LLM + text-to-speech in one call.
5. Vapi connects the call and runs the conversation using
   **Groq `llama-3.3-70b-versatile`** as the LLM.
6. Vapi streams events to our `/vapi-webhook` endpoint:
   `status-update`, `transcript`, and `end-of-call-report`.
7. Every conversational turn is saved as a `Message` row tied to a `Call`.
8. When the call ends, Vapi's full report triggers a Groq extraction
   pass that updates the client's `interest_level`, callback time,
   budget, objections, etc.
9. The React dashboard shows live call status, transcripts, summaries,
   and extracted info.

---

## 2. Architecture

```
ai_call_agent/
├── backend/                      FastAPI REST + Vapi webhooks
│   ├── app.py                    FastAPI app factory & entry point
│   ├── config.py                 Env-driven Config object
│   ├── database.py               SQLAlchemy engine + session + get_db()
│   ├── models/                   SQLAlchemy: Client, Call, Message
│   ├── routes/                   APIRouters (upload/call/webhook/dashboard/invite)
│   ├── services/                 Business logic (ai, vapi, memory, extraction, ...)
│   ├── prompts/sales_prompt.txt  System prompt template
│   ├── templates/talk.html       Public "click-to-talk" landing page (Jinja2)
│   ├── utils/                    logger.py, helpers.py
│   ├── database/app.db           SQLite (auto-created)
│   └── uploads/                  Saved CSV/XLSX files
└── frontend/                     React + Vite + Tailwind dashboard
    ├── src/components/           Navbar, StatCard, StatusBadge, TranscriptModal
    ├── src/pages/                Dashboard, Upload, Clients, Calls
    ├── src/services/api.js       Axios client (proxied via /api)
    └── vite.config.js            Dev proxy to FastAPI :5000
```

**Why Vapi:**

- One vendor handles telephony, STT, LLM, and TTS — no Twilio account,
  no Deepgram account, no ElevenLabs account needed.
- It natively supports Groq as the LLM provider, so we keep the same model
  (`llama-3.3-70b-versatile`) you originally asked for.
- Vapi sends a single consolidated `end-of-call-report` webhook with the
  full transcript, summary, and analysis — perfect for our extraction pass.

---

## 3. Tech Stack

- **Backend:** Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2, SQLite
- **Voice platform:** Vapi (https://vapi.ai) — accessed via REST (`requests`)
- **LLM:** Groq Python SDK — model `llama-3.3-70b-versatile`
- **File processing:** pandas, openpyxl
- **Frontend:** React 18, Vite, Axios, TailwindCSS, React Router
- **Tunneling:** ngrok (so Vapi can reach your local webhook)

---

## 4. Prerequisites

You'll need free accounts on:

1. **Vapi** — https://dashboard.vapi.ai
   - New accounts get free trial credits, enough for several demo calls.
   - Create a **Phone Number** inside Vapi (Phone Numbers → Buy Number).
2. **Groq** — https://console.groq.com (free tier).
3. **ngrok** — https://ngrok.com/download (free tier).

> ⚠️ **Rotate keys you've ever pasted into a chat.** Treat the Vapi
> private key and Groq key like passwords; they only belong in `.env`.

---

## 5. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Open `backend/.env` and fill in:

```env
APP_ENV=development
SECRET_KEY=replace-with-something-random

# From https://dashboard.vapi.ai (API Keys section)
VAPI_PRIVATE_KEY=
VAPI_PUBLIC_KEY=

# From https://dashboard.vapi.ai (Phone Numbers section) — UUID of a number you own
VAPI_PHONE_NUMBER_ID=

# Any random string; Vapi will echo it back on every webhook so we can verify it
VAPI_WEBHOOK_SECRET=any-random-string-you-like

# From https://console.groq.com (API Keys section)
GROQ_API_KEY=

# Your current ngrok URL (no trailing slash)
BASE_URL=https://<your-subdomain>.ngrok-free.app

BUSINESS_NAME=Acme AI Solutions
AGENT_NAME=Alex
BUSINESS_SERVICE=AI-powered business automation tools
```

Run the backend:

```bash
python app.py
# or, equivalently:
uvicorn app:app --host 0.0.0.0 --port 5000 --reload
```

It listens on `http://localhost:5000`. FastAPI also exposes an
interactive API explorer at `http://localhost:5000/docs` (Swagger UI).

### Start ngrok (separate terminal)

```bash
ngrok http 5000
```

Copy the `https://...ngrok-free.app` URL into `BASE_URL` in `.env`
and **restart the backend** so the URL we hand to Vapi is correct.

> Every time ngrok restarts, the URL changes — update `BASE_URL`
> and restart the backend.

---

## 6. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies
`/api/*` → `http://localhost:5000/*`, so no extra config is needed.

---

## 7. Vapi Setup (one-time)

1. **Sign up** at https://dashboard.vapi.ai.
2. Go to **API Keys** → copy the **Private Key** and **Public Key**
   into your `.env`.
3. Go to **Phone Numbers** → **Create Phone Number**:
   - Use a Vapi-provided number (charged from your trial credits), or
   - Import a Twilio number you already own (free for the number, you only
     pay Twilio's per-minute rate for calls).
4. Click the new phone number and copy its **ID** (a UUID).
   Put it in `.env` as `VAPI_PHONE_NUMBER_ID`.

That's it — we don't pre-create an "assistant" in the Vapi dashboard,
because our backend passes the full assistant config (system prompt,
Groq model, voice, transcriber) **per call** via the REST API.

---

## 8. Groq Setup

1. Sign up at https://console.groq.com.
2. Create an API key.
3. Paste it into `.env` as `GROQ_API_KEY`.

The model is `llama-3.3-70b-versatile` (see `config.py`).
Vapi uses this same model for the live conversation, and our backend
uses it again for post-call extraction + summaries.

---

## 9. ngrok Setup

```bash
# install
sudo snap install ngrok            # Linux
brew install ngrok                 # macOS
# or download from https://ngrok.com/download

ngrok config add-authtoken <YOUR_AUTHTOKEN>
ngrok http 5000
```

Copy the public HTTPS URL into `BASE_URL` and restart the backend.

---

## 10. Example CSV Format

`clients.csv`:

```csv
name,phone_number,company,email
Jane Cooper,+14155550100,Acme Corp,jane@acme.com
Cody Fisher,+14155550101,Globex,cody@globex.com
Esther Howard,+14155550102,Initech,esther@initech.com
```

Accepted column aliases:

| Canonical      | Aliases also accepted                                  |
| -------------- | ------------------------------------------------------ |
| `name`         | `full_name`, `client_name`, `customer_name`, `contact` |
| `phone_number` | `phone`, `mobile`, `cell`, `contact_number`, `number`  |
| `company`      | `organization`, `org`, `business`, `company_name`      |
| `email`        | `email_address`, `mail`                                |

XLSX is supported the same way.

---

## 11. API Reference

All endpoints return JSON unless noted otherwise.

### Upload

```
POST /upload-clients         multipart/form-data, field: "file"
```

### Calling

```
POST /start-calls            { "limit": 5 }          # optional
POST /call/<client_id>
```

### Vapi Webhook (called by Vapi, not the UI)

```
POST /vapi-webhook           Handles status-update, transcript, end-of-call-report
```

### Dashboard reads

```
GET  /clients?search=<text>
GET  /clients/<id>
GET  /calls?status=<status>&client_id=<id>
GET  /calls/<id>             includes full transcript
GET  /transcripts/<call_id>
GET  /dashboard/stats
```

### Example: place a single call

```bash
curl -X POST http://localhost:5000/call/1
```

### Example: bulk start calls

```bash
curl -X POST http://localhost:5000/start-calls \
     -H "Content-Type: application/json" \
     -d '{"limit": 3}'
```

---

## 12. Example Conversation Flow

```
[Vapi dials +14155550100]
AI       : Hi Jane, this is Alex calling from Acme AI Solutions.
           Do you have a quick minute to chat?
Customer : Sure, what's this about?
AI       : We help companies like yours automate repetitive tasks
           with AI. Could that be useful for your team?
Customer : Maybe. What does it cost?
AI       : Pricing starts around five hundred a month. Would you like
           a quick demo this week?
Customer : Yeah, can you call me back Friday afternoon?
AI       : Absolutely. Friday afternoon works — I'll call you then.
           Have a great day!
[Hang up — Vapi sends end-of-call-report]

Extracted info saved to Client.extracted_information:
{
  "interest_level": "medium",
  "callback_requested": true,
  "callback_time": "Friday afternoon",
  "budget": "around $500/month",
  "business_needs": "automate repetitive tasks",
  "objections": "",
  "follow_up": "schedule a demo Friday afternoon"
}
```

---

## 13. How the AI stays "natural"

- The system prompt (`backend/prompts/sales_prompt.txt`) tells the LLM:
  - Talk like a human on the phone.
  - Two short sentences max per reply.
  - Only one question at a time.
  - No markdown / bullets — this is spoken audio.
- The Vapi assistant config sets `maxTokens: 150`, so the LLM physically
  can't ramble.
- Voice provider is Vapi's bundled `Elliot` voice — natural-sounding
  and included in your trial credits. You can swap this in
  `services/vapi_service.py` (e.g. `11labs` + `voiceId: "Adam"`).
- Vapi handles barge-in (the user can interrupt the AI), turn detection,
  and end-of-utterance silence automatically.

---

## 14. Common Issues

| Symptom                                | Fix                                                                  |
| -------------------------------------- | -------------------------------------------------------------------- |
| `VAPI_PRIVATE_KEY is missing`          | Fill it in `.env` and restart the backend                            |
| `VAPI_PHONE_NUMBER_ID is missing`      | Create a phone number in Vapi dashboard, copy its UUID into `.env`   |
| Webhooks never arrive                  | `BASE_URL` must match the *current* ngrok URL; restart the backend   |
| Vapi 401 on call creation              | Wrong/rotated private key                                            |
| Vapi 402 / "out of credits"            | Top up your Vapi balance or wait for the trial credits to renew      |
| Numbers parsed as `1234567890.0`       | Save the CSV with phone_number as text, or include a leading `+`     |
| AI talks too long / sounds robotic     | Lower `maxTokens` in `vapi_service.py` and tweak the prompt          |
| `401 unauthorized` on webhook          | `VAPI_WEBHOOK_SECRET` mismatch; clear it everywhere or set it once   |

---

## 15. Security Note

The Vapi **private** key and the Groq key can both be used to spend
money / pull data from your accounts. Keep them only in `backend/.env`
(which is gitignored). If a key ever ends up in a chat log, screenshot,
or Git commit — **rotate it immediately** in the respective dashboard.

---

## 16. License

MIT — demo / educational use.
