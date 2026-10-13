#!/usr/bin/env python3
"""Validate and fingerprint the vNext deep-thinking Skill package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


EXPECTED_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    "references/adversarial-checks.md",
    "references/claim-evidence-model.md",
    "references/epistemic-kernel.md",
    "references/profile-full.md",
    "references/profile-lite.md",
    "references/profile-standard.md",
    "references/synthesis-stopping.md",
    "schemas/research-run.schema.json",
    "tools/research_state.py",
)
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
TODO_RE = re.compile(r"\[TODO:[^\n]*]")
RUNTIME_CACHE_RE = re.compile(
    r"^tools/__pycache__/research_state\.[A-Za-z0-9_.-]+\.pyc$"
)
MANIFEST_SCHEMA = "deep-thinking-package-manifest-v1"
STATE_SCHEMA_VERSION = 4
STATE_RUN_ID_PATTERN = (
    "^(?!(?:[Cc][Oo][Nn]|[Pp][Rr][Nn]|[Aa][Uu][Xx]|[Nn][Uu][Ll]|"
    "[Cc][Oo][Mm][1-9]|[Ll][Pp][Tt][1-9])(?:[.]|$))[A-Za-z0-9]"
    "(?:[A-Za-z0-9._-]{0,78}[A-Za-z0-9_-])?$"
)
EXPECTED_DESCRIPTION = (
    "Use only when the user explicitly invokes $deep-thinking or explicitly asks to use "
    "deep-thinking. Do not activate for general analysis, research, design, tradeoffs, or "
    "task complexity. Without a mode, use standard. Reject unknown modes without fallback."
)
EXPECTED_DEFAULT_PROMPT = (
    "Use $deep-thinking standard to examine this decision with calibrated evidence and "
    "a clear conclusion."
)
STATE_REQUIRED = (
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
)
EXPECTED_INVOCATION_CONTRACT = {
    "contract": "deep-thinking-invocation-v1",
    "implicit_activation": False,
    "scope": "single_request",
    "default_mode": "standard",
    "valid_modes": ["lite", "standard", "full"],
    "invalid_mode": "reject_without_fallback",
    "routes": {
        "lite": {
            "profile": "references/profile-lite.md",
            "supplements": [],
        },
        "standard": {
            "profile": "references/profile-standard.md",
            "supplements": [],
        },
        "full": {
            "profile": "references/profile-full.md",
            "supplements": [
                "references/claim-evidence-model.md",
                "references/synthesis-stopping.md",
            ],
        },
    },
}
EXPECTED_PROFILE_CONTRACTS = {
    "lite": {
        "contract": "deep-thinking-profile-v1",
        "profile": "lite",
        "research_run": "forbidden",
        "checkpoint": "forbidden",
        "typed_terminal": "forbidden",
        "retro": "forbidden",
        "state_tool": "forbidden",
    },
    "standard": {
        "contract": "deep-thinking-profile-v1",
        "profile": "standard",
        "research_run": "forbidden",
        "checkpoint": "event_only",
        "typed_terminal": "forbidden",
        "retro": "forbidden",
        "state_tool": "forbidden",
    },
    "full": {
        "contract": "deep-thinking-profile-v1",
        "profile": "full",
        "research_run": "required",
        "checkpoint": "material_transition",
        "typed_terminal": "required",
        "retro": "trigger_only",
        "state_tool": "required",
    },
}
JSON_BLOCK_RE = re.compile(r"```json[ \t]*\n(.*?)\n```", re.DOTALL)
IMPLICIT_ACTIVATION_RE = re.compile(
    r"(?:\b(?:automatically|implicitly)\b.{0,100}\b(?:activate|load|invoke|use|escalate)\b|"
    r"\b(?:activate|load|invoke|use|escalate)\b.{0,100}"
    r"\b(?:automatically|implicitly|general analysis|general research|design|tradeoffs?|"
    r"task complexity|complex tasks?|tasks? (?:is|are) complex)\b)",
    re.IGNORECASE,
)
NEGATION_RE = re.compile(
    r"\b(?:do not|does not|must not|never|no implicit|not a default|only when explicitly)\b",
    re.IGNORECASE,
)


class ValidationError(ValueError):
    """Raised when a package violates its fixed, portable contract."""


def read_utf8(path: Path) -> tuple[bytes, str]:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValidationError(f"{path}: UTF-8 BOM is not allowed")
    try:
        return data, data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{path}: invalid UTF-8: {exc}") from exc


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def split_frontmatter(text: str, source: Path) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ValidationError(f"{source}: frontmatter must start on line one")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValidationError(f"{source}: invalid frontmatter terminator")

    fields: dict[str, str] = {}
    for line_number, line in enumerate(text[4:end].splitlines(), 2):
        match = re.fullmatch(r"([a-z][a-z-]*):[ ]*(.+)", line)
        if not match:
            raise ValidationError(f"{source}:{line_number}: expected simple key: value")
        key, value = match.groups()
        if key in fields:
            raise ValidationError(f"{source}:{line_number}: duplicate key {key!r}")
        fields[key] = unquote(value)
    return fields, text[end + 5 :]


def json_contract(text: str, source: Path, contract_name: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for raw in JSON_BLOCK_RE.findall(text):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{source}: invalid JSON contract: {exc}") from exc
        if isinstance(value, dict) and value.get("contract") == contract_name:
            matches.append(value)
    if len(matches) != 1:
        raise ValidationError(
            f"{source}: expected exactly one {contract_name} contract block"
        )
    return matches[0]


def validate_exact_tree(skill_root: Path) -> dict[str, bytes]:
    if skill_root.is_symlink():
        raise ValidationError(f"{skill_root}: skill root cannot be a symlink")
    if not skill_root.is_dir():
        raise ValidationError(f"{skill_root}: skill root is not a directory")

    files: dict[str, bytes] = {}
    for path in sorted(skill_root.rglob("*")):
        relative = path.relative_to(skill_root).as_posix()
        if path.is_symlink():
            raise ValidationError(f"{path}: symlinks are not allowed")
        if path.is_dir():
            continue
        if path.is_file() and RUNTIME_CACHE_RE.fullmatch(relative):
            continue
        if not path.is_file() or relative not in EXPECTED_FILES:
            raise ValidationError(f"{path}: file is outside the package allowlist")
        data, _ = read_utf8(path)
        files[relative] = data

    missing = sorted(set(EXPECTED_FILES) - set(files))
    if missing:
        raise ValidationError(f"missing required package files: {', '.join(missing)}")
    return files


def validate_skill_text(skill_root: Path) -> str:
    _, text = read_utf8(skill_root / "SKILL.md")
    frontmatter, body = split_frontmatter(text, skill_root / "SKILL.md")
    if set(frontmatter) != {"name", "description"}:
        raise ValidationError("SKILL.md: frontmatter must contain only name and description")

    name = frontmatter["name"]
    description = frontmatter["description"]
    if not NAME_RE.fullmatch(name) or len(name) > 64:
        raise ValidationError("SKILL.md: name must be ASCII hyphen-case and at most 64 characters")
    if name != skill_root.name or name != "deep-thinking":
        raise ValidationError("SKILL.md: name and directory must both be deep-thinking")
    if not description or len(description) > 1024 or "<" in description or ">" in description:
        raise ValidationError("SKILL.md: invalid description")
    if description != EXPECTED_DESCRIPTION:
        raise ValidationError("SKILL.md: description does not match the explicit-only contract")
    if TODO_RE.search(body):
        raise ValidationError("SKILL.md: unfinished TODO placeholder")
    if len(re.findall(r"\S+", text)) > 900:
        raise ValidationError("SKILL.md: root prompt exceeds the 900-word budget")
    contract = json_contract(
        body,
        skill_root / "SKILL.md",
        "deep-thinking-invocation-v1",
    )
    if contract != EXPECTED_INVOCATION_CONTRACT:
        raise ValidationError("SKILL.md: invocation contract does not match")
    prose = JSON_BLOCK_RE.sub("", body)
    for sentence in re.split(r"(?<=[.!?])\s+|[;\n]+", prose):
        if IMPLICIT_ACTIVATION_RE.search(sentence) and not NEGATION_RE.search(sentence):
            raise ValidationError("SKILL.md: contains an implicit activation rule")
        if re.search(
            r"\b(?:use|load|select)\s+(?:the\s+)?Full\s+profile\s+for\s+(?:Lite|Standard)\b",
            sentence, re.IGNORECASE,
        ) and not NEGATION_RE.search(sentence):
            raise ValidationError("SKILL.md: contains a contradictory Full profile route")
    expected_routes = {
        "Lite": "references/profile-lite.md",
        "Standard": "references/profile-standard.md",
        "Full": "references/profile-full.md",
    }
    for label, target in expected_routes.items():
        matches = re.findall(
            rf"(?m)^- {label}: \[[^\]]+]\(([^)]+)\)",
            body,
        )
        if matches != [target]:
            raise ValidationError(f"SKILL.md: {label} route must target {target}")
    return name


def validate_openai_yaml(path: Path, skill_name: str) -> None:
    _, text = read_utf8(path)
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        section = re.fullmatch(r"([a-z_]+):", line)
        if section:
            name = section.group(1)
            if name in sections:
                raise ValidationError(f"{path}:{line_number}: duplicate section {name!r}")
            current = {}
            sections[name] = current
            continue
        field = re.fullmatch(r"  ([a-z_]+):[ ]*(.+)", line)
        if current is None or not field:
            raise ValidationError(f"{path}:{line_number}: expected a supported YAML mapping")
        key, value = field.groups()
        if key in current:
            raise ValidationError(f"{path}:{line_number}: duplicate field {key!r}")
        current[key] = unquote(value)

    required = {"display_name", "short_description", "default_prompt"}
    if set(sections) != {"interface", "policy"}:
        raise ValidationError(f"{path}: only interface and policy mappings are allowed")
    fields = sections["interface"]
    if set(fields) != required or not all(fields.values()):
        raise ValidationError(f"{path}: interface must contain exactly {', '.join(sorted(required))}")
    if fields["default_prompt"] != EXPECTED_DEFAULT_PROMPT:
        raise ValidationError(f"{path}: default_prompt does not match the explicit invocation contract")
    if sections["policy"] != {"allow_implicit_invocation": "false"}:
        raise ValidationError(f"{path}: policy must disable implicit invocation")


def validate_links(skill_root: Path) -> None:
    root = skill_root.resolve()
    for source in sorted(skill_root.rglob("*.md")):
        _, text = read_utf8(source)
        for match in MARKDOWN_LINK_RE.finditer(text):
            target_text = match.group(1).strip().split(maxsplit=1)[0].strip("<>")
            if not target_text or target_text.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = (source.parent / target_text.split("#", 1)[0]).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise ValidationError(f"{source}: link escapes Skill root: {target_text}") from exc
            if not target.is_file():
                raise ValidationError(f"{source}: broken local link: {target_text}")
            if source.name == "SKILL.md":
                parts = Path(target_text.split("#", 1)[0]).parts
                if len(parts) != 2 or parts[0] != "references":
                    raise ValidationError(
                        f"{source}: local references must use references/<file>: {target_text}"
                    )


def validate_profile_contracts(skill_root: Path) -> None:
    _, lite = read_utf8(skill_root / "references" / "profile-lite.md")
    _, standard = read_utf8(skill_root / "references" / "profile-standard.md")
    _, full = read_utf8(skill_root / "references" / "profile-full.md")
    required = {
        "Lite": (
            "prompt-only",
            "must not create persistent state",
            "must not require tool-call classification",
            "must not require Checkpoints",
            "must not require Retro",
            "must not refuse a solvable task",
        ),
        "Standard": (
            "judgment materially changes",
            "hypothesis set changes",
            "not actually independent",
            "counterevidence",
            "compression, pause, handoff, or multi-agent synthesis",
            "scope, cost, or external side effect",
            "must not require a Checkpoint per batch",
            "must not classify every tool call",
        ),
        "Full": (
            "only by an explicit `$deep-thinking full` invocation",
            "Material Epistemic Transition",
            "Research Mandate",
            "research_state.py",
            "--state-dir",
            "`validate`",
            "single writer",
            "research run is busy",
            "answered",
            "conditionally_answered",
            "unresolved_evidence_limit",
            "blocked_access",
            "stopped_budget",
            "invalidated_question",
        ),
    }
    forbidden = {
        "Lite": (
            "must create persistent state",
            "must require Checkpoints",
            "must require Retro",
            "must classify every tool call",
        ),
        "Standard": (
            "must require a Checkpoint per batch",
            "must classify every tool call",
            "must request epistemic authorization per batch",
            "must require Retro for every terminal",
        ),
        "Full": (
            "Multiple writers may update the same Research Run.",
            "Concurrent writes may wait, retry, or overwrite another update.",
            "Remove the lock without confirming that no writer is active.",
        ),
    }
    for profile, text in (("Lite", lite), ("Standard", standard), ("Full", full)):
        contract = json_contract(
            text,
            skill_root / "references" / f"profile-{profile.casefold()}.md",
            "deep-thinking-profile-v1",
        )
        if contract != EXPECTED_PROFILE_CONTRACTS[profile.casefold()]:
            raise ValidationError(
                f"references/profile-{profile.casefold()}.md: capability contract does not match"
            )
        for phrase in required[profile]:
            if phrase not in text:
                raise ValidationError(
                    f"references/profile-{profile.casefold()}.md: missing {phrase!r}"
                )
        for phrase in forbidden.get(profile, ()):
            if phrase in text:
                raise ValidationError(
                    f"references/profile-{profile.casefold()}.md: contradictory obligation {phrase!r}"
                )
    prose = {
        name: JSON_BLOCK_RE.sub("", text)
        for name, text in (("Lite", lite), ("Standard", standard))
    }
    positive_durable_state = re.compile(
        r"\b(?:create|write|persist|maintain|record|initialize)\b.{0,100}"
        r"\b(?:durable|persistent|research run|state file|state machine|json)\b|"
        r"\b(?:research run|state file|state machine|durable state|persistent state)\b"
        r"\s+(?:is|are)\s+(?:required|mandatory)\b",
        re.IGNORECASE,
    )
    for profile, text in prose.items():
        for sentence in re.split(r"(?<=[.!?])\s+|[;\n]+", text):
            if positive_durable_state.search(sentence) and not NEGATION_RE.search(sentence):
                raise ValidationError(
                    f"references/profile-{profile.casefold()}.md: "
                    "contains a positive durable-state obligation"
                )


def validate_schema(path: Path) -> None:
    _, text = read_utf8(path)
    try:
        schema = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON Schema: {exc}") from exc
    if not isinstance(schema, dict):
        raise ValidationError(f"{path}: JSON Schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ValidationError(f"{path}: must declare JSON Schema draft 2020-12")
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        raise ValidationError(f"{path}: root must be a strict object")
    if tuple(schema.get("required", ())) != STATE_REQUIRED:
        raise ValidationError(f"{path}: root required fields do not match the research-run contract")
    properties = schema.get("properties")
    definitions = schema.get("$defs")
    if not isinstance(properties, dict) or set(properties) != set(STATE_REQUIRED):
        raise ValidationError(f"{path}: root properties do not match the research-run contract")
    required_defs = {
        "non_empty_text",
        "activation",
        "mandate",
        "claim",
        "hypothesis",
        "evidence",
        "independence_group",
        "transition",
        "checkpoint",
        "working_set",
        "terminal",
        "restart_condition",
        "retro",
        "research",
    }
    if not isinstance(definitions, dict) or set(definitions) != required_defs:
        raise ValidationError(f"{path}: state definitions do not match the contract")

    collection_refs = {
        "claims": "claim",
        "hypotheses": "hypothesis",
        "evidence": "evidence",
        "independence_groups": "independence_group",
        "transitions": "transition",
        "checkpoints": "checkpoint",
        "retro": "retro",
    }
    for collection, definition in collection_refs.items():
        if properties[collection] != {
            "type": "array",
            "items": {"$ref": f"#/$defs/{definition}"},
        }:
            raise ValidationError(f"{path}: {collection} item validation is weakened")

    object_fields = {
        "activation": {"profile", "invocation_id", "started_at"},
        "research": {"question", "decision_goal", "mandate"},
        "mandate": {"scope", "cost_boundary", "external_effects"},
        "claim": {"id", "kind", "text"},
        "hypothesis": {"id", "summary", "status"},
        "evidence": {"id", "source", "source_group", "effect"},
        "independence_group": {"id", "sources"},
        "transition": {"id", "kind", "summary", "judgment", "changes", "at"},
        "checkpoint": {
            "id",
            "transition_id",
            "judgment",
            "next_action",
            "risk_level",
            "working_set",
            "at",
        },
        "working_set": {
            "claims",
            "hypotheses",
            "evidence",
            "independence_groups",
        },
        "terminal": {"status", "judgment", "restart_condition", "at"},
        "restart_condition": {"event_type", "subject", "observable_condition"},
        "retro": {"trigger", "note", "at"},
    }
    for definition, fields in object_fields.items():
        value = definitions[definition]
        if (
            not isinstance(value, dict)
            or value.get("type") != "object"
            or value.get("additionalProperties") is not False
            or set(value.get("required", ())) != fields
            or not isinstance(value.get("properties"), dict)
            or set(value["properties"]) != fields
        ):
            raise ValidationError(f"{path}: {definition} must remain a closed required record")

    text_ref = {"$ref": "#/$defs/non_empty_text"}
    date_time = {"type": "string", "format": "date-time"}
    root_nodes = {
        "schema_version": {"const": STATE_SCHEMA_VERSION},
        "run_id": {
            "type": "string",
            "pattern": STATE_RUN_ID_PATTERN,
        },
        "created_at": date_time,
        "updated_at": date_time,
        "activation": {"$ref": "#/$defs/activation"},
        "research": {"$ref": "#/$defs/research"},
        "current_judgment": {"anyOf": [text_ref, {"type": "null"}]},
        "terminal": {
            "anyOf": [{"$ref": "#/$defs/terminal"}, {"type": "null"}]
        },
    }
    for field, expected in root_nodes.items():
        if properties[field] != expected:
            raise ValidationError(f"{path}: root {field} validation is weakened")
    if definitions["non_empty_text"] != {"type": "string", "minLength": 1}:
        raise ValidationError(f"{path}: non_empty_text validation is weakened")

    field_nodes = {
        ("activation", "profile"): {"const": "full"},
        ("activation", "invocation_id"): {
            "type": "string",
            "pattern": STATE_RUN_ID_PATTERN,
        },
        ("activation", "started_at"): date_time,
        ("research", "question"): text_ref,
        ("research", "decision_goal"): text_ref,
        ("research", "mandate"): {"$ref": "#/$defs/mandate"},
        ("mandate", "scope"): text_ref,
        ("mandate", "cost_boundary"): {
            "anyOf": [text_ref, {"type": "null"}]
        },
        ("mandate", "external_effects"): {"type": "boolean"},
        ("claim", "id"): text_ref,
        ("claim", "text"): text_ref,
        ("hypothesis", "id"): text_ref,
        ("hypothesis", "summary"): text_ref,
        ("evidence", "id"): text_ref,
        ("evidence", "source"): text_ref,
        ("evidence", "source_group"): text_ref,
        ("independence_group", "id"): text_ref,
        ("independence_group", "sources"): {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": text_ref,
        },
        ("transition", "id"): {
            "type": "string",
            "pattern": "^met-[0-9]{4}$",
        },
        ("transition", "summary"): text_ref,
        ("transition", "judgment"): text_ref,
        ("transition", "changes"): {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {
                "enum": [
                    "claims",
                    "hypotheses",
                    "evidence",
                    "independence_groups",
                    "judgment",
                    "next_action",
                    "risk_level",
                ]
            },
        },
        ("transition", "at"): date_time,
        ("checkpoint", "id"): {
            "type": "string",
            "pattern": "^checkpoint-[0-9]{4}$",
        },
        ("checkpoint", "transition_id"): {
            "type": "string",
            "pattern": "^met-[0-9]{4}$",
        },
        ("checkpoint", "judgment"): text_ref,
        ("checkpoint", "next_action"): text_ref,
        ("checkpoint", "working_set"): {"$ref": "#/$defs/working_set"},
        ("checkpoint", "at"): date_time,
        ("terminal", "judgment"): text_ref,
        ("terminal", "restart_condition"): {
            "anyOf": [{"$ref": "#/$defs/restart_condition"}, {"type": "null"}]
        },
        ("terminal", "at"): date_time,
        ("restart_condition", "subject"): text_ref,
        ("restart_condition", "observable_condition"): text_ref,
        ("retro", "note"): text_ref,
        ("retro", "at"): date_time,
    }
    for (definition, field), expected in field_nodes.items():
        if definitions[definition]["properties"][field] != expected:
            raise ValidationError(f"{path}: {definition}.{field} validation is weakened")
    for field, definition in {
        "claims": "claim",
        "hypotheses": "hypothesis",
        "evidence": "evidence",
        "independence_groups": "independence_group",
    }.items():
        if definitions["working_set"]["properties"][field] != {
            "type": "array",
            "items": {"$ref": f"#/$defs/{definition}"},
        }:
            raise ValidationError(
                f"{path}: working_set.{field} item validation is weakened"
            )

    enum_contracts = {
        ("claim", "kind"): [
            "verified_fact",
            "user_claim",
            "inference",
            "assumption",
            "unknown",
        ],
        ("hypothesis", "status"): ["active", "eliminated"],
        ("evidence", "effect"): ["support", "weaken", "no_effect"],
        ("transition", "kind"): [
            "hypothesis_added",
            "hypothesis_eliminated",
            "evidence_changed_judgment",
            "evidence_independence_changed",
            "unknown_resolved",
            "risk_or_action_changed",
        ],
        ("checkpoint", "risk_level"): ["low", "medium", "high"],
        ("terminal", "status"): [
            "answered",
            "conditionally_answered",
            "unresolved_evidence_limit",
            "blocked_access",
            "stopped_budget",
            "invalidated_question",
        ],
        ("retro", "trigger"): [
            "major_reversal",
            "user_found_error",
            "source_invalidated",
            "evaluator_disagreement",
            "protocol_exception",
            "abnormal_stop",
            "high_impact_error",
            "method_to_preserve",
        ],
        ("restart_condition", "event_type"): [
            "access_granted",
            "budget_restored",
            "constraint_changed",
            "dependency_completed",
            "evidence_published",
        ],
    }
    for (definition, field), expected in enum_contracts.items():
        if definitions[definition]["properties"][field] != {"enum": expected}:
            raise ValidationError(f"{path}: {definition}.{field} enum does not match the contract")

    expected_terminal_rule = [
        {
            "if": {
                "properties": {
                    "status": {
                        "enum": [
                            "unresolved_evidence_limit",
                            "blocked_access",
                            "stopped_budget",
                        ]
                    }
                }
            },
            "then": {
                "properties": {
                    "restart_condition": {"$ref": "#/$defs/restart_condition"}
                }
            },
        }
    ]
    if definitions["terminal"].get("allOf") != expected_terminal_rule:
        raise ValidationError(f"{path}: terminal restart condition rule is weakened")


def combined_hash(items: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for relative, data in sorted(items):
        encoded_path = relative.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def fingerprint(files: dict[str, bytes]) -> dict[str, object]:
    file_entries = [
        {"path": relative, "size": len(data), "sha256": sha256(data)}
        for relative, data in sorted(files.items())
    ]
    instruction_items = [
        (relative, data)
        for relative, data in files.items()
        if relative == "SKILL.md" or relative.startswith("references/")
    ]
    return {
        "instruction_hash": combined_hash(instruction_items),
        "adapter_hash": sha256(files["agents/openai.yaml"]),
        "artifact_tree_hash": combined_hash(list(files.items())),
        "files": file_entries,
    }


def build_manifest(files: dict[str, bytes]) -> dict[str, object]:
    return {"schema": MANIFEST_SCHEMA, **fingerprint(files)}


def load_manifest(path: Path) -> dict[str, object]:
    _, text = read_utf8(path)
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"expected manifest is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValidationError("expected manifest must be a JSON object")
    required = {"schema", "instruction_hash", "adapter_hash", "artifact_tree_hash", "files"}
    if set(manifest) != required or manifest["schema"] != MANIFEST_SCHEMA:
        raise ValidationError("expected manifest has an unsupported schema")
    for key in ("instruction_hash", "adapter_hash", "artifact_tree_hash"):
        if not isinstance(manifest[key], str) or not SHA256_RE.fullmatch(manifest[key]):
            raise ValidationError(f"expected manifest {key} must be a SHA-256 hex digest")

    entries = manifest["files"]
    if not isinstance(entries, list):
        raise ValidationError("expected manifest files must be a list")
    paths: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "size", "sha256"}:
            raise ValidationError("expected manifest has an invalid file entry")
        if (
            not isinstance(entry["path"], str)
            or type(entry["size"]) is not int
            or not isinstance(entry["sha256"], str)
            or not SHA256_RE.fullmatch(entry["sha256"])
        ):
            raise ValidationError("expected manifest has an invalid file entry")
        paths.append(entry["path"])
    if paths != sorted(EXPECTED_FILES):
        raise ValidationError("expected manifest files must match the package allowlist")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_dir", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--manifest-out", type=Path)
    group.add_argument("--verify-manifest", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.skill_dir.is_symlink():
            raise ValidationError(f"{args.skill_dir}: skill root cannot be a symlink")
        skill_root = args.skill_dir.resolve()
        files = validate_exact_tree(skill_root)
        skill_name = validate_skill_text(skill_root)
        validate_openai_yaml(skill_root / "agents/openai.yaml", skill_name)
        validate_links(skill_root)
        validate_profile_contracts(skill_root)
        validate_schema(skill_root / "schemas/research-run.schema.json")

        actual = fingerprint(files)
        if args.verify_manifest:
            expected = load_manifest(args.verify_manifest.resolve())
            if any(actual[key] != expected[key] for key in actual):
                raise ValidationError("package does not match expected manifest")
            result = {"schema": "deep-thinking-package-verification-v1", "verified": True, **actual}
        else:
            result = build_manifest(files)
            if args.manifest_out:
                args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
                args.manifest_out.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return 0
    except (OSError, ValidationError) as exc:
        print(f"package validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
