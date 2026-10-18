"""FastAPI routes for project-service: projects, runs, rover profiles, plans, and approvals."""

from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from project_service.domain.models import (
    DecisionType,
    PlanStatus,
    PlanVersion,
    Project,
    RoverProfile,
)
from project_service.orchestrator.state_machine import (
    RunState,
    StartRunEvent,
    transition,
)
from project_service.workflow.engine import (
    WorkflowError,
    record_decision,
    submit_for_review,
)

router = APIRouter(prefix="/v1")

# In-memory stores for runtime state (backed by DB in container deployments)
PROJECT_STORE: dict[str, Project] = {
    "proj-shackleton": Project(
        project_id="proj-shackleton",
        org_id="org-artemis",
        name="Shackleton South Pole Traverse",
        description="Exploration traverse within the Shackleton crater rim AOI",
        members=["user-analyst", "user-lead", "user-approver-1", "user-approver-2"],
    )
}

ROVER_PROFILE_STORE: dict[str, RoverProfile] = {
    "profile-vipr": RoverProfile(
        profile_id="profile-vipr",
        project_id="proj-shackleton",
        version=1,
        name="VIPER Polar Standard",
        battery_capacity_wh=500.0,
        min_survival_wh=100.0,
        power_drive_w=80.0,
        power_wait_w=10.0,
        power_idle_w=5.0,
        power_comms_w=25.0,
        solar_area_m2=0.5,
        solar_efficiency=0.28,
        speed_mps=0.1,
        max_slope_deg=15.0,
    )
}

RUN_STORE: dict[str, RunState] = {}
PLAN_STORE: dict[str, dict[str, Any]] = {}
PLAN_VERSION_STORE: dict[str, PlanVersion] = {}
IDEMPOTENCY_STORE: dict[str, Any] = {}


# --- Request/Response Models ---


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    org_id: str = "org-artemis"
    members: list[str] = Field(default_factory=list)


class CreateRoverProfileRequest(BaseModel):
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


class StartRunRequest(BaseModel):
    scenario_id: str
    aoi_id: str


class CreatePlanRequest(BaseModel):
    name: str
    author_id: str
    payload: dict[str, Any]


class SubmitPlanRequest(BaseModel):
    user_id: str
    user_role: str = "analyst"


class DecisionRequest(BaseModel):
    user_id: str
    user_role: str = "approver"
    decision: DecisionType
    mfa_verified: bool = True
    comment: str | None = None


# --- Project Routes ---


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(payload: CreateProjectRequest) -> dict[str, Any]:
    project_id = f"proj-{uuid.uuid4().hex[:8]}"
    proj = Project(
        project_id=project_id,
        org_id=payload.org_id,
        name=payload.name,
        description=payload.description,
        members=payload.members,
    )
    PROJECT_STORE[project_id] = proj
    return vars(proj)


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict[str, Any]:
    if project_id not in PROJECT_STORE:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return vars(PROJECT_STORE[project_id])


# --- Rover Profile Routes ---


@router.post("/projects/{project_id}/rover-profiles", status_code=status.HTTP_201_CREATED)
async def create_rover_profile(
    project_id: str, payload: CreateRoverProfileRequest
) -> dict[str, Any]:
    if project_id not in PROJECT_STORE:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    profile_id = f"profile-{uuid.uuid4().hex[:8]}"
    prof = RoverProfile(
        profile_id=profile_id,
        project_id=project_id,
        version=1,
        name=payload.name,
        battery_capacity_wh=payload.battery_capacity_wh,
        min_survival_wh=payload.min_survival_wh,
        power_drive_w=payload.power_drive_w,
        power_wait_w=payload.power_wait_w,
        power_idle_w=payload.power_idle_w,
        power_comms_w=payload.power_comms_w,
        solar_area_m2=payload.solar_area_m2,
        solar_efficiency=payload.solar_efficiency,
        speed_mps=payload.speed_mps,
        max_slope_deg=payload.max_slope_deg,
    )
    ROVER_PROFILE_STORE[profile_id] = prof
    return vars(prof)


@router.get("/projects/{project_id}/rover-profiles/{profile_id}")
async def get_rover_profile(project_id: str, profile_id: str) -> dict[str, Any]:
    if profile_id not in ROVER_PROFILE_STORE:
        raise HTTPException(status_code=404, detail=f"Rover profile {profile_id} not found")
    return vars(ROVER_PROFILE_STORE[profile_id])


# --- Run Orchestrator Routes ---


