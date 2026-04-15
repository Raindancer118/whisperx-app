"""SQLAlchemy async database models and session factory."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Integer, String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://whisperx:whisperx_dev_pw@localhost:5432/whisperx",
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notify_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status: uploading → queued → processing → done | error
    status: Mapped[str] = mapped_column(String(32), default="uploading", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # File info
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Transcription options
    model: Mapped[str] = mapped_column(String(64), default="large-v3")
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    output_format: Mapped[str] = mapped_column(String(8), default="md")
    diarize: Mapped[bool] = mapped_column(Boolean, default=True)

    # Chunked upload tracking
    total_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    received_chunks: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "model": self.model,
            "language": self.language,
            "output_format": self.output_format,
            "diarize": self.diarize,
            "error_message": self.error_message,
            "total_chunks": self.total_chunks,
            "received_chunks": self.received_chunks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
