#!/usr/bin/env python3
"""Full-profile research-run state with deterministic, atomic JSON writes."""

from __future__ import annotations

import argparse
from copy import deepcopy
from contextlib import contextmanager
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 4
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
WINDOWS_RESERVED_BASENAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)
CLAIM_KINDS = frozenset(
    {"verified_fact", "user_claim", "inference", "assumption", "unknown"}
)
TRANSITION_KINDS = frozenset(
    {
        "hypothesis_added",
        "hypothesis_eliminated",
        "evidence_changed_judgment",
        "evidence_independence_changed",
        "unknown_resolved",
        "risk_or_action_changed",
    }
)
TERMINALS = frozenset(
    {
        "answered",
        "conditionally_answered",
        "unresolved_evidence_limit",
        "blocked_access",
        "stopped_budget",
        "invalidated_question",
    }
)
RESTART_REQUIRED = frozenset(
    {"unresolved_evidence_limit", "blocked_access", "stopped_budget"}
)
RETRO_TRIGGERS = frozenset(
    {
        "major_reversal",
        "user_found_error",
        "source_invalidated",
        "evaluator_disagreement",
        "protocol_exception",
        "abnormal_stop",
        "high_impact_error",
        "method_to_preserve",
    }
)
RESTART_EVENTS_BY_TERMINAL = {
    "unresolved_evidence_limit": frozenset(
        {"evidence_published", "dependency_completed", "constraint_changed"}
    ),
    "blocked_access": frozenset({"access_granted", "dependency_completed"}),
    "stopped_budget": frozenset({"budget_restored", "constraint_changed"}),
}
RESTART_EVENTS = frozenset().union(*RESTART_EVENTS_BY_TERMINAL.values())
WORKING_SET_KEYS = (
    "claims",
    "hypotheses",
    "evidence",
    "independence_groups",
)
CHANGE_DIMENSIONS = frozenset(
    {
        *WORKING_SET_KEYS,
        "judgment",
        "next_action",
        "risk_level",
    }
)


class StateError(ValueError):
    """Raised for an invalid state operation."""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise StateError(f"{label} must be a string")
    value = value.strip()
    if not value:
        raise StateError(f"{label} must not be empty")
    return value


