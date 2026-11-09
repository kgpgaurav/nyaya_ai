import asyncio
import hashlib
import json
import secrets
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from . import corpus
from .config import Settings, get_settings
from .db import Case, Document, Fact, LLMCall, Message, TimelineEvent, make_engine, make_sessionmaker
from .domains import DOMAIN_FIELDS, missing_fields, spec
from .drafts import to_docx
from .embeddings import build_embedder
from .graph.build import build_graph, current_state, pending_interrupt, resume, run_turn
from .graph.state import Ctx
from .llm import LLMError, Recorder, build_llm
from .stt import STTError, build_stt
from .texts import t

ROOT = Path(__file__).parent
COOKIE = "nyaya_case"
MODES = ("auto", "build_case", "explain", "draft", "practice", "notice")
LANG_PREFS = ("auto", "en", "hi", "hinglish")


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    mode: str = "auto"
    language: str = "auto"


class ConfirmIn(BaseModel):
    confirmed: bool
    edits: dict[str, str] = Field(default_factory=dict)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_app(settings: Settings | None = None, llm=None, stt=None, today: Callable[[], date] | None = None) -> FastAPI:
    settings = settings or get_settings()
    locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(settings.database_url)
        app.state.sessions = make_sessionmaker(engine)
        pool = AsyncConnectionPool(
            settings.psycopg_url,
            open=False,
            max_size=5,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        await pool.open()
        saver = AsyncPostgresSaver(pool)
        await saver.setup()
        app.state.saver = saver
        app.state.graph = build_graph(saver)
        app.state.llm, app.state.llm_error = llm, ""
        if app.state.llm is None:
            try:
                app.state.llm = build_llm(settings)
            except Exception as exc:
                app.state.llm_error = str(exc)
        app.state.stt = stt
        if app.state.stt is None:
            try:
                app.state.stt = build_stt(settings)
            except Exception:
                app.state.stt = None
        app.state.embedder = build_embedder(settings)
        app.state.today = today or date.today
        yield
        await pool.close()
        await engine.dispose()

    app = FastAPI(title="Nyaya", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")

    @app.middleware("http")
    async def guard_requests(request: Request, call_next):
        if request.method in ("POST", "DELETE", "PUT", "PATCH"):
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return Response("Cross-origin request rejected", status_code=403)
            if request.headers.get("x-nyaya-client") != "web":
                return Response("Client header required", status_code=403)
            limit = settings.max_audio_bytes + 50_000 if request.url.path.endswith("/voice") else 20_000
            try:
                if int(request.headers.get("content-length", "0")) > limit:
                    return Response("Request too large", status_code=413)
            except ValueError:
                return Response("Invalid content length", status_code=400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "media-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["Permissions-Policy"] = "microphone=(self)"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    async def db():
        async with app.state.sessions() as session:
            yield session

    async def load_case(request: Request, session) -> Case:
        token = request.cookies.get(COOKIE, "")
        if not token:
            raise HTTPException(401, "No active case. Start a new one.")
        case = (await session.execute(select(Case).where(Case.token_hash == token_hash(token)))).scalar_one_or_none()
        if case is None:
            raise HTTPException(401, "Case not found or expired. Start a new one.")
        if case.created_at < datetime.now(timezone.utc) - timedelta(hours=settings.session_ttl_hours):
            await drop_case(session, case)
            raise HTTPException(401, "Case expired. Start a new one.")
        return case

    async def drop_case(session, case: Case) -> None:
        await app.state.saver.adelete_thread(str(case.id))
        await session.delete(case)
        await session.commit()

    async def purge_expired(session) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.session_ttl_hours)
        old = (await session.execute(select(Case).where(Case.created_at < cutoff).limit(50))).scalars().all()
        for case in old:
            await app.state.saver.adelete_thread(str(case.id))
            await session.delete(case)
        if old:
            await session.commit()

    async def check_budget(session, case: Case) -> None:
        if case.calls >= settings.max_calls_per_case:
            raise HTTPException(429, "This case has reached its usage limit. Start a new case.")
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_calls = (await session.execute(select(func.count(LLMCall.id)).where(LLMCall.created_at >= start))).scalar_one()
        if today_calls >= settings.max_calls_per_day:
            raise HTTPException(429, "Daily usage limit reached. Please try again tomorrow.")

    def ctx() -> Ctx:
        return Ctx(llm=app.state.llm, sessions=app.state.sessions, recorder=Recorder(), today=app.state.today(), embedder=app.state.embedder)

    async def log_calls(session, case: Case, recorder: Recorder) -> None:
        for c in recorder.calls:
            session.add(LLMCall(case_id=case.id, node=c.node, provider=c.provider, model=c.model, input_tokens=c.input_tokens,
                                output_tokens=c.output_tokens, latency_ms=c.latency_ms, ok=c.ok, error=c.error))
        case.calls += len(recorder.calls)
        await session.commit()

    async def sync(session, case: Case, state: dict, pending, user_text: str | None, via: str, mode: str) -> None:
        if user_text is not None:
            session.add(Message(case_id=case.id, role="user", mode=mode, content=user_text, meta={"via": via}))
        else:
            session.add(Message(case_id=case.id, role="action", mode="draft", content="confirm", meta={}))
        if pending is not None:
            session.add(Message(case_id=case.id, role="assistant", mode="draft", content=pending.get("prompt", ""),
                                meta={"pending": pending}))
        else:
            session.add(Message(case_id=case.id, role="assistant", mode=state.get("mode", ""), content=state.get("reply", ""),
                                meta={"blocks": state.get("blocks", {}), "citations": state.get("citations", []),
                                      "dropped": len(state.get("dropped") or []),
                                      "risks": (state.get("risks") or []) + (state.get("soft_risks") or [])}))
        await session.execute(delete(Fact).where(Fact.case_id == case.id))
        for name, f in (state.get("facts") or {}).items():
            session.add(Fact(case_id=case.id, field=name, value=f["value"], quote=f["quote"], turn=f["turn"],
                             confirmed=f.get("confirmed", False)))
        await session.execute(delete(TimelineEvent).where(TimelineEvent.case_id == case.id))
        for e in state.get("events") or []:
            session.add(TimelineEvent(case_id=case.id, when_text=e["when"], what=e["what"], quote=e["quote"], turn=e["turn"]))
        case.domain = state.get("domain", case.domain)
        case.language = state.get("language", case.language)
        case.updated_at = datetime.now(timezone.utc)
        await session.commit()

    async def view(session, case: Case) -> dict:
        graph = app.state.graph
        state = await current_state(graph, str(case.id))
        pending = await pending_interrupt(graph, str(case.id))
        domain = state.get("domain", case.domain)
        lang = state.get("language", case.language)
        facts = []
        for f in DOMAIN_FIELDS.get(domain, []):
            if f.name in (state.get("facts") or {}):
                v = state["facts"][f.name]
                facts.append({"field": f.name, "label": f.label[lang], "value": v["value"], "quote": v["quote"],
                              "confirmed": v.get("confirmed", False), "edited": v.get("edited", False)})
        missing = [spec(domain, m).label[lang] for m in missing_fields(domain, state.get("facts") or {})] if domain in DOMAIN_FIELDS else []
        messages = (await session.execute(select(Message).where(Message.case_id == case.id).order_by(Message.id))).scalars().all()
        documents = (await session.execute(select(Document).where(Document.case_id == case.id).order_by(Document.id))).scalars().all()
        return {
            "domain": domain,
            "language": lang,
            "facts": facts,
            "missing": missing,
            "events": state.get("events") or [],
            "notice": state.get("notice") or None,
            "pending": pending,
            "messages": [{"role": m.role, "mode": m.mode, "content": m.content, "meta": m.meta} for m in messages if m.role != "action"],
            "documents": [{"id": d.id, "kind": d.kind, "language": d.language, "created_at": d.created_at.isoformat()} for d in documents],
            "welcome": t("welcome", lang if lang in ("en", "hi", "hinglish") else "en"),
            "usage": {"calls": case.calls, "limit": settings.max_calls_per_case},
        }

    def require_llm():
        if app.state.llm is None:
            raise HTTPException(503, f"Model not configured: {app.state.llm_error or 'set LLM_PROVIDER and its API key'}")

    async def handle_turn(session, case: Case, text: str, mode: str, language: str, via: str) -> dict:
        require_llm()
        if mode not in MODES or language not in LANG_PREFS:
            raise HTTPException(422, "Unknown mode or language")
        text = text.strip()
        if not text:
            raise HTTPException(422, "Please type or say something.")
        if len(text) > settings.max_message_chars:
            raise HTTPException(422, "Message too long.")
        await check_budget(session, case)
        c = ctx()
        async with locks[str(case.id)]:
            try:
                result = await run_turn(app.state.graph, c, str(case.id), text, mode, language)
            except LLMError:
                await log_calls(session, case, c.recorder)
                raise HTTPException(502, "The model could not answer just now. Your case was not changed. Please try again.")
            await log_calls(session, case, c.recorder)
            await sync(session, case, result.state, result.pending, text, via, mode)
        return {"case": await view(session, case), "transcript": text if via == "voice" else None}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/config")
    async def config():
        return {
            "llm_provider": settings.llm_provider,
            "model": settings.resolved_model,
            "llm_ready": app.state.llm is not None,
            "llm_error": app.state.llm_error,
            "voice_ready": app.state.stt is not None,
            "embeddings": settings.embedding_provider,
            "retention_hours": settings.session_ttl_hours,
        }

    @app.get("/api/sources")
    async def sources(session=Depends(db)):
        return await corpus.all_cards(session)

    @app.post("/api/case")
    async def new_case(request: Request, response: Response, session=Depends(db)):
        await purge_expired(session)
        old = request.cookies.get(COOKIE)
        if old:
            existing = (await session.execute(select(Case).where(Case.token_hash == token_hash(old)))).scalar_one_or_none()
            if existing:
                await drop_case(session, existing)
        token = secrets.token_urlsafe(32)
        case = Case(id=uuid.uuid4(), token_hash=token_hash(token))
        session.add(case)
        await session.commit()
        response.set_cookie(COOKIE, token, httponly=True, secure=settings.cookie_secure, samesite="strict",
                            max_age=settings.session_ttl_hours * 3600)
        return {"case": await view(session, case)}

    @app.get("/api/case")
    async def get_case(request: Request, session=Depends(db)):
        return {"case": await view(session, await load_case(request, session))}

    @app.post("/api/case/messages")
    async def chat(body: ChatIn, request: Request, session=Depends(db)):
        case = await load_case(request, session)
        return await handle_turn(session, case, body.text, body.mode, body.language, "text")

    @app.post("/api/case/voice")
    async def voice(request: Request, audio: UploadFile = File(...), mode: str = Form("auto"), language: str = Form("auto"),
                    session=Depends(db)):
        case = await load_case(request, session)
        if app.state.stt is None:
            raise HTTPException(503, "Voice input is not configured. Set STT_PROVIDER and its API key.")
        data = await audio.read()
        if not data or len(data) > settings.max_audio_bytes:
            raise HTTPException(413, "Recording is empty or too long.")
        try:
            text = await app.state.stt.transcribe(data, audio.filename or "voice.webm", language if language in ("en", "hi") else None)
        except STTError:
            raise HTTPException(502, "Could not transcribe the recording. Please try again or type instead.")
        if not text:
            raise HTTPException(422, "I couldn't hear anything in that recording.")
        return await handle_turn(session, case, text, mode, language, "voice")

    @app.post("/api/case/confirm")
    async def confirm(body: ConfirmIn, request: Request, session=Depends(db)):
        case = await load_case(request, session)
        require_llm()
        if await pending_interrupt(app.state.graph, str(case.id)) is None:
            raise HTTPException(409, "Nothing is waiting for confirmation.")
        await check_budget(session, case)
        c = ctx()
        async with locks[str(case.id)]:
            try:
                result = await resume(app.state.graph, c, str(case.id), body.model_dump())
            except LLMError:
                await log_calls(session, case, c.recorder)
                raise HTTPException(502, "The model could not write the draft just now. Please try again.")
            await log_calls(session, case, c.recorder)
            await sync(session, case, result.state, result.pending, None, "confirm", "draft")
        return {"case": await view(session, case)}

    @app.get("/api/case/documents/{doc_id}.{fmt}")
    async def download(doc_id: int, fmt: str, request: Request, session=Depends(db)):
        case = await load_case(request, session)
        doc = (await session.execute(select(Document).where(Document.id == doc_id, Document.case_id == case.id))).scalar_one_or_none()
        if doc is None:
            raise HTTPException(404, "Document not found")
        name = f"{doc.kind}_{doc.id}"
        if fmt == "txt":
            return Response(doc.content.encode("utf-8"), media_type="text/plain; charset=utf-8",
                            headers={"Content-Disposition": f'attachment; filename="{name}.txt"'})
        if fmt == "docx":
            return Response(to_docx(doc.content),
                            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            headers={"Content-Disposition": f'attachment; filename="{name}.docx"'})
        raise HTTPException(404, "Unknown format")

    @app.get("/api/case/export")
    async def export(request: Request, session=Depends(db)):
        case = await load_case(request, session)
        data = await view(session, case)
        return Response(json.dumps(data, ensure_ascii=False, indent=2, default=str), media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="case.json"'})

    @app.delete("/api/case")
    async def delete_case(request: Request, response: Response, session=Depends(db)):
        token = request.cookies.get(COOKIE, "")
        if token:
            case = (await session.execute(select(Case).where(Case.token_hash == token_hash(token)))).scalar_one_or_none()
            if case:
                await drop_case(session, case)
        response.delete_cookie(COOKIE)
        return {"deleted": True}

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(ROOT / "static" / "favicon.svg", media_type="image/svg+xml")

    @app.get("/")
    async def index():
        return FileResponse(ROOT / "static" / "index.html")

    return app


app = create_app()
