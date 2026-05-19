"""
Münazara — FastAPI REST Backend

React frontend'i Python orchestrator ile bağlar.

Endpoints:
  POST /api/start          → Tartışmayı başlat
  POST /api/skip           → Turu atla (Kamil konuşur, Profesör cevaplar)
  POST /api/ask            → Kullanıcı soru sorar
  GET  /api/status/{sid}   → Oturum durumu
  POST /api/summary/{sid}  → Özet üret
  DELETE /api/session/{sid} → Oturumu temizle

Streaming: SSE (Server-Sent Events) ile chunk'lar gönderilir.
Session storage: in-memory dict (üretim için Redis kullanılabilir).
"""

import os
import uuid
import threading
import json
import sys
import queue

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from agents.orchestrator import DebateOrchestrator
from agents.demo_data import DEMO_MESSAGES, DEMO_TOPIC

load_dotenv()

app = FastAPI(title="Münazara API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store: { session_id: DebateOrchestrator }
_sessions: dict[str, DebateOrchestrator] = {}
_sessions_lock = threading.Lock()


# ─── Pydantic Models ───────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    topic: str
    max_rounds: int = 5
    max_user_questions: int = 3


class AskRequest(BaseModel):
    session_id: str
    question: str


class SessionIdRequest(BaseModel):
    session_id: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_session(session_id: str) -> DebateOrchestrator:
    with _sessions_lock:
        orch = _sessions.get(session_id)
    if not orch:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    return orch


def _orch_to_dict(orch: DebateOrchestrator) -> dict:
    return {
        "current_round": orch.current_round,
        "max_rounds": orch.max_rounds,
        "is_started": orch.is_started,
        "is_finished": orch.is_finished,
        "waiting_for_user": orch.waiting_for_user,
        "user_question_count": orch.user_question_count,
        "max_user_questions": orch.max_user_questions,
        "questions_remaining": orch.questions_remaining,
        "can_ask_question": orch.can_ask_question,
        "last_error": orch.last_error,
        "messages": [
            {"role": m.role, "content": m.content}
            for m in orch.messages
        ],
    }


def _stream_generator(gen):
    """Convert a generator of (role, chunk) tuples to SSE format."""
    try:
        for event_type, data in gen:
            payload = json.dumps({"type": event_type, "data": data})
            yield f"data: {payload}\n\n"
    except Exception as e:
        payload = json.dumps({"type": "error", "data": str(e)})
        yield f"data: {payload}\n\n"
    finally:
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/start")
def start_debate(req: StartRequest):
    """
    Yeni bir tartışma başlatır.
    Returns session_id + ilk profesör mesajı (streaming değil, sync).
    """
    session_id = str(uuid.uuid4())
    orch = DebateOrchestrator(
        topic=req.topic,
        max_rounds=req.max_rounds,
        max_user_questions=req.max_user_questions,
    )

    def stream():
        # Use streaming version
        import queue as q
        chunk_queue = q.Queue()
        done_event = threading.Event()

        def run_debate():
            try:
                success = orch.start_debate(
                    on_chunk=lambda role, chunk: chunk_queue.put(("chunk", role, chunk)),
                    on_complete=lambda role, msg: chunk_queue.put(("complete", role, msg)),
                )
                if not success:
                    chunk_queue.put(("error", None, orch.last_error or "Başlatma hatası"))
            except Exception as e:
                chunk_queue.put(("error", None, str(e)))
            finally:
                chunk_queue.put(("done", None, None))

        t = threading.Thread(target=run_debate, daemon=True)
        t.start()

        # Register session before streaming
        with _sessions_lock:
            _sessions[session_id] = orch

        # First send session_id
        yield f"data: {json.dumps({'type': 'session_id', 'data': session_id})}\n\n"

        while True:
            item = chunk_queue.get()
            event_type, role, data = item

            if event_type == "done":
                status = _orch_to_dict(orch)
                yield f"data: {json.dumps({'type': 'status', 'data': status})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            elif event_type == "chunk":
                yield f"data: {json.dumps({'type': 'chunk', 'role': role, 'data': data})}\n\n"
            elif event_type == "complete":
                yield f"data: {json.dumps({'type': 'complete', 'role': role, 'data': data})}\n\n"
            elif event_type == "error":
                yield f"data: {json.dumps({'type': 'error', 'data': data})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/skip")
