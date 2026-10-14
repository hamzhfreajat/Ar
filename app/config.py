"""Settings, read from the environment and from two optional files.

    ~/.kitabcom/azure-speech.env   the Azure Speech key and region (kept outside any repo)
    .env (in this folder)          anything else, e.g. DATABASE_URL; ignored by git

A value already in the environment wins over both files.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent


def _read_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


def _database_url() -> str:
    """Where the data lives, from the first of these that is set:

    1. DATABASE_URL.
    2. DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, as docker-compose.yml sets them.
    3. POSTGRES_PASSWORD alone: the database service of docker-compose.yml, at host "db".
       Some platforms pass only the variables entered in their own settings and drop those
       written in the compose file; the Postgres image then keeps its defaults (user and
       database "postgres"), and so does this.
    4. Otherwise a SQLite file in this folder, for running without Docker.
    """
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    password = os.environ.get("DB_PASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    host = os.environ.get("DB_HOST") or ("db" if password else "")
    if host:
        user = os.environ.get("DB_USER") or os.environ.get("POSTGRES_USER") or "postgres"
        name = os.environ.get("DB_NAME") or os.environ.get("POSTGRES_DB") or user
        port = os.environ.get("DB_PORT", "5432")
        return f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(password or '')}@{host}:{port}/{name}"
    return f"sqlite:///{(ROOT / 'kitabcom.db').as_posix()}"


@dataclass(frozen=True)
class Settings:
    database_url: str
    azure_speech_key: str
    azure_speech_region: str
    # Pronunciation checks a device may ask for in one day
    daily_checks: int
    # Longest recording accepted, in seconds of 16 kHz, 16-bit sound
    max_audio_seconds: int


def load_settings() -> Settings:
    _read_env_file(ROOT / ".env")
    _read_env_file(Path.home() / ".kitabcom" / "azure-speech.env")
    return Settings(
        database_url=_database_url(),
        azure_speech_key=os.environ.get("AZURE_SPEECH_KEY", ""),
        azure_speech_region=os.environ.get("AZURE_SPEECH_REGION", "").lower().replace(" ", ""),
        daily_checks=int(os.environ.get("DAILY_PRONUNCIATION_CHECKS", "60")),
        max_audio_seconds=int(os.environ.get("MAX_AUDIO_SECONDS", "10")),
    )
