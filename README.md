# AI Chatbot — Next.js + FastAPI + Puter

A streaming AI chatbot with a polished dark UI. Uses **Puter's free OpenAI-compatible API** — no API key needed.

---

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11+ |
| AI Provider | Puter (free, OpenAI-compatible) |
| Model | GPT-4o mini |

---

## Project Structure

```
chatbot/
├── backend/
│   ├── main.py            # FastAPI app with streaming endpoint
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── page.tsx       # Main chat page
    │   ├── layout.tsx
    │   └── globals.css
    ├── components/
    │   ├── MessageBubble.tsx   # User/assistant message bubbles
    │   ├── Markdown.tsx        # Markdown + syntax highlighting
    │   ├── TypingIndicator.tsx # Animated dots
    │   └── ChatInput.tsx       # Textarea with send button
    ├── lib/
    │   └── api.ts         # SSE streaming client
    └── types/
        └── chat.ts        # TypeScript types
```

---

## Setup

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**

---

## How Puter API works

Puter provides a free OpenAI-compatible endpoint at `https://api.puter.com/drivers/call`.  
No API key is required. The backend sends requests to this endpoint and streams the response back to the frontend via **Server-Sent Events (SSE)**.

To change the model, edit `MODEL` in `backend/main.py`.

---

## Features

- ✅ Streaming token-by-token responses (SSE)
- ✅ Markdown rendering with syntax highlighting
- ✅ Typing animation (bouncing dots)
- ✅ Blinking cursor during streaming
- ✅ Multi-turn conversation history
- ✅ Auto-resizing textarea
- ✅ Shift+Enter for newlines
- ✅ Error handling
- ✅ Clear conversation

---

## Customization

- **System prompt**: Edit `SYSTEM_MESSAGE` in `frontend/app/page.tsx`
- **Model**: Edit `MODEL` in `backend/main.py`
- **CORS origins**: Edit `allow_origins` in `backend/main.py`
- **Theme colors**: Edit `tailwind.config.js`