def default_state_dir() -> Path:
    override = os.environ.get("DEEP_THINKING_STATE_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "deep-thinking" / "runs"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "deep-thinking" / "runs"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "deep-thinking" / "runs"


def resolve_state_dir(value: str | None) -> Path:
    directory = Path(value).expanduser() if value else default_state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir():
        raise StateError(f"state directory is not a directory: {directory}")
    return directory.resolve()


def validate_run_id(run_id: Any) -> str:
    if not isinstance(run_id, str):
        raise StateError("run id must be a string")
    if not RUN_ID_RE.fullmatch(run_id):
        raise StateError("run id must use letters, numbers, dot, underscore, or hyphen")
    if run_id.endswith(".") or run_id.split(".", 1)[0].upper() in WINDOWS_RESERVED_BASENAMES:
        raise StateError("run id is not a portable filename")
    return run_id


def state_path(directory: Path, run_id: str) -> Path:
    return directory / f"{validate_run_id(run_id)}.json"


@contextmanager
def run_lock(directory: Path, run_id: str):
    run_id = validate_run_id(run_id)
    path = directory / f".{run_id}.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise StateError(f"research run is busy: {run_id}") from exc
    try:
        os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        path.unlink(missing_ok=True)


def parse_json_list(value: str | None, label: str) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise StateError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise StateError(f"{label} must be a JSON list of objects")
    return parsed


def parse_timestamp(value: Any, label: str) -> datetime:
    text = nonempty(value, label)
    try:
        timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StateError(f"{label} must be an ISO-8601 timestamp") from exc
    if timestamp.utcoffset() != timedelta(0):
        raise StateError(f"{label} must use UTC")
    return timestamp


def assert_unique_ids(items: list[dict[str, Any]], label: str) -> None:
    ids: set[str] = set()
    for item in items:
        item_id = nonempty(item["id"], f"{label} id")
        if item_id in ids:
            raise StateError(f"{label} ids must be unique")
        ids.add(item_id)


def validate_items(state: dict[str, Any]) -> None:
    for item in state["claims"]:
        if not isinstance(item, dict) or set(item) != {"id", "kind", "text"}:
            raise StateError("each claim must contain id, kind, and text")
        if not isinstance(item["kind"], str) or item["kind"] not in CLAIM_KINDS:
            raise StateError("claim kind is invalid")
        nonempty(item["id"], "claim id")
        nonempty(item["text"], "claim text")
    assert_unique_ids(state["claims"], "claim")

    for item in state["hypotheses"]:
        if not isinstance(item, dict) or set(item) != {"id", "summary", "status"}:
            raise StateError("each hypothesis must contain id, summary, and status")
        nonempty(item["id"], "hypothesis id")
        nonempty(item["summary"], "hypothesis summary")
        if not isinstance(item["status"], str) or item["status"] not in {"active", "eliminated"}:
            raise StateError("hypothesis status is invalid")
    assert_unique_ids(state["hypotheses"], "hypothesis")

    for item in state["evidence"]:
        if not isinstance(item, dict) or set(item) != {"id", "source", "source_group", "effect"}:
            raise StateError("each evidence item must contain id, source, source_group, and effect")
        for key in ("id", "source", "source_group"):
            nonempty(item[key], f"evidence {key}")
        if not isinstance(item["effect"], str) or item["effect"] not in {
            "support",
            "weaken",
            "no_effect",
        }:
            raise StateError("evidence effect is invalid")
    assert_unique_ids(state["evidence"], "evidence")

    for item in state["independence_groups"]:
        if not isinstance(item, dict) or set(item) != {"id", "sources"}:
            raise StateError("each independence group must contain id and sources")
        nonempty(item["id"], "independence group id")
        if not isinstance(item["sources"], list) or not item["sources"]:
            raise StateError("independence group sources must be non-empty strings")
        for source in item["sources"]:
            nonempty(source, "independence group source")
    assert_unique_ids(state["independence_groups"], "independence group")

    groups = {group["id"]: set(group["sources"]) for group in state["independence_groups"]}
    source_owners: dict[str, str] = {}
    for group in state["independence_groups"]:
        if len(set(group["sources"])) != len(group["sources"]):
            raise StateError("independence group sources must be unique")
        for source in group["sources"]:
            owner = source_owners.setdefault(source, group["id"])
            if owner != group["id"]:
                raise StateError("a source may belong to only one independence group")
    for item in state["evidence"]:
        if item["source_group"] not in groups:
            raise StateError("evidence references an unknown independence group")
        if item["source"] not in groups[item["source_group"]]:
            raise StateError("evidence source is not a member of its independence group")


def working_set_snapshot(state: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    snapshot = {key: deepcopy(state[key]) for key in WORKING_SET_KEYS}
    for group in snapshot["independence_groups"]:
        group["sources"].sort()
    for key in WORKING_SET_KEYS:
        snapshot[key].sort(key=lambda item: item["id"])
    return snapshot


def validate_working_set_snapshot(value: Any) -> dict[str, list[dict[str, Any]]]:
    if (
        not isinstance(value, dict)
        or set(value) != set(WORKING_SET_KEYS)
        or any(not isinstance(value[key], list) for key in WORKING_SET_KEYS)
    ):
        raise StateError("checkpoint working set snapshot is invalid")
    validate_items(value)
    return value


def validate_transition_changes(kind: str, changes: list[str]) -> None:
    required = {
        "hypothesis_added": {"hypotheses"},
        "hypothesis_eliminated": {"hypotheses"},
        "evidence_changed_judgment": {"evidence", "judgment"},
        "unknown_resolved": {"claims"},
    }
    if kind in required and not required[kind].issubset(changes):
        raise StateError(f"{kind} transition changes do not match its kind")
    if kind == "evidence_independence_changed" and not {
        "evidence",
        "independence_groups",
    }.intersection(changes):
        raise StateError("evidence_independence_changed requires a source grouping change")
    if kind == "risk_or_action_changed" and not {
        "next_action",
        "risk_level",
    }.intersection(changes):
        raise StateError("risk_or_action_changed requires a risk or action change")


def validate_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise StateError("state must be an object")
    if state.get("schema_version") in {1, 2, 3}:
        raise StateError(
            f"legacy schema_version {state['schema_version']} must be replayed "
            "with its captured package"
        )
    required = {
        "schema_version",
        "run_id",
        "created_at",
        "updated_at",
        "activation",
        "research",
        "claims",
        "hypotheses",
        "evidence",
        "independence_groups",
        "current_judgment",
        "transitions",
        "checkpoints",
        "terminal",
        "retro",
    }
    if set(state) != required or state["schema_version"] != SCHEMA_VERSION:
        raise StateError("state has an unsupported schema")
    validate_run_id(state["run_id"])
    created_at = parse_timestamp(state["created_at"], "created_at")
    updated_at = parse_timestamp(state["updated_at"], "updated_at")
    if updated_at < created_at:
        raise StateError("updated_at cannot be earlier than created_at")
    activation = state["activation"]
    if not isinstance(activation, dict) or set(activation) != {
        "profile",
        "invocation_id",
        "started_at",
    }:
        raise StateError("activation provenance is invalid")
    if activation["profile"] != "full":
        raise StateError("Research Run activation profile must be full")
    validate_run_id(activation["invocation_id"])
    if parse_timestamp(activation["started_at"], "activation started_at") != created_at:
        raise StateError("activation started_at must equal created_at")

    research = state["research"]
    if not isinstance(research, dict) or set(research) != {"question", "decision_goal", "mandate"}:
        raise StateError("research is invalid")
    nonempty(research["question"], "question")
    nonempty(research["decision_goal"], "decision goal")
    mandate = research["mandate"]
    if not isinstance(mandate, dict) or set(mandate) != {
        "scope",
        "cost_boundary",
        "external_effects",
    }:
        raise StateError("research mandate is invalid")
    nonempty(mandate["scope"], "scope")
    if mandate["cost_boundary"] is not None:
        nonempty(mandate["cost_boundary"], "cost boundary")
    if not isinstance(mandate["external_effects"], bool):
        raise StateError("external effects is invalid")

    list_keys = ("claims", "hypotheses", "evidence", "independence_groups", "transitions", "checkpoints", "retro")
    if not all(isinstance(state[key], list) for key in list_keys):
        raise StateError("state lists are invalid")
    if state["current_judgment"] is not None:
        nonempty(state["current_judgment"], "current judgment")
    validate_items(state)

    transition_times: dict[str, datetime] = {}
    previous_transition_at = created_at
    for index, transition in enumerate(state["transitions"], 1):
        if not isinstance(transition, dict) or set(transition) != {
            "id",
            "kind",
            "summary",
            "judgment",
            "changes",
            "at",
        }:
            raise StateError("transition is invalid")
        if (
            transition["id"] != f"met-{index:04d}"
            or not isinstance(transition["kind"], str)
            or transition["kind"] not in TRANSITION_KINDS
        ):
            raise StateError("transition id or kind is invalid")
        for key in ("summary", "judgment"):
            nonempty(transition[key], f"transition {key}")
        if (
            not isinstance(transition["changes"], list)
            or not transition["changes"]
            or any(change not in CHANGE_DIMENSIONS for change in transition["changes"])
            or len(set(transition["changes"])) != len(transition["changes"])
        ):
            raise StateError("transition changes are invalid")
        validate_transition_changes(transition["kind"], transition["changes"])
        transition_at = parse_timestamp(transition["at"], "transition timestamp")
        if not created_at <= transition_at <= updated_at:
            raise StateError("transition timestamp falls outside the research run")
        if transition_at < previous_transition_at:
            raise StateError("transition timestamps must be chronological")
        transition_times[transition["id"]] = transition_at
        previous_transition_at = transition_at

    if len(state["transitions"]) != len(state["checkpoints"]):
        raise StateError("each transition must have exactly one checkpoint")

    previous_checkpoint_at = created_at
    previous_working_set = {key: [] for key in WORKING_SET_KEYS}
    previous_judgment: str | None = None
    previous_next_action: str | None = None
    previous_risk_level: str | None = None
    for index, checkpoint in enumerate(state["checkpoints"], 1):
        if not isinstance(checkpoint, dict) or set(checkpoint) != {
            "id",
            "transition_id",
            "judgment",
            "next_action",
            "risk_level",
            "working_set",
            "at",
        }:
            raise StateError("checkpoint is invalid")
        if checkpoint["id"] != f"checkpoint-{index:04d}":
            raise StateError("checkpoint id is invalid")
        if checkpoint["transition_id"] != f"met-{index:04d}":
            raise StateError("checkpoint references an unknown transition")
        for key in ("transition_id", "judgment", "next_action"):
            nonempty(checkpoint[key], f"checkpoint {key}")
        if not isinstance(checkpoint["risk_level"], str) or checkpoint["risk_level"] not in {
            "low",
            "medium",
            "high",
        }:
            raise StateError("checkpoint risk level is invalid")
        checkpoint_at = parse_timestamp(checkpoint["at"], "checkpoint timestamp")
        if not created_at <= checkpoint_at <= updated_at:
            raise StateError("checkpoint timestamp falls outside the research run")
        if checkpoint_at < transition_times[checkpoint["transition_id"]]:
            raise StateError("checkpoint timestamp precedes its transition")
        if checkpoint_at < previous_checkpoint_at:
            raise StateError("checkpoint timestamps must be chronological")
        transition = state["transitions"][index - 1]
        if checkpoint["judgment"] != transition["judgment"]:
            raise StateError("checkpoint judgment must match its transition")
        current_working_set = working_set_snapshot(
            validate_working_set_snapshot(checkpoint["working_set"])
        )
        actual_changes = compute_transition_changes(
            previous_working_set,
            current_working_set,
            previous_judgment,
            previous_next_action,
            previous_risk_level,
            checkpoint["judgment"],
            checkpoint["next_action"],
            checkpoint["risk_level"],
        )
        if transition["changes"] != actual_changes:
            raise StateError("transition changes do not match checkpoint history")
        validate_transition_semantics(
            transition["kind"],
            previous_working_set,
            current_working_set,
            actual_changes,
        )
        previous_working_set = current_working_set
        previous_judgment = checkpoint["judgment"]
        previous_next_action = checkpoint["next_action"]
        previous_risk_level = checkpoint["risk_level"]
        previous_checkpoint_at = checkpoint_at

    if working_set_snapshot(state) != previous_working_set:
        raise StateError("current working set must match the latest checkpoint snapshot")

    terminal = state["terminal"]
    terminal_at: datetime | None = None
    if terminal is not None:
        if not isinstance(terminal, dict) or set(terminal) != {
            "status",
            "judgment",
            "restart_condition",
            "at",
        }:
            raise StateError("terminal is invalid")
        if not isinstance(terminal["status"], str) or terminal["status"] not in TERMINALS:
            raise StateError("terminal status is invalid")
        nonempty(terminal["judgment"], "terminal judgment")
        if terminal["status"] in RESTART_REQUIRED and terminal["restart_condition"] is None:
            raise StateError("terminal requires a restart condition")
        if terminal["restart_condition"] is not None:
            validate_restart_condition(terminal["restart_condition"], terminal["status"])
        if previous_judgment is None:
            raise StateError("terminal requires at least one checkpoint")
        if terminal["judgment"] != previous_judgment:
            raise StateError("terminal judgment must match the latest checkpoint judgment")
        if state["current_judgment"] != terminal["judgment"]:
            raise StateError("current judgment must match the terminal judgment")
        terminal_at = parse_timestamp(terminal["at"], "terminal timestamp")
        if not created_at <= terminal_at <= updated_at:
            raise StateError("terminal timestamp falls outside the research run")
        if terminal_at < max(previous_transition_at, previous_checkpoint_at):
            raise StateError("terminal timestamp precedes recorded research activity")
    elif state["current_judgment"] != previous_judgment:
        raise StateError("current judgment must match the latest checkpoint")

    previous_retro_at = terminal_at or max(previous_transition_at, previous_checkpoint_at)
    for retro in state["retro"]:
        if not isinstance(retro, dict) or set(retro) != {"trigger", "note", "at"}:
            raise StateError("retro is invalid")
        if not isinstance(retro["trigger"], str) or retro["trigger"] not in RETRO_TRIGGERS:
            raise StateError("retro trigger is invalid")
        nonempty(retro["note"], "retro note")
        retro_at = parse_timestamp(retro["at"], "retro timestamp")
        if not created_at <= retro_at <= updated_at:
            raise StateError("retro timestamp falls outside the research run")
        if retro_at < previous_retro_at:
            raise StateError("retro timestamps must follow the research lifecycle")
        previous_retro_at = retro_at
    return state


def atomic_write(path: Path, state: dict[str, Any]) -> None:
    payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def load_state(path: Path, expected_run_id: str) -> dict[str, Any]:
    expected_run_id = validate_run_id(expected_run_id)
    if path.name != f"{expected_run_id}.json":
        raise StateError("filename and requested run id do not match")
    if not path.is_file():
        raise StateError(f"research run does not exist: {expected_run_id}")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot read research run: {exc}") from exc
    state = validate_state(state)
    if state["run_id"] != expected_run_id:
        raise StateError("payload and requested run id do not match")
    return state


def new_state(args: argparse.Namespace) -> dict[str, Any]:
    run_id = validate_run_id(args.run_id or f"run-{uuid.uuid4().hex}")
    invocation_id = validate_run_id(
        args.invocation_id or f"invocation-{uuid.uuid4().hex}"
    )
    timestamp = now()
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "activation": {
            "profile": "full",
            "invocation_id": invocation_id,
            "started_at": timestamp,
        },
        "research": {
            "question": nonempty(args.question, "question"),
            "decision_goal": nonempty(args.decision_goal, "decision goal"),
            "mandate": {
                "scope": nonempty(args.scope, "scope"),
                "cost_boundary": (
                    nonempty(args.cost_boundary, "cost boundary")
                    if args.cost_boundary is not None
                    else None
                ),
                "external_effects": args.external_effects,
            },
        },
        "claims": [],
        "hypotheses": [],
        "evidence": [],
        "independence_groups": [],
        "current_judgment": None,
        "transitions": [],
        "checkpoints": [],
        "terminal": None,
        "retro": [],
    }


def assign_working_sets(state: dict[str, Any], args: argparse.Namespace) -> None:
    mappings = (
        ("claims", args.claims_json),
        ("hypotheses", args.hypotheses_json),
        ("evidence", args.evidence_json),
        ("independence_groups", args.independence_groups_json),
    )
    for key, raw in mappings:
        parsed = parse_json_list(raw, key)
        if parsed is not None:
            state[key] = parsed


def reject_if_terminal(state: dict[str, Any]) -> None:
    if state["terminal"] is not None:
        raise StateError("research run is already finalized")


def validate_restart_condition(value: Any, terminal: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {
        "event_type",
        "subject",
        "observable_condition",
    }:
        raise StateError(
            "restart condition must contain event_type, subject, and observable_condition"
        )
    event_type = nonempty(value["event_type"], "restart event type")
    subject = nonempty(value["subject"], "restart subject")
    observable = nonempty(value["observable_condition"], "restart observable condition")
    allowed = RESTART_EVENTS_BY_TERMINAL.get(terminal, RESTART_EVENTS)
    if event_type not in allowed:
        raise StateError(f"restart event type is invalid for terminal {terminal}")
    return {
        "event_type": event_type,
        "subject": subject,
        "observable_condition": observable,
    }


def build_restart_condition(args: argparse.Namespace) -> dict[str, str] | None:
    values = (args.restart_event, args.restart_subject, args.restart_condition)
    if not any(value is not None for value in values):
        return None
    if not all(value is not None for value in values):
        raise StateError(
            "restart event, subject, and observable condition must be supplied together"
        )
    return validate_restart_condition(
        {
            "event_type": args.restart_event,
            "subject": args.restart_subject,
            "observable_condition": args.restart_condition,
        },
        args.terminal,
    )


def compute_transition_changes(
    before: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    previous_judgment: str | None,
    previous_next_action: str | None,
    previous_risk_level: str | None,
    judgment: str,
    next_action: str,
    risk_level: str,
) -> list[str]:
    changes = {key for key in WORKING_SET_KEYS if before[key] != after[key]}
    previous = {
        "judgment": previous_judgment,
        "next_action": previous_next_action,
        "risk_level": previous_risk_level,
    }
    current = {
        "judgment": judgment,
        "next_action": next_action,
        "risk_level": risk_level,
    }
    changes.update(key for key in current if previous[key] != current[key])
    return sorted(changes)


def validate_transition_semantics(
    kind: str,
    before: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    changes: list[str],
) -> None:
    before_hypotheses = {item["id"]: item for item in before["hypotheses"]}
    after_hypotheses = {item["id"]: item for item in after["hypotheses"]}
    before_claims = {item["id"]: item for item in before["claims"]}
    after_claims = {item["id"]: item for item in after["claims"]}
    before_independence = {
        (item["id"], item["source"], item["source_group"])
        for item in before["evidence"]
    }
    after_independence = {
        (item["id"], item["source"], item["source_group"])
        for item in after["evidence"]
    }

    if kind == "hypothesis_added" and not (after_hypotheses.keys() - before_hypotheses.keys()):
        raise StateError("hypothesis_added requires a newly added hypothesis")
    if kind == "hypothesis_eliminated" and not any(
        item["status"] == "active"
        and after_hypotheses.get(item_id, {}).get("status") == "eliminated"
        for item_id, item in before_hypotheses.items()
    ):
        raise StateError("hypothesis_eliminated requires an active hypothesis to be eliminated")
    if kind == "evidence_changed_judgment" and not {
        "evidence",
        "judgment",
    }.issubset(changes):
        raise StateError("evidence_changed_judgment requires evidence and judgment changes")
    if kind == "evidence_independence_changed" and not (
        before["independence_groups"] != after["independence_groups"]
        or before_independence != after_independence
    ):
        raise StateError(
            "evidence_independence_changed requires a changed source grouping"
        )
    if kind == "unknown_resolved" and not any(
        item["kind"] == "unknown"
        and after_claims.get(item_id, {}).get("kind") not in {None, "unknown"}
        for item_id, item in before_claims.items()
    ):
        raise StateError("unknown_resolved requires an unknown claim to be reclassified")
    if kind == "risk_or_action_changed" and not set(changes).intersection(
        {"next_action", "risk_level"}
    ):
        raise StateError("risk_or_action_changed requires a changed risk level or next action")
    if not changes:
        raise StateError("checkpoint requires a material epistemic state change")


def transition_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    kind: str,
    judgment: str,
    next_action: str,
    risk_level: str,
) -> list[str]:
    previous_checkpoint = before["checkpoints"][-1] if before["checkpoints"] else None
    changes = compute_transition_changes(
        working_set_snapshot(before),
        working_set_snapshot(after),
        before["current_judgment"],
        previous_checkpoint["next_action"] if previous_checkpoint else None,
        previous_checkpoint["risk_level"] if previous_checkpoint else None,
        judgment,
        next_action,
        risk_level,
    )
    validate_transition_semantics(
        kind,
        working_set_snapshot(before),
        working_set_snapshot(after),
        changes,
    )
    return changes


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    directory = resolve_state_dir(args.state_dir)
    state = new_state(args)
    path = state_path(directory, state["run_id"])
    with run_lock(directory, state["run_id"]):
        if path.exists():
            raise StateError(f"research run already exists: {state['run_id']}")
        validate_state(state)
        atomic_write(path, state)
    return state


def command_checkpoint(args: argparse.Namespace) -> dict[str, Any]:
    directory = resolve_state_dir(args.state_dir)
    path = state_path(directory, args.run_id)
    with run_lock(directory, args.run_id):
        state = load_state(path, args.run_id)
        reject_if_terminal(state)
        before = deepcopy(state)
        assign_working_sets(state, args)
        validate_items(state)
        transition_id = f"met-{len(state['transitions']) + 1:04d}"
        timestamp = now()
        judgment = nonempty(args.judgment, "judgment")
        next_action = nonempty(args.next_action, "next action")
        changes = transition_delta(
            before,
            state,
            args.kind,
            judgment,
            next_action,
            args.risk_level,
        )
        state["transitions"].append(
            {
                "id": transition_id,
                "kind": args.kind,
                "summary": nonempty(args.summary, "summary"),
                "judgment": judgment,
                "changes": changes,
                "at": timestamp,
            }
        )
        state["checkpoints"].append(
            {
                "id": f"checkpoint-{len(state['checkpoints']) + 1:04d}",
                "transition_id": transition_id,
                "judgment": judgment,
                "next_action": next_action,
                "risk_level": args.risk_level,
                "working_set": working_set_snapshot(state),
                "at": timestamp,
            }
        )
        state["current_judgment"] = judgment
        state["updated_at"] = timestamp
        validate_state(state)
        atomic_write(path, state)
    return state


def command_finalize(args: argparse.Namespace) -> dict[str, Any]:
    directory = resolve_state_dir(args.state_dir)
    path = state_path(directory, args.run_id)
    with run_lock(directory, args.run_id):
        state = load_state(path, args.run_id)
        reject_if_terminal(state)
        if not state["checkpoints"]:
            raise StateError("terminal requires at least one checkpoint")
        if bool(args.retro_trigger) != bool(args.retro_note):
            raise StateError("retro trigger and note must be supplied together")
        restart_condition = build_restart_condition(args)
        if args.terminal in RESTART_REQUIRED:
            if restart_condition is None:
                raise StateError(f"{args.terminal} requires a concrete restart condition")
        timestamp = now()
        judgment = nonempty(args.judgment, "judgment")
        if judgment != state["checkpoints"][-1]["judgment"]:
            raise StateError("terminal judgment must match the latest checkpoint judgment")
        state["current_judgment"] = judgment
        state["terminal"] = {
            "status": args.terminal,
            "judgment": judgment,
            "restart_condition": restart_condition,
            "at": timestamp,
        }
        if args.retro_trigger:
            state["retro"].append(
                {
                    "trigger": args.retro_trigger,
                    "note": nonempty(args.retro_note, "retro note"),
                    "at": timestamp,
                }
            )
        state["updated_at"] = timestamp
        validate_state(state)
        atomic_write(path, state)
    return state


def command_resume(args: argparse.Namespace) -> dict[str, Any]:
    return load_state(
        state_path(resolve_state_dir(args.state_dir), args.run_id),
        args.run_id,
    )


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    return command_resume(args)


def add_state_location(parser: argparse.ArgumentParser, *, run_id: bool = True) -> None:
    parser.add_argument("--state-dir")
    if run_id:
        parser.add_argument("--run-id", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    add_state_location(init, run_id=False)
    init.add_argument("--run-id")
    init.add_argument("--invocation-id")
    init.add_argument("--question", required=True)
    init.add_argument("--decision-goal", required=True)
    init.add_argument("--scope", required=True)
    init.add_argument("--cost-boundary")
    init.add_argument("--external-effects", action="store_true")
    init.set_defaults(handler=command_init)

    checkpoint = subparsers.add_parser(
        "checkpoint", formatter_class=argparse.RawTextHelpFormatter,
        description="Record a material change. JSON arguments replace the complete named list; omitted lists remain unchanged.",
        epilog="Use stable unique IDs. Evidence source must belong to its source_group; one source has one group owner. "
               "Choose a kind supported by the actual delta; risk_or_action_changed requires changed next-action or risk. "
               "A label alone is not a transition.")
    add_state_location(checkpoint)
    checkpoint.add_argument("--kind", choices=sorted(TRANSITION_KINDS), required=True)
    checkpoint.add_argument("--summary", required=True)
    checkpoint.add_argument("--judgment", required=True)
    checkpoint.add_argument("--next-action", default="Reassess the next discriminating action.")
    checkpoint.add_argument("--risk-level", choices=("low", "medium", "high"), default="medium")
    checkpoint.add_argument("--claims-json", help='JSON array: [{"id":"c1","kind":"user_claim","text":"Reported claim"}]. kind: ' + ", ".join(sorted(CLAIM_KINDS)))
    checkpoint.add_argument("--hypotheses-json", help='JSON array: [{"id":"h1","summary":"Possible explanation","status":"active"}]. status: active or eliminated.')
    checkpoint.add_argument("--evidence-json", help='JSON array: [{"id":"e1","source":"report","source_group":"g1","effect":"weaken"}]. effect: support, weaken or no_effect.')
    checkpoint.add_argument("--independence-groups-json", help='JSON array: [{"id":"g1","sources":["report"]}]. Sources must be nonempty and uniquely owned.')
    checkpoint.set_defaults(handler=command_checkpoint)

    finalize = subparsers.add_parser("finalize")
    add_state_location(finalize)
    finalize.add_argument("--terminal", choices=sorted(TERMINALS), required=True)
    finalize.add_argument("--judgment", required=True)
    finalize.add_argument("--restart-event", choices=sorted(RESTART_EVENTS))
    finalize.add_argument("--restart-subject")
    finalize.add_argument("--restart-condition")
    finalize.add_argument("--retro-trigger", choices=sorted(RETRO_TRIGGERS))
    finalize.add_argument("--retro-note")
    finalize.set_defaults(handler=command_finalize)

    for command, handler in (("resume", command_resume), ("validate", command_validate)):
        child = subparsers.add_parser(command)
        add_state_location(child)
        child.set_defaults(handler=handler)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        state = args.handler(args)
    except (OSError, StateError) as exc:
        print(f"research state failed: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