@router.post("/projects/{project_id}/runs", status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    project_id: str,
    payload: StartRunRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if project_id not in PROJECT_STORE:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Idempotency check
    if idempotency_key and idempotency_key in IDEMPOTENCY_STORE:
        return cast(dict[str, Any], IDEMPOTENCY_STORE[idempotency_key])

    run_id = f"run-{uuid.uuid4().hex[:8]}"
    initial_state = RunState(
        run_id=run_id,
        org_id=PROJECT_STORE[project_id].org_id,
        project_id=project_id,
        scenario_id=payload.scenario_id,
        aoi_id=payload.aoi_id,
    )

    # Trigger start run in pure state machine
    new_state, _commands = transition(
        initial_state,
        StartRunEvent(event_id=f"evt-{uuid.uuid4().hex[:8]}", run_id=run_id),
    )
    RUN_STORE[run_id] = new_state

    response = {
        "run_id": run_id,
        "status": new_state.status.value,
        "project_id": project_id,
        "scenario_id": payload.scenario_id,
        "steps": {k: v.status.value for k, v in new_state.steps.items()},
    }

    if idempotency_key:
        IDEMPOTENCY_STORE[idempotency_key] = response

    return response


@router.get("/projects/{project_id}/runs/{run_id}")
async def get_run(project_id: str, run_id: str) -> dict[str, Any]:
    if run_id not in RUN_STORE:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    state = RUN_STORE[run_id]
    if state.project_id != project_id:
        raise HTTPException(status_code=403, detail="Cross-project access forbidden")

    return {
        "run_id": state.run_id,
        "project_id": state.project_id,
        "status": state.status.value,
        "steps": {
            name: {
                "status": step.status.value,
                "attempts": step.attempts,
                "product_id": step.product_id,
                "error": step.error,
            }
            for name, step in state.steps.items()
        },
        "plan_id": state.plan_id,
        "error": state.error,
    }


# --- Plan & Approval Lifecycle Routes ---


@router.post("/projects/{project_id}/plans", status_code=status.HTTP_201_CREATED)
async def create_plan(project_id: str, payload: CreatePlanRequest) -> dict[str, Any]:
    if project_id not in PROJECT_STORE:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    plan_id = f"plan-{uuid.uuid4().hex[:8]}"
    version_id = f"pv-{uuid.uuid4().hex[:8]}"

    plan_version = PlanVersion(
        version_id=version_id,
        plan_id=plan_id,
        version_number=1,
        author_id=payload.author_id,
        status=PlanStatus.DRAFT,
        payload=payload.payload,
    )

    PLAN_VERSION_STORE[version_id] = plan_version
    PLAN_STORE[plan_id] = {
        "plan_id": plan_id,
        "project_id": project_id,
        "name": payload.name,
        "current_version_id": version_id,
        "versions": [version_id],
    }

    return {
        "plan_id": plan_id,
        "version_id": version_id,
        "version_number": 1,
        "status": plan_version.status.value,
        "author_id": payload.author_id,
    }


@router.get("/projects/{project_id}/plans/{plan_id}")
async def get_plan(project_id: str, plan_id: str) -> dict[str, Any]:
    if plan_id not in PLAN_STORE:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    plan_meta = PLAN_STORE[plan_id]
    if plan_meta["project_id"] != project_id:
        raise HTTPException(status_code=403, detail="Cross-project access forbidden")

    curr_version = PLAN_VERSION_STORE[plan_meta["current_version_id"]]
    return {
        "plan_id": plan_id,
        "name": plan_meta["name"],
        "project_id": project_id,
        "current_version": {
            "version_id": curr_version.version_id,
            "version_number": curr_version.version_number,
            "status": curr_version.status.value,
            "author_id": curr_version.author_id,
            "payload_sha256": curr_version.payload_sha256,
            "decisions": [
                {
                    "user_id": d.user_id,
                    "decision": d.decision.value,
                    "comment": d.comment,
                    "timestamp": d.timestamp.isoformat(),
                }
                for d in curr_version.decisions
            ],
            "signature": curr_version.signature,
        },
    }


@router.post("/plans/{plan_id}/versions/{version_id}/submit")
async def submit_plan(plan_id: str, version_id: str, payload: SubmitPlanRequest) -> dict[str, Any]:
    if plan_id not in PLAN_STORE or version_id not in PLAN_VERSION_STORE:
        raise HTTPException(status_code=404, detail="Plan or version not found")

    project_id = PLAN_STORE[plan_id]["project_id"]
    members = PROJECT_STORE[project_id].members
    plan_version = PLAN_VERSION_STORE[version_id]

    try:
        updated = submit_for_review(
            plan=plan_version,
            user_id=payload.user_id,
            user_role=payload.user_role,
            project_members=members,
        )
    except WorkflowError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "plan_id": plan_id,
        "version_id": version_id,
        "status": updated.status.value,
        "payload_sha256": updated.payload_sha256,
    }


@router.post("/plans/{plan_id}/versions/{version_id}/decision")
async def make_decision(
    plan_id: str,
    version_id: str,
    payload: DecisionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if plan_id not in PLAN_STORE or version_id not in PLAN_VERSION_STORE:
        raise HTTPException(status_code=404, detail="Plan or version not found")

    if idempotency_key and idempotency_key in IDEMPOTENCY_STORE:
        return cast(dict[str, Any], IDEMPOTENCY_STORE[idempotency_key])

    plan_version = PLAN_VERSION_STORE[version_id]

    try:
        updated, decision_record = record_decision(
            plan=plan_version,
            user_id=payload.user_id,
            user_role=payload.user_role,
            decision=payload.decision,
            mfa_verified=payload.mfa_verified,
            comment=payload.comment,
        )
    except WorkflowError as e:
        raise HTTPException(status_code=400, detail=str(e))

    res = {
        "plan_id": plan_id,
        "version_id": version_id,
        "status": updated.status.value,
        "decision": decision_record.decision.value,
        "user_id": decision_record.user_id,
        "comment": decision_record.comment,
    }

    if idempotency_key:
        IDEMPOTENCY_STORE[idempotency_key] = res

    return res
