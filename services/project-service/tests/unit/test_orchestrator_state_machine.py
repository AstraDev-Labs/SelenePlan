"""Unit tests for the pure-function orchestrator state machine.

Per services/project-service/SPEC.md:
- Acceptance Criterion 3: Survives restart mid-run; completes run exactly once per step.
- Acceptance Criterion 4: Duplicate events do not create duplicate steps or plans.
- Partial results visible on failure.
"""

from project_service.orchestrator.state_machine import (
    ANALYSIS_STEPS,
    CancelRunEvent,
    EmitEventCommand,
    RunState,
    RunStatus,
    StartRunEvent,
    StepCompletedEvent,
    StepFailedEvent,
    StepStatus,
    StepTimeoutEvent,
    transition,
)


def create_initial_state() -> RunState:
    return RunState(
        run_id="run-test-001",
        org_id="org-artemis",
        project_id="proj-shackleton",
        scenario_id="scen-south-pole",
        aoi_id="aoi-shackleton",
    )


def test_full_pipeline_success_join_barrier() -> None:
    state = create_initial_state()

    # 1. Start Run
    state, cmds = transition(state, StartRunEvent(event_id="evt-start", run_id=state.run_id))
    assert state.status == RunStatus.RUNNING
    # Should emit requested events for all 4 parallel analysis steps
    requested_steps = [c.payload["step"] for c in cmds if isinstance(c, EmitEventCommand)]
    assert sorted(requested_steps) == sorted(ANALYSIS_STEPS)
    for name in ANALYSIS_STEPS:
        assert state.steps[name].status == StepStatus.RUNNING

    # 2. Complete 3 of the 4 steps (join barrier not yet reached)
    for name in ["terrain", "hazard", "illumination"]:
        state, cmds = transition(
            state,
            StepCompletedEvent(
                event_id=f"evt-{name}-done",
                step_name=name,
                product_id=f"prod-{name}-123",
            ),
        )
        assert state.steps[name].status == StepStatus.SUCCEEDED
        # Barrier not reached yet -> no plan.requested command
        assert not any(
            isinstance(c, EmitEventCommand) and c.event_type == "plan.requested" for c in cmds
        )

    # Plan step is still PENDING
    assert state.steps["plan"].status == StepStatus.PENDING

    # 3. Complete 4th step ("comms") -> join barrier fulfilled!
    state, cmds = transition(
        state,
        StepCompletedEvent(
            event_id="evt-comms-done",
            step_name="comms",
            product_id="prod-comms-123",
        ),
    )
    assert state.steps["comms"].status == StepStatus.SUCCEEDED
    assert state.steps["plan"].status == StepStatus.RUNNING
    plan_cmds = [
        c for c in cmds if isinstance(c, EmitEventCommand) and c.event_type == "plan.requested"
    ]
    assert len(plan_cmds) == 1
    assert len(plan_cmds[0].payload["inputs"]) == 4

    # 4. Complete plan step
    state, cmds = transition(
        state,
        StepCompletedEvent(
            event_id="evt-plan-done",
            step_name="plan",
            product_id="plan-shackleton-v1",
        ),
    )
    assert state.status == RunStatus.SUCCEEDED
    assert state.plan_id == "plan-shackleton-v1"
    assert any(isinstance(c, EmitEventCommand) and c.event_type == "run.succeeded" for c in cmds)


def test_idempotent_deduplication_of_events() -> None:
    state = create_initial_state()
    state, _ = transition(state, StartRunEvent(event_id="evt-start", run_id=state.run_id))

    complete_evt = StepCompletedEvent(
        event_id="evt-dup-001",
        step_name="terrain",
        product_id="prod-terrain-999",
    )

    # First delivery
    state1, cmds1 = transition(state, complete_evt)
    assert state1.steps["terrain"].status == StepStatus.SUCCEEDED
    assert len(cmds1) > 0

    # Duplicate delivery of identical event_id
    state2, cmds2 = transition(state1, complete_evt)
    assert state2 == state1
    assert len(cmds2) == 0


def test_step_failure_retries_and_terminal_exhaustion() -> None:
    state = create_initial_state()
    state, _ = transition(state, StartRunEvent(event_id="evt-start", run_id=state.run_id))

    # Attempt 1 failed -> triggers attempt 2
    state, cmds1 = transition(
        state,
        StepFailedEvent(
            event_id="evt-fail-1", step_name="hazard", error="OOM killed", retryable=True
        ),
        max_retries=3,
    )
    assert state.status == RunStatus.RUNNING
    assert state.steps["hazard"].status == StepStatus.RETRYING
    assert state.steps["hazard"].attempts == 2
    assert any(isinstance(c, EmitEventCommand) and c.payload.get("attempt") == 2 for c in cmds1)

    # Attempt 2 failed -> triggers attempt 3
    state, _cmds2 = transition(
        state,
        StepFailedEvent(
            event_id="evt-fail-2", step_name="hazard", error="OOM killed again", retryable=True
        ),
        max_retries=3,
    )
    assert state.steps["hazard"].status == StepStatus.RETRYING
    assert state.steps["hazard"].attempts == 3

    # Attempt 3 failed -> max retries reached -> run fails
    state, cmds3 = transition(
        state,
        StepFailedEvent(
            event_id="evt-fail-3", step_name="hazard", error="Third OOM", retryable=True
        ),
        max_retries=3,
    )
    assert state.status == RunStatus.FAILED
    assert state.steps["hazard"].status == StepStatus.FAILED
    assert "hazard" in state.error
    fail_cmds = [
        c for c in cmds3 if isinstance(c, EmitEventCommand) and c.event_type == "run.failed"
    ]
    assert len(fail_cmds) == 1


def test_step_timeout_triggers_retry() -> None:
    state = create_initial_state()
    state, _ = transition(state, StartRunEvent(event_id="evt-start", run_id=state.run_id))

    state, _cmds = transition(
        state,
        StepTimeoutEvent(event_id="evt-timeout-1", step_name="illumination"),
        max_retries=3,
    )
    assert state.steps["illumination"].status == StepStatus.RETRYING
    assert state.steps["illumination"].attempts == 2


def test_non_retryable_failure_fails_immediately() -> None:
    state = create_initial_state()
    state, _ = transition(state, StartRunEvent(event_id="evt-start", run_id=state.run_id))

    state, cmds = transition(
        state,
        StepFailedEvent(
            event_id="evt-fatal",
            step_name="terrain",
            error="Corrupt elevation dataset",
            retryable=False,
        ),
        max_retries=3,
    )
    assert state.status == RunStatus.FAILED
    assert state.steps["terrain"].status == StepStatus.FAILED
    assert any(isinstance(c, EmitEventCommand) and c.event_type == "run.failed" for c in cmds)


def test_cancel_run_cancels_running_steps() -> None:
    state = create_initial_state()
    state, _ = transition(state, StartRunEvent(event_id="evt-start", run_id=state.run_id))

    state, cmds = transition(
        state,
        CancelRunEvent(event_id="evt-cancel", reason="Operator aborted mission"),
    )
    assert state.status == RunStatus.CANCELED
    for name in ANALYSIS_STEPS:
        assert state.steps[name].status == StepStatus.CANCELED

    cancel_cmds = [
        c for c in cmds if isinstance(c, EmitEventCommand) and c.event_type.endswith(".cancel")
    ]
    assert len(cancel_cmds) == 4
