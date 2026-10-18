#!/usr/bin/env python3
"""Create the SelenePlan GitHub Project, milestones, labels and issues from prompts/*.md.

What it does (safe to re-run; existing items are reused, not duplicated):
  1. Creates labels and Phase milestones (with due dates from docs/07-roadmap.md).
  2. Creates (or reuses) the org project "SelenePlan Roadmap", links it to the repo and adds
     the custom fields: Phase, Service, Kind, Priority, Size, Security-critical, Target date.
  3. Creates one epic per phase and one issue per "### Task X.Y" in prompts/phase-*.md,
     plus P-0 tasks, ADR issues, follow-ups and backlog items.
  4. Adds every issue to the project and sets its fields and Status.

Prerequisites (run once):
  gh auth login
  gh auth refresh -s project          # project scope is required for GitHub Projects

Usage (from the repo root):
  python scripts/setup_github_project.py --dry-run          # preview, makes no changes
  python scripts/setup_github_project.py                    # do it
  python scripts/setup_github_project.py --skip-fields      # faster: issues only, no field values

Options: --owner AstraDev-Labs --repo SelenePlan --start-date 2026-10-19 --project-title "..."
Fields are set with one gh call each, so a full run takes roughly 10 to 15 minutes.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"

# Last roadmap week of each phase (docs/07-roadmap.md).
PHASE_END_WEEK = {0: 2, 1: 4, 2: 7, 3: 9, 4: 12, 5: 16, 6: 20, 7: 22}
PHASE_NAMES = {
    0: "Foundation",
    1: "Data and terrain",
    2: "Illumination",
    3: "Earth visibility",
    4: "ML hazards",
    5: "Planning and integrity",
    6: "Hardening",
    7: "Release",
}
P0_NAME = "P-0 Prior art and scope"

SERVICES = [
    "gateway",
    "identity",
    "project-service",
    "ingestion-service",
    "terrain-service",
    "hazard-ml-service",
    "illumination-service",
    "comms-service",
    "planner-service",
    "report-service",
    "audit-service",
    "signing-service",
    "provenance-service",
    "web",
    "libs",
    "infra",
    "docs",
]
TYPES = ["Epic", "Task", "Bug", "Spike", "ADR", "Security", "Validation"]
PRIORITIES = ["P0", "P1", "P2"]
SIZES = ["S", "M", "L"]
PHASE_OPTIONS = ["P-0"] + [f"Phase {n}" for n in range(8)] + ["Backlog"]

LABELS = {
    "epic": ("5319e7", "Phase epic"),
    "task": ("0e8a16", "Implementation task from the prompt pack"),
    "adr-needed": ("fbca04", "Needs an architecture decision record"),
    "security": ("d73a4a", "Security-critical: needs human review before merge"),
    "science-validation": ("1d76db", "Scientific correctness or validation work"),
    "blocked": ("b60205", "Blocked by another item"),
    "backlog": ("cfd3d7", "Post-v1 idea"),
    **{f"svc:{s}": ("c5def5", f"Service or area: {s}") for s in SERVICES},
}

# Heuristic service detection from the task title (first match wins).
SERVICE_KEYWORDS = [
    ("signing-service", ["signing service"]),
    ("audit-service", ["audit"]),
    ("provenance-service", ["provenance", "replay"]),
    ("ingestion-service", ["ingestion"]),
    ("terrain-service", ["terrain service", "terrain"]),
    ("hazard-ml-service", ["hazard", "model registry", "inference", "training"]),
    ("illumination-service", ["illumination", "sun geometry"]),
    ("comms-service", ["earth direction", "visibility worker"]),
    ("planner-service", ["planner", "traverse", "site ranking", "energy model", "explanations"]),
    ("report-service", ["report"]),
    ("project-service", ["orchestrator", "approval", "rover profile"]),
    ("gateway", ["gateway"]),
    ("identity", ["realm", "keycloak"]),
    ("web", ["web shell", "ui", "timeline"]),
    ("libs", ["librar", "horizon computation"]),
    ("docs", ["documentation", "runbook", "release", "novelty", "demo", "final review"]),
]
SERVICE_OVERRIDES = {
    "0.1": "infra",
    "0.3": "identity",
    "0.6": "infra",
    "1.5": "terrain-service",
    "2.1": "illumination-service",
    "2.5": "illumination-service",
    "2.7": "illumination-service",
    "3.3": "comms-service",
    "3.5": "comms-service",
    "4.1": "hazard-ml-service",
    "5.1": "planner-service",
    "5.8": "provenance-service",
    "5.10": "web",
    "6.1": "infra",
    "6.2": "infra",
    "6.3": "infra",
    "6.4": "infra",
    "6.5": "infra",
    "6.6": "infra",
    "6.7": "infra",
    "6.8": "infra",
    "6.9": "docs",
}
SECURITY_SERVICES = {
    "signing-service",
    "audit-service",
    "provenance-service",
    "identity",
    "gateway",
}
SECURITY_WORDS = [
    "auth",
    "ssrf",
    "opa",
    "approval",
    "network and identity",
    "penetration",
    "model registry",
    "supply chain",
    "ingestion",
]
STATUS_DONE = {"0.1", "0.2"}
STATUS_IN_PROGRESS = {"0.3"}


@dataclass
class Item:
    key: str  # "0.3", "P-0.1", "EPIC-2", "ADR-gateway", ...
    title: str
    body: str
    phase: str  # one of PHASE_OPTIONS
    service: str
    type: str
    priority: str
    size: str
    security: bool
    labels: list[str] = field(default_factory=list)
    status: str = "Todo"  # Todo | In Progress | Done
    milestone: str | None = None
    due: date | None = None
    epic_key: str | None = None
    # filled in at runtime
    number: int | None = None
    url: str | None = None


# ----------------------------------------------------------------------------- gh wrapper
TRANSIENT_MARKERS = (
    "something went wrong",
    "502",
    "503",
    "504",
    "bad gateway",
    "timeout",
    "timed out",
    "connection reset",
    "eof",
    "rate limit",
    "temporarily unavailable",
)


class GH:
    def __init__(self, dry: bool, owner: str, repo: str) -> None:
        self.dry = dry
        self.owner = owner
        self.repo = repo
        self.exe = shutil.which("gh") or "gh"
        self._fake_issue = 1000
        self._calls = 0

    def run(self, *args: str, check: bool = True) -> str:
        cmd = [self.exe, *args]
        self._calls += 1
        if self.dry:
            return self._fake(args)
        # Retry transient GitHub errors (GraphQL hiccups, 5xx, rate limits). Never retry
        # "issue create": a retry could duplicate an issue that was actually created.
        retryable = tuple(args[:2]) != ("issue", "create")
        waits = [2, 5, 15, 45]
        attempt = 0
        while True:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            if proc.returncode == 0:
                return proc.stdout
            msg = (proc.stderr or proc.stdout).strip()
            low = msg.lower()
            transient = any(m in low for m in TRANSIENT_MARKERS)
            if retryable and transient and attempt < len(waits):
                wait = 60 if "rate limit" in low else waits[attempt]
                attempt += 1
                print(f"    (transient GitHub error, retry {attempt}/{len(waits)} in {wait}s)")
                time.sleep(wait)
                continue
            if check:
                raise SystemExit(
                    f"\nERROR: gh {' '.join(args[:4])} ... failed:\n{msg}\n"
                    "Safe to re-run the script: it skips what already exists."
                )
            return ""

    def json(self, *args: str, check: bool = True):
        out = self.run(*args, check=check).strip()
        return json.loads(out) if out else None

    def _fake(self, args: tuple[str, ...]):
        head = " ".join(args[:2])
        if head == "issue create":
            self._fake_issue += 1
            return f"https://github.com/{self.owner}/{self.repo}/issues/{self._fake_issue}\n"
        if head == "project create":
            return json.dumps({"number": 1, "id": "PVT_dry", "url": "dry"})
        if head == "project list":
            return json.dumps({"projects": []})
        if head == "project field-list":
            fields = [
                {
                    "id": "F_status",
                    "name": "Status",
                    "type": "ProjectV2SingleSelectField",
                    "options": [
                        {"id": "o1", "name": "Todo"},
                        {"id": "o2", "name": "In Progress"},
                        {"id": "o3", "name": "Done"},
                    ],
                }
            ]
            return json.dumps({"fields": fields})
        if head == "project item-add":
            return json.dumps({"id": f"ITEM_{self._calls}"})
        if head == "auth status":
            return "Token scopes: 'project', 'repo'"
        if head in ("issue list", "api repos"):
            return ""
        return ""


# ----------------------------------------------------------------------------- parsing
def parse_phase_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^# Phase (\d+): (.+)$", text, re.M)
    if not m:
        raise SystemExit(f"Cannot parse phase header in {path}")
    num = int(m.group(1))
    goal = re.search(r"\*\*Goal:\*\*\s*(.+)", text)
    read_first = re.search(r"\*\*Read first:\*\*\s*(.+)", text)
    exit_m = re.search(r"^## Phase \d+ exit criteria\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    tasks = []
    for tm in re.finditer(
        r"^### Task (\d+\.\d+): (.+?)\n(.*?)(?=^### |^## |\Z)", text, re.M | re.S
    ):
        tasks.append({"id": tm.group(1), "title": tm.group(2).strip(), "body": tm.group(3).strip()})
    return {
        "num": num,
        "title": m.group(2).strip(),
        "goal": goal.group(1).strip() if goal else "",
        "read_first": read_first.group(1).strip() if read_first else "",
        "exit": exit_m.group(1).strip() if exit_m else "",
        "tasks": tasks,
        "file": path.name,
    }


def detect_service(task_id: str, title: str) -> str:
    if task_id in SERVICE_OVERRIDES:
        return SERVICE_OVERRIDES[task_id]
    low = title.lower()
    for service, words in SERVICE_KEYWORDS:
        if any(w in low for w in words):
            return service
    return "infra"


def classify_type(title: str) -> str:
    low = title.lower()
    if "adr" in low.split() or low.startswith("adrs"):
        return "ADR"
    if low.startswith(("validation", "cross-check")) or "load, soak" in low:
        return "Validation"
    if "penetration" in low:
        return "Security"
    return "Task"


def labels_for(service: str, typ: str, security: bool) -> list[str]:
    labels = ["task", f"svc:{service}"]
    if security:
        labels.append("security")
    if typ == "Validation":
        labels.append("science-validation")
    if typ == "ADR":
        labels.append("adr-needed")
    return labels


def phase_due(start: date, phase: int) -> date:
    return start + timedelta(days=PHASE_END_WEEK[phase] * 7 - 1)


def build_items(start: date) -> list[Item]:
    items: list[Item] = []
    phases = [parse_phase_file(p) for p in sorted(PROMPTS.glob("phase-*.md"))]
    if len(phases) != 8:
        raise SystemExit(f"Expected 8 prompts/phase-*.md files, found {len(phases)}")

    # P-0 (prior art and scope)
    p0_due = start + timedelta(days=6)
    p0 = [
        (
            "P-0.1",
            "Prior-art search",
            "Search Google Scholar, arXiv, Google Patents and GitHub for: lunar south pole traverse planning, illumination and Earth-visibility mapping, explainable site selection, time-dependent rover path planning. Record findings with citations.",
            "Spike",
        ),
        (
            "P-0.2",
            "Write docs/novelty.md",
            "Table of existing tools, what they cover, and the gap SelenePlan fills. State the one-line novelty claim. Do not invent citations.",
            "Task",
        ),
        (
            "P-0.3",
            "Choose the AOI and period",
            "Pick a small south-polar AOI (about 10 to 20 km) and the analysis period. Record in docs/validation/aoi.md.",
            "Task",
        ),
        (
            "P-0.4",
            "List datasets, licenses and access method",
            "For every dataset (DEM, imagery, SPICE kernels, crater catalog, ISRO PRADAN if used) record source, license, redistribution terms, checksums and how to download.",
            "Task",
        ),
    ]
    for key, title, body, typ in p0:
        items.append(
            Item(
                key,
                f"{key}: {title}",
                body,
                "P-0",
                "docs",
                typ,
                "P0",
                "S",
                False,
                ["task", "svc:docs"],
                milestone=P0_NAME,
                due=p0_due,
            )
        )

    for ph in phases:
        n = ph["num"]
        milestone = f"Phase {n} - {PHASE_NAMES[n]}"
        due = phase_due(start, n)
        epic_key = f"EPIC-{n}"
        items.append(
            Item(
                epic_key,
                f"Epic: Phase {n} - {ph['title']}",
                f"**Goal:** {ph['goal']}\n\n**Prompt:** `prompts/{ph['file']}`\n\n"
                f"## Exit criteria\n{ph['exit']}\n\n## Tasks\n_(checklist added automatically)_",
                f"Phase {n}",
                "docs",
                "Epic",
                "P0" if n <= 2 else "P1",
                "L",
                False,
                ["epic"],
                milestone=milestone,
                due=due,
            )
        )
        for t in ph["tasks"]:
            service = detect_service(t["id"], t["title"])
            typ = classify_type(t["title"])
            low = t["title"].lower()
            security = service in SECURITY_SERVICES or any(w in low for w in SECURITY_WORDS)
            priority = "P0" if (n <= 1 or security) else ("P2" if service == "docs" else "P1")
            size = "L" if len(t["body"]) > 800 else ("M" if len(t["body"]) > 450 else "S")
            status = (
                "Done"
                if t["id"] in STATUS_DONE
                else ("In Progress" if t["id"] in STATUS_IN_PROGRESS else "Todo")
            )
            body = (
                f"**Phase:** {n} - {ph['title']} | **Service:** `{service}` | "
                f"**Prompt:** `prompts/{ph['file']}` (Task {t['id']})\n\n"
                f"## Goal\n{ph['goal']}\n\n## Read first\n{ph['read_first']}\n\n"
                f"## Task\n{t['body']}\n\n"
                "## Definition of done (AGENTS.md section 3)\n"
                "- [ ] The 'Done when' criteria above are met\n"
                "- [ ] Code plus unit tests (and an integration test where a DB, Kafka or MinIO is involved)\n"
                "- [ ] `ruff`, `mypy --strict` and `pytest` pass (real output attached)\n"
                "- [ ] OpenAPI / event contracts and docs updated\n"
                "- [ ] Audit events for state changes; no secrets; deny-by-default authz\n"
                "- [ ] Human review of security- and science-critical code\n"
            )
            items.append(
                Item(
                    t["id"],
                    f"Task {t['id']}: {t['title']}",
                    body,
                    f"Phase {n}",
                    service,
                    typ,
                    priority,
                    size,
                    security,
                    labels_for(service, typ, security),
                    status=status,
                    milestone=milestone,
                    due=due,
                    epic_key=epic_key,
                )
            )

    # Follow-ups and decisions discovered during Phase 0 reviews
    p0m, p1m = "Phase 0 - Foundation", "Phase 1 - Data and terrain"
    due0, due1 = phase_due(start, 0), phase_due(start, 1)
    extras = [
        Item(
            "FU-lease",
            "Follow-up: long-running handlers vs 60 s dedupe lease",
            "The two-phase dedupe lease defaults to 60 s, but analysis jobs can take up to 15 min (NFR-03).\n\n"
            "Before Phase 1 consumers run heavy analyses, implement either (a) heartbeat lease renewal plus matching "
            "`max.poll.interval.ms`, or (b) asynchronous dispatch per ADR-0002 (write PENDING job to PostgreSQL, commit "
            "the offset, run compute out of band). Add a crash-mid-job test.",
            "Phase 0",
            "libs",
            "Task",
            "P0",
            "M",
            False,
            ["task", "svc:libs"],
            milestone=p0m,
            due=due0,
            epic_key="EPIC-0",
        ),
        Item(
            "ADR-gateway",
            "ADR: gateway choice (Kong + jwt plugin vs Envoy jwt_authn)",
            "Kong OSS validates JWTs with static keys only; JWKS rotation needs a plugin or a different gateway. "
            "Decide, record in services/gateway/DECISIONS.md and update infra/. See services/gateway/SPEC.md.",
            "Phase 0",
            "gateway",
            "ADR",
            "P0",
            "S",
            True,
            ["task", "svc:gateway", "adr-needed", "security"],
            milestone=p0m,
            due=due0,
            epic_key="EPIC-0",
        ),
        Item(
            "ADR-minio",
            "ADR note: MinIO image and future S3-compatible store",
            "The compose stack uses cgr.dev/chainguard/minio:latest. Pin by digest before staging and note a possible "
            "move to another S3-compatible store (for example SeaweedFS or Garage). Add the note to docs/adr/0004.",
            "Phase 0",
            "infra",
            "ADR",
            "P2",
            "S",
            False,
            ["task", "svc:infra", "adr-needed"],
            milestone=p0m,
            due=due0,
            epic_key="EPIC-0",
        ),
        Item(
            "ADR-illum",
            "ADR: illumination algorithm (horizon profile vs ray marching)",
            "Compare horizon-profile, per-time ray marching and hybrid. See prompts/phase-2-illumination.md Task 2.1.",
            "Phase 2",
            "illumination-service",
            "ADR",
            "P0",
            "M",
            False,
            ["task", "svc:illumination-service", "adr-needed"],
            milestone="Phase 2 - Illumination",
            due=phase_due(start, 2),
            epic_key="EPIC-2",
        ),
        Item(
            "ADR-timestack",
            "ADR: time-stack storage (banded COG vs Zarr vs hybrid)",
            "Benchmark slice reads and per-cell time-series reads. See docs/adr/0004 (open item).",
            "Phase 2",
            "illumination-service",
            "ADR",
            "P0",
            "M",
            False,
            ["task", "svc:illumination-service", "adr-needed"],
            milestone="Phase 2 - Illumination",
            due=phase_due(start, 2),
            epic_key="EPIC-2",
        ),
        Item(
            "ADR-map",
            "ADR: 2D polar map library (MapLibre vs deck.gl)",
            "Decide in Phase 1 Task 1.6 and record the decision.",
            "Phase 1",
            "web",
            "ADR",
            "P1",
            "S",
            False,
            ["task", "svc:web", "adr-needed"],
            milestone=p1m,
            due=due1,
            epic_key="EPIC-1",
        ),
        Item(
            "ADR-ml",
            "ADR: ML detection architecture",
            "Choose and justify the detection or segmentation model for craters (then boulders). See prompts/phase-4-ml-hazards.md Task 4.2.",
            "Phase 4",
            "hazard-ml-service",
            "ADR",
            "P1",
            "S",
            True,
            ["task", "svc:hazard-ml-service", "adr-needed", "security"],
            milestone="Phase 4 - ML hazards",
            due=phase_due(start, 4),
            epic_key="EPIC-4",
        ),
    ]
    items.extend(extras)

    # Backlog (post v1)
    for idea in [
        "Multi-rover fleet planning",
        "Dynamic re-planning from telemetry",
        "Thermal modeling",
        "Higher-fidelity soil mechanics",
        "Collaborative editing",
        "Other bodies (Mars)",
        "Public read-only dashboard",
    ]:
        items.append(
            Item(
                f"BL-{idea}",
                f"Backlog: {idea}",
                "Post-v1 idea from docs/07-roadmap.md. Not scheduled.",
                "Backlog",
                "docs",
                "Task",
                "P2",
                "L",
                False,
                ["backlog", "svc:docs"],
            )
        )
    return items


# ----------------------------------------------------------------------------- GitHub steps
def check_auth(gh: GH) -> None:
    out = gh.run("auth", "status", check=False) or ""
    if not gh.dry:
        proc = subprocess.run(
            [gh.exe, "auth", "status"], capture_output=True, text=True, encoding="utf-8"
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            raise SystemExit("gh is not logged in. Run: gh auth login")
        if "project" not in out:
            raise SystemExit("gh token lacks the 'project' scope. Run: gh auth refresh -s project")


def ensure_labels(gh: GH) -> None:
    print("Labels ...")
    for name, (color, desc) in LABELS.items():
        gh.run(
            "label",
            "create",
            name,
            "--color",
            color,
            "--description",
            desc,
            "--force",
            "-R",
            f"{gh.owner}/{gh.repo}",
        )


def ensure_milestones(gh: GH, items: list[Item]) -> None:
    print("Milestones ...")
    existing = set()
    out = gh.run(
        "api",
        f"repos/{gh.owner}/{gh.repo}/milestones?state=all&per_page=100",
        "--paginate",
        "--jq",
        ".[].title",
        check=False,
    )
    existing.update(line.strip() for line in out.splitlines() if line.strip())
    wanted: dict[str, date] = {}
    for it in items:
        if it.milestone and it.due:
            wanted.setdefault(it.milestone, it.due)
    for title, due in wanted.items():
        if title in existing:
            continue
        gh.run(
            "api",
            f"repos/{gh.owner}/{gh.repo}/milestones",
            "--method",
            "POST",
            "-f",
            f"title={title}",
            "-f",
            f"due_on={due.isoformat()}T00:00:00Z",
            "-f",
            "description=See docs/07-roadmap.md",
        )


def ensure_project(gh: GH, title: str) -> tuple[int, str, dict]:
    print(f"Project '{title}' ...")
    data = gh.json("project", "list", "--owner", gh.owner, "--format", "json", "--limit", "100")
    number = project_id = None
    for p in (data or {}).get("projects", []):
        if p.get("title") == title:
            number, project_id = p["number"], p["id"]
    if number is None:
        created = gh.json(
            "project", "create", "--owner", gh.owner, "--title", title, "--format", "json"
        )
        number, project_id = created["number"], created["id"]
    gh.run(
        "project",
        "link",
        str(number),
        "--owner",
        gh.owner,
        "--repo",
        f"{gh.owner}/{gh.repo}",
        check=False,
    )

    def fields() -> dict:
        fl = gh.json(
            "project",
            "field-list",
            str(number),
            "--owner",
            gh.owner,
            "--format",
            "json",
            "--limit",
            "100",
        )
        return {f["name"]: f for f in fl["fields"]}

    have = fields()
    specs = [
        ("Phase", "SINGLE_SELECT", PHASE_OPTIONS),
        ("Service", "SINGLE_SELECT", SERVICES),
        ("Kind", "SINGLE_SELECT", TYPES),
        ("Priority", "SINGLE_SELECT", PRIORITIES),
        ("Size", "SINGLE_SELECT", SIZES),
        ("Security-critical", "SINGLE_SELECT", ["Yes", "No"]),
        ("Target date", "DATE", []),
    ]
    for name, dtype, options in specs:
        if name in have:
            continue
        args = [
            "project",
            "field-create",
            str(number),
            "--owner",
            gh.owner,
            "--name",
            name,
            "--data-type",
            dtype,
        ]
        if options:
            args += ["--single-select-options", ",".join(options)]
        # "Type" is a reserved GitHub field name, hence "Kind". Do not abort on one bad field.
        gh.run(*args, check=False)
    final = fields()
    for name, _dtype, _options in specs:
        if name not in final:
            print(
                f"  WARNING: could not create project field '{name}'. Add it in the project settings "
                "(its values will be skipped in this run)."
            )
    return number, project_id, final


def load_existing_issues(gh: GH) -> dict[str, dict]:
    data = gh.json(
        "issue",
        "list",
        "-R",
        f"{gh.owner}/{gh.repo}",
        "--state",
        "all",
        "--limit",
        "1000",
        "--json",
        "number,title,url",
        check=False,
    )
    return {d["title"]: d for d in (data or [])}


_TMP_FILES: list[str] = []


def write_tmp(text: str) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    _TMP_FILES.append(f.name)
    return f.name


def cleanup_tmp() -> None:
    for name in _TMP_FILES:
        try:
            Path(name).unlink()
        except OSError:
            pass


def create_issue(gh: GH, it: Item, existing: dict[str, dict], epic: Item | None) -> None:
    if it.title in existing:
        it.number, it.url = existing[it.title]["number"], existing[it.title]["url"]
        print(f"  = exists  #{it.number} {it.title}")
        return
    body = it.body + (f"\n\nPart of #{epic.number}" if epic and epic.number else "")
    args = [
        "issue",
        "create",
        "-R",
        f"{gh.owner}/{gh.repo}",
        "--title",
        it.title,
        "--body-file",
        write_tmp(body),
    ]
    for lab in it.labels:
        args += ["--label", lab]
    if it.milestone:
        args += ["--milestone", it.milestone]
    url = gh.run(*args).strip().splitlines()[-1]
    it.url = url
    it.number = int(url.rstrip("/").split("/")[-1])
    print(f"  + {'would create' if gh.dry else 'created'} #{it.number} {it.title}")
    if not gh.dry:
        time.sleep(1.5)
    if it.status == "Done":
        gh.run(
            "issue", "close", str(it.number), "-R", f"{gh.owner}/{gh.repo}", "--reason", "completed"
        )


def set_fields(gh: GH, it: Item, project_number: int, project_id: str, fields: dict) -> None:
    added = gh.json(
        "project",
        "item-add",
        str(project_number),
        "--owner",
        gh.owner,
        "--url",
        it.url,
        "--format",
        "json",
    )
    item_id = added["id"]

    def single(field_name: str, value: str) -> None:
        f = fields.get(field_name)
        if not f:
            return
        opt = next((o for o in f.get("options", []) if o["name"] == value), None)
        if not opt:
            return
        gh.run(
            "project",
            "item-edit",
            "--id",
            item_id,
            "--project-id",
            project_id,
            "--field-id",
            f["id"],
            "--single-select-option-id",
            opt["id"],
        )

    single("Status", it.status)
    single("Phase", it.phase)
    single("Service", it.service)
    single("Kind", it.type)
    single("Priority", it.priority)
    single("Size", it.size)
    single("Security-critical", "Yes" if it.security else "No")
    if it.due and "Target date" in fields:
        gh.run(
            "project",
            "item-edit",
            "--id",
            item_id,
            "--project-id",
            project_id,
            "--field-id",
            fields["Target date"]["id"],
            "--date",
            it.due.isoformat(),
        )


def update_epics(gh: GH, items: list[Item]) -> None:
    print("Epic checklists ...")
    by_key = {i.key: i for i in items}
    for it in items:
        if it.type != "Epic" or not it.number:
            continue
        children = [c for c in items if c.epic_key == it.key and c.number]
        checklist = "\n".join(
            f"- [{'x' if c.status == 'Done' else ' '}] #{c.number} {c.title}" for c in children
        )
        body = it.body.replace("_(checklist added automatically)_", checklist)
        gh.run(
            "issue",
            "edit",
            str(it.number),
            "-R",
            f"{gh.owner}/{gh.repo}",
            "--body-file",
            write_tmp(body),
        )
    _ = by_key


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--owner", default="AstraDev-Labs")
    ap.add_argument("--repo", default="SelenePlan")
    ap.add_argument("--project-title", default="SelenePlan Roadmap")
    ap.add_argument(
        "--start-date", default="2026-10-19", help="Monday of roadmap week 1 (YYYY-MM-DD)"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Parse and print the plan; make no changes"
    )
    ap.add_argument(
        "--skip-fields",
        action="store_true",
        help="Create issues and add to project, but do not set field values",
    )
    ap.add_argument(
        "--skip-project", action="store_true", help="Only labels, milestones and issues"
    )
    args = ap.parse_args()

    start = date.fromisoformat(args.start_date)
    items = build_items(start)
    gh = GH(args.dry_run, args.owner, args.repo)

    if args.dry_run:
        print(f"DRY RUN: {len(items)} items would be created\n")
        print(
            f"{'KEY':<16}{'PHASE':<9}{'SERVICE':<22}{'TYPE':<11}{'PRI':<5}{'SZ':<4}{'SEC':<5}{'STATUS':<12}TITLE"
        )
        for it in items:
            print(
                f"{it.key[:15]:<16}{it.phase:<9}{it.service:<22}{it.type:<11}{it.priority:<5}{it.size:<4}"
                f"{'Y' if it.security else '-':<5}{it.status:<12}{it.title[:60]}"
            )
        print()

    check_auth(gh)
    ensure_labels(gh)
    ensure_milestones(gh, items)

    project_number = project_id = None
    fields: dict = {}
    if not args.skip_project:
        project_number, project_id, fields = ensure_project(gh, args.project_title)

    existing = load_existing_issues(gh)
    print("Issues ...")
    by_key = {i.key: i for i in items}
    ordered = [i for i in items if i.type == "Epic"] + [i for i in items if i.type != "Epic"]
    for it in ordered:
        epic = by_key.get(it.epic_key) if it.epic_key else None
        create_issue(gh, it, existing, epic)
        if project_number is not None and it.url:
            if args.skip_fields:
                gh.run(
                    "project", "item-add", str(project_number), "--owner", gh.owner, "--url", it.url
                )
            else:
                set_fields(gh, it, project_number, project_id or "", fields)

    update_epics(gh, items)
    cleanup_tmp()
    print(
        f"\nDone. {len(items)} items processed, {gh._calls} gh calls."
        + (" (dry run, nothing changed)" if gh.dry else "")
    )
    if not gh.dry:
        print(
            "Open the project, then create the views (Board / Roadmap / Table) as described in the guide."
        )


if __name__ == "__main__":
    sys.exit(main())
