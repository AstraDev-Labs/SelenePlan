"""Pure-function orchestrator state machine for SelenePlan runs.

Per services/project-service/SPEC.md:
- Run states: queued -> running -> succeeded | failed | canceled.
- Steps: terrain, hazard, illumination, comms (parallel), then plan.
- Pure function: transition(state, event) -> (new_state, list[Command]).
- Idempotent deduplication by event_id.
- Resumable after process restart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELED = "canceled"


ANALYSIS_STEPS = ("terrain", "hazard", "illumination", "comms")
ALL_STEPS = ANALYSIS_STEPS + ("plan",)
DEFAULT_MAX_RETRIES = 3


@dataclass(frozen=True)
class StepState:
    name: str
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    product_id: str | None = None
    product_sha256: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class RunState:
    run_id: str
    org_id: str
    project_id: str
    scenario_id: str
    aoi_id: str
    status: RunStatus = RunStatus.QUEUED
    steps: dict[str, StepState] = field(
        default_factory=lambda: {name: StepState(name=name) for name in ALL_STEPS}
    )
    processed_event_ids: frozenset[str] = field(default_factory=frozenset)
    plan_id: str | None = None
    error: str | None = None


# --- Commands (Side effects to execute) ---


@dataclass(frozen=True)
class Command:
    pass


@dataclass(frozen=True)
class EmitEventCommand(Command):
    event_type: str
    topic: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ScheduleTimeoutCommand(Command):
    step_name: str
    timeout_seconds: int


@dataclass(frozen=True)
class AuditEventCommand(Command):
    action: str
    details: dict[str, Any]


# --- Events (Inputs to state machine) ---


@dataclass(frozen=True)
class RunEvent:
    event_id: str


@dataclass(frozen=True)
class StartRunEvent(RunEvent):
    run_id: str


@dataclass(frozen=True)
class StepCompletedEvent(RunEvent):
    step_name: str
    product_id: str
    product_sha256: str | None = None


@dataclass(frozen=True)
class StepFailedEvent(RunEvent):
    step_name: str
    error: str
    retryable: bool = True


@dataclass(frozen=True)
class StepTimeoutEvent(RunEvent):
    step_name: str


@dataclass(frozen=True)
class CancelRunEvent(RunEvent):
    reason: str = "User requested cancellation"


def transition(
    state: RunState,
    event: RunEvent,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> tuple[RunState, list[Command]]:
    """Pure-function transition for the run orchestration state machine.

    Given a current RunState and an incoming RunEvent, computes the next RunState
    and a list of side-effect Commands to execute (outbox events, audit records, timers).
    """
    # 1. Idempotency Check: deduplicate processed events
    if event.event_id in state.processed_event_ids:
        return state, []

    # Update processed events set
    new_processed = state.processed_event_ids | {event.event_id}

    # 2. Terminal state guard
    if state.status in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED):
        # Already finished, ignore subsequent events
        new_state = RunState(
            run_id=state.run_id,
            org_id=state.org_id,
            project_id=state.project_id,
            scenario_id=state.scenario_id,
            aoi_id=state.aoi_id,
            status=state.status,
            steps=state.steps,
            processed_event_ids=new_processed,
            plan_id=state.plan_id,
            error=state.error,
        )
        return new_state, []

    commands: list[Command] = []

    # 3. Handle StartRunEvent
    if isinstance(event, StartRunEvent):
        new_steps = dict(state.steps)
        for name in ANALYSIS_STEPS:
            curr = new_steps[name]
            new_steps[name] = StepState(
                name=name,
                status=StepStatus.RUNNING,
                attempts=curr.attempts + 1,
            )
            commands.append(
                EmitEventCommand(
                    event_type=f"{name}.requested",
                    topic=f"selene.analysis.{name}",
                    payload={
                        "run_id": state.run_id,
                        "org_id": state.org_id,
                        "project_id": state.project_id,
                        "aoi_id": state.aoi_id,
                        "scenario_id": state.scenario_id,
                        "step": name,
                        "attempt": 1,
                    },
                )
            )

        commands.append(
            AuditEventCommand(
                action="run.started",
                details={"run_id": state.run_id, "aoi_id": state.aoi_id},
            )
        )

        new_state = RunState(
            run_id=state.run_id,
            org_id=state.org_id,
            project_id=state.project_id,
            scenario_id=state.scenario_id,
            aoi_id=state.aoi_id,
            status=RunStatus.RUNNING,
            steps=new_steps,
            processed_event_ids=new_processed,
            plan_id=state.plan_id,
            error=None,
        )
        return new_state, commands

    # 4. Handle StepCompletedEvent
    if isinstance(event, StepCompletedEvent):
        step_name = event.step_name
        if step_name not in state.steps:
            return state, []

        curr_step = state.steps[step_name]
        if curr_step.status == StepStatus.SUCCEEDED:
            # Already succeeded
            return state, []

        new_steps = dict(state.steps)
        new_steps[step_name] = StepState(
            name=step_name,
            status=StepStatus.SUCCEEDED,
            attempts=curr_step.attempts,
            product_id=event.product_id,
            product_sha256=event.product_sha256,
        )

        commands.append(
            AuditEventCommand(
                action=f"step.completed.{step_name}",
                details={"run_id": state.run_id, "product_id": event.product_id},
            )
        )

        # Check Join Barrier for analysis steps
        if step_name in ANALYSIS_STEPS:
            all_analysis_done = all(
                new_steps[name].status == StepStatus.SUCCEEDED for name in ANALYSIS_STEPS
            )
            if all_analysis_done and new_steps["plan"].status == StepStatus.PENDING:
                # Dispatch Plan Step
                new_steps["plan"] = StepState(
                    name="plan",
                    status=StepStatus.RUNNING,
                    attempts=1,
                )
                product_refs = {name: new_steps[name].product_id for name in ANALYSIS_STEPS}
                commands.append(
                    EmitEventCommand(
                        event_type="plan.requested",
                        topic="selene.planning",
                        payload={
                            "run_id": state.run_id,
                            "org_id": state.org_id,
                            "project_id": state.project_id,
                            "aoi_id": state.aoi_id,
                            "scenario_id": state.scenario_id,
                            "inputs": product_refs,
                        },
                    )
                )

            new_state = RunState(
                run_id=state.run_id,
                org_id=state.org_id,
                project_id=state.project_id,
                scenario_id=state.scenario_id,
                aoi_id=state.aoi_id,
                status=RunStatus.RUNNING,
                steps=new_steps,
                processed_event_ids=new_processed,
                plan_id=state.plan_id,
                error=None,
            )
            return new_state, commands

        elif step_name == "plan":
            # Entire pipeline succeeded!
            plan_id = event.product_id
            commands.append(
                EmitEventCommand(
                    event_type="run.succeeded",
                    topic="selene.runs",
                    payload={"run_id": state.run_id, "plan_id": plan_id},
                )
            )
            commands.append(
                AuditEventCommand(
                    action="run.succeeded",
                    details={"run_id": state.run_id, "plan_id": plan_id},
                )
            )
            new_state = RunState(
                run_id=state.run_id,
                org_id=state.org_id,
                project_id=state.project_id,
                scenario_id=state.scenario_id,
                aoi_id=state.aoi_id,
                status=RunStatus.SUCCEEDED,
                steps=new_steps,
                processed_event_ids=new_processed,
                plan_id=plan_id,
                error=None,
            )
            return new_state, commands

    # 5. Handle StepFailedEvent or StepTimeoutEvent
    if isinstance(event, (StepFailedEvent, StepTimeoutEvent)):
        step_name = event.step_name
        if step_name not in state.steps:
            return state, []

        curr_step = state.steps[step_name]
        error_msg = event.error if isinstance(event, StepFailedEvent) else "Step timed out"
        retryable = event.retryable if isinstance(event, StepFailedEvent) else True

        new_steps = dict(state.steps)

        # Retry logic: up to max_retries
        if retryable and curr_step.attempts < max_retries:
            next_attempt = curr_step.attempts + 1
            new_steps[step_name] = StepState(
                name=step_name,
                status=StepStatus.RETRYING,
                attempts=next_attempt,
                error=error_msg,
            )
            commands.append(
                EmitEventCommand(
                    event_type=f"{step_name}.requested",
                    topic=f"selene.analysis.{step_name}"
                    if step_name in ANALYSIS_STEPS
                    else "selene.planning",
                    payload={
                        "run_id": state.run_id,
                        "org_id": state.org_id,
                        "project_id": state.project_id,
                        "step": step_name,
                        "attempt": next_attempt,
                    },
                )
            )
            commands.append(
                AuditEventCommand(
                    action=f"step.retrying.{step_name}",
                    details={"run_id": state.run_id, "attempt": next_attempt, "error": error_msg},
                )
            )
            new_state = RunState(
                run_id=state.run_id,
                org_id=state.org_id,
                project_id=state.project_id,
                scenario_id=state.scenario_id,
                aoi_id=state.aoi_id,
                status=RunStatus.RUNNING,
                steps=new_steps,
                processed_event_ids=new_processed,
                plan_id=state.plan_id,
                error=None,
            )
            return new_state, commands
        else:
            # Exceeded retries or non-retryable: Run Fails
            new_steps[step_name] = StepState(
                name=step_name,
                status=StepStatus.FAILED,
                attempts=curr_step.attempts,
                error=error_msg,
            )
            partial_products = {
                name: step.product_id
                for name, step in new_steps.items()
                if step.product_id is not None
            }
            commands.append(
                EmitEventCommand(
                    event_type="run.failed",
                    topic="selene.runs",
                    payload={
                        "run_id": state.run_id,
                        "failed_step": step_name,
                        "error": error_msg,
                        "partial_products": partial_products,
                    },
                )
            )
            commands.append(
                AuditEventCommand(
                    action="run.failed",
                    details={"run_id": state.run_id, "failed_step": step_name, "error": error_msg},
                )
            )
            new_state = RunState(
                run_id=state.run_id,
                org_id=state.org_id,
                project_id=state.project_id,
                scenario_id=state.scenario_id,
                aoi_id=state.aoi_id,
                status=RunStatus.FAILED,
                steps=new_steps,
                processed_event_ids=new_processed,
                plan_id=None,
                error=f"Step '{step_name}' failed after {curr_step.attempts} attempts: {error_msg}",
            )
            return new_state, commands

    # 6. Handle CancelRunEvent
    if isinstance(event, CancelRunEvent):
        new_steps = dict(state.steps)
        for name, step in new_steps.items():
            if step.status in (StepStatus.RUNNING, StepStatus.RETRYING):
                new_steps[name] = StepState(
                    name=name,
                    status=StepStatus.CANCELED,
                    attempts=step.attempts,
                    product_id=step.product_id,
                )
                commands.append(
                    EmitEventCommand(
                        event_type=f"{name}.cancel",
                        topic="selene.cancel",
                        payload={"run_id": state.run_id, "step": name},
                    )
                )
            elif step.status == StepStatus.PENDING:
                new_steps[name] = StepState(
                    name=name,
                    status=StepStatus.CANCELED,
                    attempts=step.attempts,
                )

        commands.append(
            AuditEventCommand(
                action="run.canceled",
                details={"run_id": state.run_id, "reason": event.reason},
            )
        )
        new_state = RunState(
            run_id=state.run_id,
            org_id=state.org_id,
            project_id=state.project_id,
            scenario_id=state.scenario_id,
            aoi_id=state.aoi_id,
            status=RunStatus.CANCELED,
            steps=new_steps,
            processed_event_ids=new_processed,
            plan_id=None,
            error=f"Run canceled: {event.reason}",
        )
        return new_state, commands

    return state, []
