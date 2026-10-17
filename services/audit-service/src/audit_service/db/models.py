"""SQLAlchemy ORM models for audit log and anchors."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AuditLog(Base):
    """Immutable, append-only audit log table."""

    __tablename__ = "audit_log"
    __table_args__ = (
        UniqueConstraint("id", name="uq_audit_log_id"),
        {"schema": "audit"},
    )

    seq: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        insert_default=None,  # Generated always by DB
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ts: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    actor_sub: Mapped[str] = mapped_column(String, nullable=False)
    actor_type: Mapped[str] = mapped_column(String, nullable=False)  # 'user' | 'service'
    action: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[str] = mapped_column(String, nullable=False)
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_service: Mapped[str] = mapped_column(String, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String, nullable=True)
    prev_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    row_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)


class Anchor(Base):
    """Daily audit log hash chain anchor."""

    __tablename__ = "anchors"
    __table_args__ = {"schema": "audit"}  # noqa: RUF012

    day: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    last_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    digest: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    anchor_uri: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.UTC),
    )
