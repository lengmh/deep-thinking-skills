#!/usr/bin/env python3
"""Full-profile research-run state with deterministic, atomic JSON writes."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
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
VAGUE_RESTART_PHRASES = (
    "more information",
    "further investigation",
    "investigate further",
    "further research",
    "do more research",
    "when more is known",
    "retry later",
    "try again later",
    "更多信息",
    "进一步调查",
    "继续调查",
    "有新资料后重试",
    "获得新资料后重试",
    "以后重试",
    "稍后重试",
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
    return run_id


def state_path(directory: Path, run_id: str) -> Path:
    return directory / f"{validate_run_id(run_id)}.json"


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

    group_ids = {group["id"] for group in state["independence_groups"]}
    if any(item["source_group"] not in group_ids for item in state["evidence"]):
        raise StateError("evidence references an unknown independence group")


def validate_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise StateError("state must be an object")
    required = {
        "schema_version",
        "run_id",
        "created_at",
        "updated_at",
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

    for index, transition in enumerate(state["transitions"], 1):
        if not isinstance(transition, dict) or set(transition) != {
            "id",
            "kind",
            "summary",
            "judgment",
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
        transition_at = parse_timestamp(transition["at"], "transition timestamp")
        if not created_at <= transition_at <= updated_at:
            raise StateError("transition timestamp falls outside the research run")

    for index, checkpoint in enumerate(state["checkpoints"], 1):
        if not isinstance(checkpoint, dict) or set(checkpoint) != {
            "id",
            "transition_id",
            "judgment",
            "next_action",
            "risk_level",
            "at",
        }:
            raise StateError("checkpoint is invalid")
        if checkpoint["id"] != f"checkpoint-{index:04d}":
            raise StateError("checkpoint id is invalid")
        if checkpoint["transition_id"] not in {
            transition["id"] for transition in state["transitions"]
        }:
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

    terminal = state["terminal"]
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
        if terminal["status"] in RESTART_REQUIRED and not terminal["restart_condition"]:
            raise StateError("terminal requires a restart condition")
        if terminal["restart_condition"] is not None:
            concrete_restart_condition(terminal["restart_condition"])
        terminal_at = parse_timestamp(terminal["at"], "terminal timestamp")
        if not created_at <= terminal_at <= updated_at:
            raise StateError("terminal timestamp falls outside the research run")

    for retro in state["retro"]:
        if not isinstance(retro, dict) or set(retro) != {"trigger", "note", "at"}:
            raise StateError("retro is invalid")
        if not isinstance(retro["trigger"], str) or retro["trigger"] not in RETRO_TRIGGERS:
            raise StateError("retro trigger is invalid")
        nonempty(retro["note"], "retro note")
        retro_at = parse_timestamp(retro["at"], "retro timestamp")
        if not created_at <= retro_at <= updated_at:
            raise StateError("retro timestamp falls outside the research run")
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


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise StateError(f"research run does not exist: {path.stem}")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot read research run: {exc}") from exc
    return validate_state(state)


def new_state(args: argparse.Namespace) -> dict[str, Any]:
    run_id = validate_run_id(args.run_id or f"run-{uuid.uuid4().hex}")
    timestamp = now()
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
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


def concrete_restart_condition(value: Any) -> str:
    value = nonempty(value, "restart condition")
    normalized = " ".join(value.casefold().strip(" .。；;").split())
    if any(phrase in normalized for phrase in VAGUE_RESTART_PHRASES):
        raise StateError("restart condition must name a concrete event, not a vague future inquiry")
    return value


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    directory = resolve_state_dir(args.state_dir)
    state = new_state(args)
    path = state_path(directory, state["run_id"])
    if path.exists():
        raise StateError(f"research run already exists: {state['run_id']}")
    validate_state(state)
    atomic_write(path, state)
    return state


def command_checkpoint(args: argparse.Namespace) -> dict[str, Any]:
    directory = resolve_state_dir(args.state_dir)
    path = state_path(directory, args.run_id)
    state = load_state(path)
    reject_if_terminal(state)
    assign_working_sets(state, args)
    transition_id = f"met-{len(state['transitions']) + 1:04d}"
    timestamp = now()
    judgment = nonempty(args.judgment, "judgment")
    state["transitions"].append(
        {
            "id": transition_id,
            "kind": args.kind,
            "summary": nonempty(args.summary, "summary"),
            "judgment": judgment,
            "at": timestamp,
        }
    )
    state["checkpoints"].append(
        {
            "id": f"checkpoint-{len(state['checkpoints']) + 1:04d}",
            "transition_id": transition_id,
            "judgment": judgment,
            "next_action": nonempty(args.next_action, "next action"),
            "risk_level": args.risk_level,
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
    state = load_state(path)
    reject_if_terminal(state)
    if bool(args.retro_trigger) != bool(args.retro_note):
        raise StateError("retro trigger and note must be supplied together")
    restart_condition = args.restart_condition
    if args.terminal in RESTART_REQUIRED:
        if restart_condition is None:
            raise StateError(f"{args.terminal} requires a concrete restart condition")
        restart_condition = concrete_restart_condition(restart_condition)
    elif restart_condition is not None:
        restart_condition = concrete_restart_condition(restart_condition)
    timestamp = now()
    judgment = nonempty(args.judgment, "judgment")
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
    return load_state(state_path(resolve_state_dir(args.state_dir), args.run_id))


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
    init.add_argument("--question", required=True)
    init.add_argument("--decision-goal", required=True)
    init.add_argument("--scope", required=True)
    init.add_argument("--cost-boundary")
    init.add_argument("--external-effects", action="store_true")
    init.set_defaults(handler=command_init)

    checkpoint = subparsers.add_parser("checkpoint")
    add_state_location(checkpoint)
    checkpoint.add_argument("--kind", choices=sorted(TRANSITION_KINDS), required=True)
    checkpoint.add_argument("--summary", required=True)
    checkpoint.add_argument("--judgment", required=True)
    checkpoint.add_argument("--next-action", default="Reassess the next discriminating action.")
    checkpoint.add_argument("--risk-level", choices=("low", "medium", "high"), default="medium")
    checkpoint.add_argument("--claims-json")
    checkpoint.add_argument("--hypotheses-json")
    checkpoint.add_argument("--evidence-json")
    checkpoint.add_argument("--independence-groups-json")
    checkpoint.set_defaults(handler=command_checkpoint)

    finalize = subparsers.add_parser("finalize")
    add_state_location(finalize)
    finalize.add_argument("--terminal", choices=sorted(TERMINALS), required=True)
    finalize.add_argument("--judgment", required=True)
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
