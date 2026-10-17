"""Domain models for organizations, projects, AOIs, rover profiles, runs, plans, and approvals.

Per services/project-service/SPEC.md and docs/04-data-model.md.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class PlanStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SIGNED = "signed"
    SUPERSEDED = "superseded"


class DecisionType(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


@dataclass
class Project:
    project_id: str
    org_id: str
    name: str
    description: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    members: list[str] = field(default_factory=list)


@dataclass
class RoverProfile:
    profile_id: str
    project_id: str
    version: int
    name: str
    battery_capacity_wh: float = 500.0
    min_survival_wh: float = 100.0
    power_drive_w: float = 80.0
    power_wait_w: float = 10.0
    power_idle_w: float = 5.0
    power_comms_w: float = 25.0
    solar_area_m2: float = 0.5
    solar_efficiency: float = 0.28
    speed_mps: float = 0.1
    max_slope_deg: float = 15.0


@dataclass
class ApprovalDecision:
    decision_id: str
    plan_version_id: str
    user_id: str
    decision: DecisionType
    mfa_verified: bool
    comment: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PlanVersion:
    version_id: str
    plan_id: str
    version_number: int
    author_id: str
    status: PlanStatus = PlanStatus.DRAFT
    payload: dict[str, Any] = field(default_factory=dict)
    payload_sha256: str | None = None
    decisions: list[ApprovalDecision] = field(default_factory=list)
    signature: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def compute_hash(self) -> str:
        """Deterministic hash of payload for integrity verification."""
        encoded = json.dumps(self.payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
