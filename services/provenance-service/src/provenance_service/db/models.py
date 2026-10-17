"""SQLAlchemy ORM models for provenance-service."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative model."""


class Artifact(Base):
    """Registered artifact entity with immutable checksum and storage URI."""

    __tablename__ = "artifacts"
    __table_args__ = (
        Index("ix_artifacts_project_id", "project_id"),
        Index("ix_artifacts_org_id", "org_id"),
        Index("ix_artifacts_sha256", "sha256"),
        {"schema": "provenance"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_by_service: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    manifests: Mapped[list[ManifestRecord]] = relationship(
        "ManifestRecord",
        back_populates="artifact",
        cascade="all, delete-orphan",
    )


class LineageEdge(Base):
    """Directed edge in the provenance graph from parent to child."""

    __tablename__ = "lineage_edges"
    __table_args__ = (
        UniqueConstraint("child_artifact_id", "parent_artifact_id", "relation"),
        Index("ix_lineage_child", "child_artifact_id"),
        Index("ix_lineage_parent", "parent_artifact_id"),
        {"schema": "provenance"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    child_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provenance.artifacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provenance.artifacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation: Mapped[str] = mapped_column(String(64), nullable=False, default="derived_from")
    params_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ManifestRecord(Base):
    """Cryptographic manifest record associated with an artifact."""

    __tablename__ = "manifests"
    __table_args__ = (
        Index("ix_manifests_artifact_id", "artifact_id"),
        {"schema": "provenance"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provenance.artifacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    manifest_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    signature: Mapped[str | None] = mapped_column(String(512), nullable=True)
    key_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    artifact: Mapped[Artifact] = relationship("Artifact", back_populates="manifests")
