"""The book app's server: devices, lesson progress, and pronunciation checks through Azure.

The app never holds the Azure key: it sends the child's recording here, and this server asks
Azure and answers with one score. Recordings are passed on and forgotten; nothing is stored.

Run locally:  .venv/Scripts/python -m uvicorn app.main:app --reload --port 8090
"""
import hashlib
import secrets
from datetime import date
from typing import Annotated, Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import azure_speech
from .config import Settings, load_settings
from .db import DailyUsage, Device, SceneProgress, make_session_factory

MAX_TEXT = 80


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_app(settings: Settings | None = None, assess: Callable[..., dict] | None = None) -> FastAPI:
    """`assess` stands in for Azure in tests."""
    settings = settings or load_settings()
    assess = assess or azure_speech.assess
    session_factory = make_session_factory(settings.database_url)
    app = FastAPI(title="Kitabcom app server", version="0.1.0")

    def session():
        with session_factory() as db:
            yield db

    Db = Annotated[Session, Depends(session)]

    def device(db: Db, authorization: Annotated[str, Header()] = "") -> Device:
        token = authorization.removeprefix("Bearer ").strip()
        found = db.scalar(select(Device).where(Device.token_hash == _hash(token))) if token else None
        if found is None:
            raise HTTPException(401, "unknown device")
        return found

    CurrentDevice = Annotated[Device, Depends(device)]

    @app.get("/v1/health")
    def health():
        return {"ok": True, "pronunciation": bool(settings.azure_speech_key and settings.azure_speech_region)}

    class NewDevice(BaseModel):
        platform: str = Field("", max_length=16)
        app_version: str = Field("", max_length=32)

    @app.post("/v1/devices")
    def register(body: NewDevice, db: Db):
        """A first start of the app: it gets a token to keep and send with every later call."""
        token = secrets.token_urlsafe(32)
        db.add(Device(token_hash=_hash(token), platform=body.platform, app_version=body.app_version))
        db.commit()
        return {"token": token}

    @app.post("/v1/pronunciation")
    async def pronunciation(request: Request, me: CurrentDevice, db: Db,
                            text: Annotated[str, Query(min_length=1, max_length=MAX_TEXT)]):
        """POST the recording as a WAV (16 kHz, 16-bit, one channel); `text` is what was asked for.
        Failures come back as {"ok": false}: the app then carries on without judging."""
        if not (settings.azure_speech_key and settings.azure_speech_region):
            return {"ok": False, "reason": "off"}
        wav = await request.body()
        if not 44 < len(wav) <= 44 + 16000 * 2 * settings.max_audio_seconds or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
            raise HTTPException(400, "expected a short WAV recording")

        today = date.today()
        usage = db.scalar(select(DailyUsage).where(DailyUsage.device_id == me.id, DailyUsage.day == today))
        if usage is None:
            usage = DailyUsage(device_id=me.id, day=today, checks=0)
            db.add(usage)
        if usage.checks >= settings.daily_checks:
            return {"ok": False, "reason": "limit"}
        usage.checks += 1
        db.commit()

        return assess(wav, text.strip(), settings.azure_speech_key, settings.azure_speech_region)

    class Progress(BaseModel):
        completed: bool = False
        stars: int = Field(0, ge=0, le=3)

    @app.put("/v1/progress/{scene}")
    def save_progress(scene: Annotated[str, Path(max_length=64)], body: Progress, me: CurrentDevice, db: Db):
        """Keeps the best: playing a scene again never lowers what was earned."""
        row = db.scalar(select(SceneProgress).where(SceneProgress.device_id == me.id, SceneProgress.scene == scene))
        if row is None:
            row = SceneProgress(device_id=me.id, scene=scene, completed=0, stars=0)
            db.add(row)
        row.completed = max(row.completed, int(body.completed))
        row.stars = max(row.stars, body.stars)
        db.commit()
        return {"scene": scene, "completed": bool(row.completed), "stars": row.stars}

    @app.get("/v1/progress")
    def progress(me: CurrentDevice, db: Db):
        rows = db.scalars(select(SceneProgress).where(SceneProgress.device_id == me.id)).all()
        return {"scenes": [{"scene": r.scene, "completed": bool(r.completed), "stars": r.stars} for r in rows]}

    return app


app = create_app()
