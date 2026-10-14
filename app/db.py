"""The database: SQLite in this folder by default, PostgreSQL when DATABASE_URL says so."""
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Device(Base):
    """A copy of the app on one phone. It needs no sign-in: the free lessons work as a guest."""
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Only a hash of the token is kept: a copy of the database gives no one a working token
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(16), default="")
    app_version: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DailyUsage(Base):
    """How many pronunciation checks a device asked for on a day: they cost money at Azure."""
    __tablename__ = "daily_usage"
    __table_args__ = (UniqueConstraint("device_id", "day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    day: Mapped[date] = mapped_column(Date)
    checks: Mapped[int] = mapped_column(Integer, default=0)


class SceneProgress(Base):
    """How far a device got in one AR scene, and its best result there."""
    __tablename__ = "scene_progress"
    __table_args__ = (UniqueConstraint("device_id", "scene"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    # The scene's id, e.g. "unit1.page1"
    scene: Mapped[str] = mapped_column(String(64))
    completed: Mapped[int] = mapped_column(Integer, default=0)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


def make_session_factory(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
    # Enough while the schema is young; Alembic migrations take over once there is data to keep
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