def skip_turn(req: SessionIdRequest):
    """Turu atla: Kamil sorar, Profesör cevaplar (SSE stream)."""
    orch = _get_session(req.session_id)

    if not orch.waiting_for_user:
        raise HTTPException(status_code=400, detail="Şu an kullanıcı sırası değil.")

    def stream():
        import queue as q
        chunk_queue = q.Queue()

        def run():
            try:
                success = orch.user_skip_turn(
                    on_chunk=lambda role, chunk: chunk_queue.put(("chunk", role, chunk)),
                    on_complete=lambda role, msg: chunk_queue.put(("complete", role, msg)),
                )
                if not success:
                    chunk_queue.put(("error", None, orch.last_error or "Hata"))
            except Exception as e:
                chunk_queue.put(("error", None, str(e)))
            finally:
                chunk_queue.put(("done", None, None))

        threading.Thread(target=run, daemon=True).start()

        while True:
            item = chunk_queue.get()
            event_type, role, data = item
            if event_type == "done":
                status = _orch_to_dict(orch)
                yield f"data: {json.dumps({'type': 'status', 'data': status})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            elif event_type == "chunk":
                yield f"data: {json.dumps({'type': 'chunk', 'role': role, 'data': data})}\n\n"
            elif event_type == "complete":
                yield f"data: {json.dumps({'type': 'complete', 'role': role, 'data': data})}\n\n"
            elif event_type == "error":
                yield f"data: {json.dumps({'type': 'error', 'data': data})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/ask")
def ask_question(req: AskRequest):
    """Kullanıcı soru sorar, Profesör cevaplar (SSE stream)."""
    orch = _get_session(req.session_id)

    if not orch.waiting_for_user:
        raise HTTPException(status_code=400, detail="Şu an kullanıcı sırası değil.")

    if orch.questions_remaining <= 0:
        raise HTTPException(status_code=400, detail="Soru hakkınız bitti.")

    def stream():
        import queue as q
        chunk_queue = q.Queue()

        def run():
            try:
                success = orch.user_ask_question(
                    question=req.question,
                    on_chunk=lambda role, chunk: chunk_queue.put(("chunk", role, chunk)),
                    on_complete=lambda role, msg: chunk_queue.put(("complete", role, msg)),
                )
                if not success:
                    chunk_queue.put(("error", None, orch.last_error or "Hata"))
            except Exception as e:
                chunk_queue.put(("error", None, str(e)))
            finally:
                chunk_queue.put(("done", None, None))

        threading.Thread(target=run, daemon=True).start()

        while True:
            item = chunk_queue.get()
            event_type, role, data = item
            if event_type == "done":
                status = _orch_to_dict(orch)
                yield f"data: {json.dumps({'type': 'status', 'data': status})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            elif event_type == "chunk":
                yield f"data: {json.dumps({'type': 'chunk', 'role': role, 'data': data})}\n\n"
            elif event_type == "complete":
                yield f"data: {json.dumps({'type': 'complete', 'role': role, 'data': data})}\n\n"
            elif event_type == "error":
                yield f"data: {json.dumps({'type': 'error', 'data': data})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/status/{session_id}")
def get_status(session_id: str):
    orch = _get_session(session_id)
    return _orch_to_dict(orch)


@app.post("/api/summary/{session_id}")
def get_summary(session_id: str):
    """Özet üret (SSE stream)."""
    orch = _get_session(session_id)

    if not orch.is_finished:
        raise HTTPException(status_code=400, detail="Tartışma henüz bitmedi.")

    def stream():
        import queue as q
        chunk_queue = q.Queue()

        def run():
            try:
                orch.generate_summary(
                    on_chunk=lambda role, chunk: chunk_queue.put(chunk)
                )
            except Exception as e:
                chunk_queue.put(f"HATA: {e}")
            finally:
                chunk_queue.put(None)  # sentinel

        threading.Thread(target=run, daemon=True).start()

        while True:
            chunk = chunk_queue.get()
            if chunk is None:
                yield f"data: {json.dumps({'type': 'summary_complete', 'data': orch.summary or ''})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            else:
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str):
    with _sessions_lock:
        _sessions.pop(session_id, None)
    return {"deleted": session_id}


@app.get("/api/demo")
def get_demo():
    """Demo verisi döner (API key gerektirmez)."""
    return {
        "topic": DEMO_TOPIC,
        "messages": [{"role": m["role"], "content": m["content"]} for m in DEMO_MESSAGES],
    }


FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/")
    def serve_frontend():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
