import struct

import pytest
from fastapi.testclient import TestClient

from app import azure_speech
from app.config import Settings
from app.main import create_app


def wav(seconds: float = 0.5) -> bytes:
    data = b"\0\0" * int(16000 * seconds)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
            + b"data" + struct.pack("<I", len(data)) + data)


@pytest.fixture
def calls():
    return []


@pytest.fixture
def client(tmp_path, calls):
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", azure_speech_key="k",
                        azure_speech_region="swedencentral", daily_checks=2, max_audio_seconds=10)

    def fake_assess(audio, text, key, region):
        calls.append(text)
        return {"ok": True, "score": 90.0, "heard": text}

    return TestClient(create_app(settings, assess=fake_assess))


def token(client) -> dict:
    response = client.post("/v1/devices", json={"platform": "android", "app_version": "0.1"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


def test_health(client):
    assert client.get("/v1/health").json() == {"ok": True, "pronunciation": True}


def test_pronunciation_needs_a_device(client):
    assert client.post("/v1/pronunciation?text=hello", content=wav()).status_code == 401
    assert client.post("/v1/pronunciation?text=hello", content=wav(), headers={"Authorization": "Bearer nope"}).status_code == 401


def test_pronunciation_scores_and_keeps_the_daily_limit(client, calls):
    me = token(client)
    for _ in range(2):
        assert client.post("/v1/pronunciation?text=hello", content=wav(), headers=me).json()["score"] == 90.0
    assert client.post("/v1/pronunciation?text=hello", content=wav(), headers=me).json() == {"ok": False, "reason": "limit"}
    assert calls == ["hello", "hello"]
    # Another device has its own limit
    assert client.post("/v1/pronunciation?text=hi", content=wav(), headers=token(client)).json()["ok"]


def test_pronunciation_refuses_what_is_not_a_short_wav(client):
    me = token(client)
    assert client.post("/v1/pronunciation?text=hello", content=b"not a wav", headers=me).status_code == 400
    assert client.post("/v1/pronunciation?text=hello", content=wav(seconds=12), headers=me).status_code == 400
    assert client.post("/v1/pronunciation?text=", content=wav(), headers=me).status_code == 422


def test_progress_keeps_the_best(client):
    me = token(client)
    client.put("/v1/progress/unit1.page1", json={"completed": True, "stars": 3}, headers=me)
    client.put("/v1/progress/unit1.page1", json={"completed": False, "stars": 1}, headers=me)
    assert client.get("/v1/progress", headers=me).json() == {"scenes": [{"scene": "unit1.page1", "completed": True, "stars": 3}]}
    assert client.get("/v1/progress", headers=token(client)).json() == {"scenes": []}


def phonemes(*scores):
    return {"RecognitionStatus": "Success", "DisplayText": "Hello.", "NBest": [{
        "AccuracyScore": sum(scores) / len(scores), "PronScore": 90.0,
        "Words": [{"Word": "hello", "AccuracyScore": 80.0, "ErrorType": "None",
                   "Phonemes": [{"Phoneme": "x", "AccuracyScore": s} for s in scores]}]}]}


def test_a_badly_missed_sound_caps_the_score():
    # What Azure answered for "yellow" said instead of "hello"
    assert azure_speech.read_result(phonemes(0, 6, 100, 100))["score"] == 50.0
    assert azure_speech.read_result(phonemes(100, 90, 100, 100))["score"] == 97.5
    assert azure_speech.read_result({"RecognitionStatus": "NoMatch"}) == {"ok": False, "reason": "not understood"}


def test_database_settings(monkeypatch):
    from app import config
    for name in ("DATABASE_URL", "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "POSTGRES_PASSWORD", "POSTGRES_USER", "POSTGRES_DB"):
        monkeypatch.delenv(name, raising=False)
    assert config._database_url().startswith("sqlite:///")

    # Only the password reached the container: the Postgres image's defaults
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss")
    assert config._database_url() == "postgresql+psycopg://postgres:p%40ss@db:5432/postgres"

    # Everything docker-compose.yml sets
    for name, value in {"DB_HOST": "db", "DB_USER": "kitabcom", "DB_PASSWORD": "x/y", "DB_NAME": "kitabcom"}.items():
        monkeypatch.setenv(name, value)
    assert config._database_url() == "postgresql+psycopg://kitabcom:x%2Fy@db:5432/kitabcom"

    monkeypatch.setenv("DATABASE_URL", "sqlite:///other.db")
    assert config._database_url() == "sqlite:///other.db"
