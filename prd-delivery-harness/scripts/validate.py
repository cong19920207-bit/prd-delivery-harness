#!/usr/bin/env python3
"""Validate the small, fixed contract used by prd-delivery-harness."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable


OUTCOMES = {"PASS", "PASS_WITH_RISKS", "DOCUMENT_ONLY", "BLOCKED", "FAILED_VALIDATION"}
STATES = {
    "INPUT_READY",
    "PRD_READY",
    "PRD_DOCUMENT_ONLY",
    "STEPS_DRAFTED",
    "PROVISIONAL_STEPS_READY",
    "STEPS_VERIFIED",
    "IMPLEMENTATION_PLAN_READY",
}
PHASE_ORDER = (
    "prd-review",
    "prd-to-steps",
    "step-doc-review",
    "milestone-step-execution",
)
PHASES = {"initialization", "final", *PHASE_ORDER}
STEP_STATES = {
    "STEPS_DRAFTED",
    "PROVISIONAL_STEPS_READY",
    "STEPS_VERIFIED",
    "IMPLEMENTATION_PLAN_READY",
}
FORMAL_STATES = {"STEPS_VERIFIED", "IMPLEMENTATION_PLAN_READY"}
SOURCE_TYPES = {"USER_DECISION", "PRD", "CONTRACT", "REPO_BASELINE", "RUNTIME"}
EVIDENCE_SOURCES = {*SOURCE_TYPES, "PLANNED", "UNVERIFIED"}
REQUIREMENT_SOURCES = {"USER_DECISION", "PRD", "CONTRACT"}
REFERENCE_STATUSES = {"existing", "planned", "unverified"}
REFERENCE_KINDS = {"path", "symbol", "contract"}
EXISTING_SOURCES = {"CONTRACT", "REPO_BASELINE", "RUNTIME"}
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
ARTIFACT_META = re.compile(r"^<!-- prd-delivery-harness-meta (\{.*\}) -->$")
GENERIC_LOCATORS = {
    "class",
    "const",
    "def",
    "for",
    "from",
    "function",
    "if",
    "import",
    "let",
    "return",
    "var",
    "while",
}

ARTIFACT_RULES = {
    "requirements_ledger": ("requirements-ledger.md", "requirements_ledger", "prd-review"),
    "steps_draft": ("steps-draft.md", "step_draft", "prd-to-steps"),
    "steps_provisional": ("steps-provisional.md", "step_provisional", "prd-to-steps"),
    "step_audit": ("step-audit.md", "step_audit", "step-doc-review"),
    "steps_verified": ("steps-verified.md", "step_verified", "step-doc-review"),
    "execution_plan": ("execution-plan.md", "execution_plan", "milestone-step-execution"),
    "decision_addendum": ("decision-addendum.md", "decision_addendum", "initialization"),
    "run": ("run.json", "run_index", "final"),
}

STAGE_RULES = {
    "prd-review": {
        "from": {"INPUT_READY"},
        "success_state": "PRD_READY",
        "success_artifacts": {"requirements_ledger"},
        "document_state": "PRD_DOCUMENT_ONLY",
        "document_artifacts": {"requirements_ledger"},
        "stop_artifacts": {"requirements_ledger"},
    },
    "prd-to-steps": {
        "from": {"PRD_READY", "PRD_DOCUMENT_ONLY"},
        "success_state": "STEPS_DRAFTED",
        "success_artifacts": {"steps_draft"},
        "document_state": "PROVISIONAL_STEPS_READY",
        "document_artifacts": {"steps_provisional"},
        "stop_artifacts": {"steps_draft", "steps_provisional"},
    },
    "step-doc-review": {
        "from": {"STEPS_DRAFTED"},
        "success_state": "STEPS_VERIFIED",
        "success_artifacts": {"step_audit", "steps_verified"},
        "stop_artifacts": {"step_audit"},
    },
    "milestone-step-execution": {
        "from": {"STEPS_VERIFIED"},
        "success_state": "IMPLEMENTATION_PLAN_READY",
        "success_artifacts": {"execution_plan"},
        "stop_artifacts": {"execution_plan"},
    },
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: str = ""


def _issue(issues: list[ValidationIssue], code: str, message: str, path: str = "") -> None:
    issues.append(ValidationIssue(code, message, path))


def _records(value: Any, name: str, issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _issue(issues, f"E_{name.upper()}_TYPE", f"{name} must be a list", name)
        return []
    records: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, dict):
            records.append(item)
        else:
            _issue(issues, f"E_{name.upper()}_ITEM_TYPE", f"{name} item must be an object", f"{name}[{index}]")
    return records


def _ids(
    records: Iterable[dict[str, Any]],
    name: str,
    duplicate_code: str,
    issues: list[ValidationIssue],
) -> set[str]:
    values: list[str] = []
    for index, record in enumerate(records):
        value = record.get("id")
        if isinstance(value, str) and value.strip():
            values.append(value)
        else:
            _issue(issues, f"E_{name.upper()}_ID_MISSING", f"{name} id is required", f"{name}[{index}].id")
    for value, count in Counter(values).items():
        if count > 1:
            _issue(issues, duplicate_code, f"duplicate {name} id: {value}")
    return set(values)


def _resolve(run_path: Path, value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else run_path.parent / path).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_line(source: dict[str, Any]) -> str:
    return f'{source["id"]}\t{source["source"]}\t{source["sha256"]}'


def _manifest_digest(lines: Iterable[str]) -> str:
    return hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def _validate_sources(
    data: dict[str, Any], issues: list[ValidationIssue], run_path: Path | None
) -> dict[str, dict[str, Any]]:
    current = data.get("source_digest")
    validated = data.get("validated_source_digest")
    if not isinstance(current, str) or not HEX_64.fullmatch(current):
        _issue(issues, "E_SOURCE_DIGEST_INVALID", "source_digest must be lowercase SHA-256")
    if not isinstance(validated, str) or not HEX_64.fullmatch(validated):
        _issue(issues, "E_VALIDATED_SOURCE_DIGEST_INVALID", "validated_source_digest must be lowercase SHA-256")
    if isinstance(current, str) and isinstance(validated, str) and current != validated:
        _issue(issues, "E_SOURCE_DIGEST_MISMATCH", "source changed after validation")

    raw = data.get("source_manifest")
    if not isinstance(raw, list):
        _issue(issues, "E_SOURCE_MANIFEST_TYPE", "source_manifest must be a non-empty list")
        return {}
    if not raw:
        _issue(issues, "E_SOURCE_MANIFEST_EMPTY", "source_manifest must not be empty")
        return {}

    entries: dict[str, dict[str, Any]] = {}
    lines: list[str] = []
    ids: list[str] = []
    for index, item in enumerate(raw):
        path = f"source_manifest[{index}]"
        if not isinstance(item, dict):
            _issue(issues, "E_SOURCE_MANIFEST_ITEM_TYPE", "source entry must be an object", path)
            continue
        source_id = item.get("id")
        source_type = item.get("source")
        digest = item.get("sha256")
        source_path = item.get("path")
        valid = True
        if not isinstance(source_id, str) or not source_id.strip():
            _issue(issues, "E_SOURCE_ID_MISSING", "source id is required", f"{path}.id")
            valid = False
        else:
            ids.append(source_id)
            entries[source_id] = item
        if source_type not in SOURCE_TYPES:
            _issue(issues, "E_SOURCE_MANIFEST_SOURCE_INVALID", "invalid source type", f"{path}.source")
            valid = False
        if not isinstance(digest, str) or not HEX_64.fullmatch(digest):
            _issue(issues, "E_SOURCE_FILE_DIGEST_INVALID", "source sha256 is invalid", f"{path}.sha256")
            valid = False
        if not isinstance(source_path, str) or not source_path.strip():
            _issue(issues, "E_SOURCE_PATH_INVALID", "source path is required", f"{path}.path")
            valid = False
        elif run_path is not None:
            resolved = _resolve(run_path, source_path)
            if not resolved.is_file():
                _issue(issues, "E_SOURCE_FILE_NOT_FOUND", f"source not found: {source_path}", f"{path}.path")
            elif isinstance(digest, str) and HEX_64.fullmatch(digest):
                try:
                    actual = _sha256(resolved)
                except OSError as exc:
                    _issue(issues, "E_SOURCE_FILE_READ", str(exc), f"{path}.path")
                else:
                    if actual != digest:
                        _issue(issues, "E_SOURCE_FILE_DIGEST_MISMATCH", f"source changed: {source_path}", f"{path}.sha256")
        if valid:
            lines.append(_tree_line(item))

    for source_id, count in Counter(ids).items():
        if count > 1:
            _issue(issues, "E_SOURCE_ID_DUPLICATE", f"duplicate source id: {source_id}")
    computed = _manifest_digest(lines)
    if isinstance(current, str) and HEX_64.fullmatch(current) and current != computed:
        _issue(issues, "E_SOURCE_DIGEST_CONTENT_MISMATCH", "source_digest does not match source_manifest")
    return entries


def _artifact_entries(data: dict[str, Any], issues: list[ValidationIssue]) -> dict[str, dict[str, Any]]:
    raw = data.get("artifacts")
    if not isinstance(raw, dict):
        _issue(issues, "E_ARTIFACTS_TYPE", "artifacts must be an object")
        return {}
    entries: dict[str, dict[str, Any]] = {}
    for key, entry in raw.items():
        path = f"artifacts.{key}"
        if not isinstance(entry, dict):
            _issue(issues, "E_ARTIFACT_ENTRY_TYPE", "artifact entry must be an object", path)
            continue
        if key not in ARTIFACT_RULES:
            _issue(issues, "E_ARTIFACT_KEY_INVALID", f"unknown artifact: {key}", path)
            continue
        entries[key] = entry
        expected_name, expected_role, _ = ARTIFACT_RULES[key]
        value = entry.get("path")
        if not isinstance(value, str) or not value.strip():
            _issue(issues, "E_ARTIFACT_PATH_INVALID", "artifact path is required", f"{path}.path")
        elif Path(value).name != expected_name:
            _issue(issues, "E_ARTIFACT_NAME_INVALID", f"artifact must be named {expected_name}", f"{path}.path")
        if entry.get("role") != expected_role:
            _issue(issues, "E_ARTIFACT_ROLE_INVALID", f"artifact role must be {expected_role}", f"{path}.role")
        if key != "run":
            digest = entry.get("sha256")
            if not isinstance(digest, str) or not HEX_64.fullmatch(digest):
                _issue(issues, "E_ARTIFACT_DIGEST_INVALID", "artifact sha256 is invalid", f"{path}.sha256")
    if "run" not in entries:
        _issue(issues, "E_ARTIFACT_REQUIRED", "run artifact is required", "artifacts.run")
    if data.get("state") == "PROVISIONAL_STEPS_READY":
        for key in {"steps_draft", "step_audit", "steps_verified", "execution_plan"} & set(raw):
            _issue(issues, "E_PROVISIONAL_ARTIFACT", f"provisional run cannot contain {key}", f"artifacts.{key}")
    return entries


def _validate_stages(
    data: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    issues: list[ValidationIssue],
) -> dict[str, dict[str, Any]]:
    phase = data.get("phase")
    if phase not in PHASES:
        _issue(issues, "E_PHASE_INVALID", f"invalid phase: {phase!r}")
    raw = data.get("stage_results")
    results = _records(raw, "stage_results", issues)
    if isinstance(raw, list) and not results:
        if not (data.get("state") == "INPUT_READY" and phase == "initialization"):
            _issue(issues, "E_STAGE_RESULTS_EMPTY", "terminal run requires stage_results")
        return {}
    if not results:
        return {}

    by_phase: dict[str, dict[str, Any]] = {}
    claimed: list[str] = []
    previous_state = "INPUT_READY"
    observed: list[str] = []
    stopped = False
    for index, result in enumerate(results):
        location = f"stage_results[{index}]"
        result_phase = result.get("phase")
        if result_phase not in STAGE_RULES:
            _issue(issues, "E_STAGE_PHASE_INVALID", "invalid stage phase", location)
            continue
        observed.append(result_phase)
        if observed != list(PHASE_ORDER[: len(observed)]):
            _issue(issues, "E_STAGE_ORDER", "stage_results must be a fixed-order prefix", location)
        if result_phase in by_phase:
            _issue(issues, "E_STAGE_ORDER", "stage phase may appear only once", location)
        by_phase[result_phase] = result
        rule = STAGE_RULES[result_phase]
        result_state = result.get("state")
        result_outcome = result.get("outcome")
        if result_state not in STATES:
            _issue(issues, "E_STAGE_STATE_INVALID", "invalid stage state", location)
        if result_outcome not in OUTCOMES:
            _issue(issues, "E_STAGE_OUTCOME_INVALID", "invalid stage outcome", location)
        if previous_state not in rule["from"]:
            _issue(issues, "E_STAGE_PREDECESSOR", f"{result_phase} cannot start from {previous_state}", location)
        if result.get("source_digest") != data.get("source_digest"):
            _issue(issues, "E_STAGE_SOURCE_DIGEST_MISMATCH", "stage source digest mismatch", location)

        keys = result.get("artifact_keys")
        if not isinstance(keys, list) or not all(isinstance(item, str) for item in keys):
            _issue(issues, "E_STAGE_ARTIFACT_KEYS_TYPE", "artifact_keys must be a string list", location)
            keys = []
        if len(keys) != len(set(keys)):
            _issue(issues, "E_STAGE_ARTIFACT_DUPLICATE", "artifact key repeated in stage", location)
        key_set = set(keys)
        claimed.extend(keys)
        for key in key_set - set(artifacts):
            _issue(issues, "E_STAGE_ARTIFACT_UNKNOWN", f"stage references unknown artifact: {key}", location)

        if result_outcome in {"PASS", "PASS_WITH_RISKS"}:
            expected_state = rule["success_state"]
            expected_keys = rule["success_artifacts"]
        elif result_outcome == "DOCUMENT_ONLY":
            expected_state = rule.get("document_state")
            expected_keys = rule.get("document_artifacts", set())
            if expected_state is None:
                _issue(issues, "E_STAGE_TRANSITION", "DOCUMENT_ONLY is not valid for this phase", location)
        else:
            expected_state = previous_state
            expected_keys = key_set
            if not key_set <= rule["stop_artifacts"]:
                _issue(issues, "E_STAGE_ARTIFACT_FORBIDDEN", "stopping stage claims a forbidden artifact", location)
            if result_state != previous_state:
                _issue(issues, "E_STAGE_STOP_STATE", "stopping stage must retain its predecessor state", location)
            stopped = True
            if index != len(results) - 1:
                _issue(issues, "E_STAGE_AFTER_STOP", "no stage may follow a stopping result", location)

        if result_state != expected_state:
            _issue(issues, "E_STAGE_TRANSITION", f"stage must end in {expected_state}", location)
        if key_set != expected_keys:
            code = "E_STAGE_ARTIFACT_FORBIDDEN" if key_set - expected_keys else "E_STAGE_ARTIFACT_REQUIRED"
            _issue(issues, code, f"stage artifacts must be {sorted(expected_keys)}", location)
        previous_state = result_state if isinstance(result_state, str) else previous_state

    for key, count in Counter(claimed).items():
        if count > 1:
            _issue(issues, "E_STAGE_ARTIFACT_DUPLICATE", f"artifact claimed by multiple stages: {key}")
    indexed = set(artifacts) - {"run", "decision_addendum"}
    if indexed != set(claimed):
        for key in sorted(indexed - set(claimed)):
            _issue(issues, "E_STAGE_ARTIFACT_UNCLAIMED", f"artifact not claimed by a stage: {key}")
        for key in sorted(set(claimed) - indexed):
            _issue(issues, "E_STAGE_ARTIFACT_UNKNOWN", f"claimed artifact is not indexed: {key}")

    state = data.get("state")
    outcome = data.get("outcome")
    last = results[-1]
    if state == "IMPLEMENTATION_PLAN_READY":
        if observed != list(PHASE_ORDER) or stopped:
            _issue(issues, "E_STAGE_SEQUENCE_INCOMPLETE", "formal plan requires four successful stages")
        expected_outcome = (
            "PASS_WITH_RISKS"
            if any(item.get("outcome") == "PASS_WITH_RISKS" for item in results)
            else "PASS"
        )
        if phase != "final" or outcome != expected_outcome:
            _issue(issues, "E_PHASE_STATE_MISMATCH", "formal top-level phase/outcome mismatch")
    elif state == "PROVISIONAL_STEPS_READY":
        if observed != list(PHASE_ORDER[:2]) or any(item.get("outcome") != "DOCUMENT_ONLY" for item in results):
            _issue(issues, "E_STAGE_SEQUENCE_INCOMPLETE", "provisional path requires two DOCUMENT_ONLY stages")
        if phase != "prd-to-steps" or outcome != "DOCUMENT_ONLY":
            _issue(issues, "E_PHASE_STATE_MISMATCH", "provisional top-level fields mismatch")
    elif last.get("outcome") in {"BLOCKED", "FAILED_VALIDATION"}:
        if phase != last.get("phase") or state != last.get("state") or outcome != last.get("outcome"):
            _issue(issues, "E_PHASE_STATE_MISMATCH", "stopped top-level fields must match the last stage")
    elif phase != last.get("phase") or state != last.get("state") or outcome != last.get("outcome"):
        _issue(issues, "E_PHASE_STATE_MISMATCH", "top-level fields must match the last completed stage")
    return by_phase


def _stage_summary(phase: str, state: str, outcome: str) -> str:
    return f"> Harness: phase={phase}; state={state}; outcome={outcome}; code_status=NOT_STARTED"


def _validate_artifact_files(
    data: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    stages: dict[str, dict[str, Any]],
    issues: list[ValidationIssue],
    run_path: Path | None,
) -> None:
    if run_path is None:
        return
    run_dir = run_path.parent.resolve()
    resolved: dict[str, Path] = {}
    for key, entry in artifacts.items():
        value = entry.get("path")
        if not isinstance(value, str) or not value.strip():
            continue
        path = _resolve(run_path, value)
        resolved[key] = path
        if path.parent != run_dir:
            _issue(issues, "E_ARTIFACT_OUTSIDE_RUN_DIR", "artifact must be a direct child of run directory", f"artifacts.{key}")
        if not path.is_file():
            _issue(issues, "E_ARTIFACT_NOT_FOUND", f"artifact not found: {value}", f"artifacts.{key}")
            continue
        if key == "run":
            continue
        try:
            content = path.read_text(encoding="utf-8")
            actual = _sha256(path)
        except (OSError, UnicodeDecodeError) as exc:
            _issue(issues, "E_ARTIFACT_READ", str(exc), f"artifacts.{key}")
            continue
        if actual != entry.get("sha256"):
            _issue(issues, "E_ARTIFACT_DIGEST_MISMATCH", f"artifact changed: {value}", f"artifacts.{key}.sha256")

        lines = content.splitlines()
        first = next((line.strip() for line in lines if line.strip()), "")
        match = ARTIFACT_META.fullmatch(first)
        if not match:
            _issue(issues, "E_ARTIFACT_METADATA_MISSING", "artifact metadata comment is required", f"artifacts.{key}")
            continue
        try:
            metadata = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            _issue(issues, "E_ARTIFACT_METADATA_JSON", str(exc), f"artifacts.{key}")
            continue
        if not isinstance(metadata, dict):
            _issue(issues, "E_ARTIFACT_METADATA_TYPE", "artifact metadata must be an object", f"artifacts.{key}")
            continue
        owner = ARTIFACT_RULES[key][2]
        stage = stages.get(owner)
        expected = {
            "schema_version": 2,
            "run_id": data.get("run_id"),
            "artifact": key,
            "owner_phase": owner,
            "source_digest": data.get("source_digest"),
            "code_status": "NOT_STARTED",
            "state": stage.get("state") if stage else data.get("state"),
            "outcome": stage.get("outcome") if stage else data.get("outcome"),
        }
        for field, expected_value in expected.items():
            if metadata.get(field) != expected_value:
                _issue(issues, "E_ARTIFACT_METADATA_MISMATCH", f"metadata {field} mismatch", f"artifacts.{key}")
        body = "\n".join(lines[1:])
        if not re.search(r"(?m)^#\s+\S", body):
            _issue(issues, "E_ARTIFACT_BODY_INVALID", "artifact needs a Markdown heading", f"artifacts.{key}")
        summary = _stage_summary(owner, str(expected["state"]), str(expected["outcome"]))
        if summary not in body:
            _issue(issues, "E_ARTIFACT_STAGE_TOKEN_MISSING", "artifact stage summary does not match run.json", f"artifacts.{key}")

    for path, count in Counter(resolved.values()).items():
        if count > 1:
            _issue(issues, "E_ARTIFACT_PATH_DUPLICATE", f"multiple artifacts use {path}")
    if resolved.get("run") != run_path.resolve():
        _issue(issues, "E_RUN_ARTIFACT_MISMATCH", "artifacts.run must identify this run.json")


def _validate_dependencies(steps: list[dict[str, Any]], step_ids: set[str], issues: list[ValidationIssue]) -> None:
    graph: dict[str, list[str]] = {step_id: [] for step_id in step_ids}
    for index, step in enumerate(steps):
        step_id = step.get("id")
        values = step.get("depends_on")
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            _issue(issues, "E_DEPENDENCY_TYPE", "depends_on must be a string list", f"steps[{index}].depends_on")
            continue
        if len(values) != len(set(values)):
            _issue(issues, "E_DEPENDENCY_DUPLICATE", "dependency repeated", f"steps[{index}].depends_on")
        if step_id in graph:
            graph[step_id] = values
        for value in values:
            if value not in step_ids:
                _issue(issues, "E_DEPENDENCY_UNKNOWN", f"unknown dependency: {value}", f"steps[{index}].depends_on")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str, trail: list[str]) -> None:
        if step_id in visiting:
            _issue(issues, "E_DEPENDENCY_CYCLE", "dependency cycle: " + " -> ".join(trail + [step_id]))
            return
        if step_id in visited:
            return
        visiting.add(step_id)
        for dependency in graph.get(step_id, []):
            if dependency in graph:
                visit(dependency, trail + [step_id])
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in sorted(step_ids):
        visit(step_id, [])


def _clean_relative(value: str) -> str | None:
    normalized = value.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts or not normalized:
        return None
    return normalized


def _path_is_source_suffix(display_path: str, source_file: Path) -> bool:
    normalized = _clean_relative(display_path)
    if normalized is None:
        return False
    actual = source_file.as_posix()
    return actual == normalized or actual.endswith("/" + normalized)


def _symbol_value_matches(value: str, locator: str, source_file: Path) -> bool:
    if value == locator:
        return True
    if value.endswith("::" + locator):
        return _path_is_source_suffix(value[: -(len(locator) + 2)], source_file)
    marker = locator + " in "
    if value.startswith(marker):
        return _path_is_source_suffix(value[len(marker) :], source_file)
    return False


def _validate_references(
    steps: list[dict[str, Any]],
    formal: bool,
    sources: dict[str, dict[str, Any]],
    run_path: Path | None,
    issues: list[ValidationIssue],
) -> None:
    for step_index, step in enumerate(steps):
        refs = step.get("references")
        if not isinstance(refs, list):
            _issue(issues, "E_REFERENCES_TYPE", "references must be a list", f"steps[{step_index}].references")
            continue
        for ref_index, ref in enumerate(refs):
            location = f"steps[{step_index}].references[{ref_index}]"
            if not isinstance(ref, dict):
                _issue(issues, "E_REFERENCE_ITEM_TYPE", "reference must be an object", location)
                continue
            kind = ref.get("kind")
            value = ref.get("value")
            status = ref.get("status")
            source_type = ref.get("source")
            critical = ref.get("critical")
            if kind not in REFERENCE_KINDS:
                _issue(issues, "E_REFERENCE_KIND_INVALID", "kind must be path, symbol, or contract", location)
            if not isinstance(value, str) or not value.strip():
                _issue(issues, "E_REFERENCE_VALUE_INVALID", "reference value is required", location)
            if status not in REFERENCE_STATUSES:
                _issue(issues, "E_REFERENCE_STATUS_INVALID", "invalid reference status", location)
            if source_type not in EVIDENCE_SOURCES:
                _issue(issues, "E_SOURCE_INVALID", "invalid reference source", location)
            if not isinstance(critical, bool):
                _issue(issues, "E_REFERENCE_CRITICAL_TYPE", "critical must be boolean", location)
            expected_source = {"planned": "PLANNED", "unverified": "UNVERIFIED"}.get(status)
            if expected_source and source_type != expected_source:
                _issue(issues, "E_REFERENCE_SOURCE_MISMATCH", f"{status} reference must use {expected_source}", location)
            if status == "existing" and source_type not in EXISTING_SOURCES:
                _issue(issues, "E_REFERENCE_SOURCE_MISMATCH", "existing reference needs verified evidence", location)

            if status == "existing":
                source_id = ref.get("source_id")
                locator = ref.get("locator")
                source = sources.get(source_id) if isinstance(source_id, str) else None
                if not isinstance(source_id, str) or not source_id.strip():
                    _issue(issues, "E_REFERENCE_SOURCE_ID", "existing reference needs source_id", location)
                elif source is None:
                    _issue(issues, "E_REFERENCE_SOURCE_UNKNOWN", f"unknown source_id: {source_id}", location)
                elif source.get("source") != source_type:
                    _issue(issues, "E_REFERENCE_SOURCE_BINDING", "reference source type does not match source_id", location)
                if not isinstance(locator, str) or not locator.strip():
                    _issue(issues, "E_REFERENCE_LOCATOR_INVALID", "existing reference needs locator", location)
                    continue
                if run_path is None or source is None or not isinstance(source.get("path"), str):
                    continue
                source_file = _resolve(run_path, source["path"])
                if not source_file.is_file() or not isinstance(value, str):
                    continue
                if kind == "path":
                    if _clean_relative(value) != _clean_relative(locator) or not _path_is_source_suffix(locator, source_file):
                        _issue(issues, "E_REFERENCE_VALUE_SOURCE_MISMATCH", "path value must exactly identify its bound source", location)
                elif kind == "symbol":
                    if not IDENTIFIER.fullmatch(locator) or locator in GENERIC_LOCATORS:
                        _issue(issues, "E_REFERENCE_LOCATOR_INVALID", "symbol locator must be a specific identifier", location)
                    elif not _symbol_value_matches(value, locator, source_file):
                        _issue(issues, "E_REFERENCE_VALUE_SOURCE_MISMATCH", "symbol value does not match bound source and locator", location)
                    else:
                        try:
                            text = source_file.read_text(encoding="utf-8")
                        except (OSError, UnicodeDecodeError) as exc:
                            _issue(issues, "E_REFERENCE_SOURCE_READ", str(exc), location)
                        else:
                            pattern = rf"(?<![A-Za-z0-9_]){re.escape(locator)}(?![A-Za-z0-9_])"
                            if not re.search(pattern, text):
                                _issue(issues, "E_REFERENCE_LOCATOR_NOT_FOUND", "symbol locator not found", location)
                elif kind == "contract":
                    allowed = {locator, f"{source_file.name}::{locator}"}
                    if value not in allowed or len(locator.strip()) < 8:
                        _issue(issues, "E_REFERENCE_VALUE_SOURCE_MISMATCH", "contract value must equal its exact clause locator", location)
                    else:
                        try:
                            text = source_file.read_text(encoding="utf-8")
                        except (OSError, UnicodeDecodeError) as exc:
                            _issue(issues, "E_REFERENCE_SOURCE_READ", str(exc), location)
                        else:
                            if locator not in text:
                                _issue(issues, "E_REFERENCE_LOCATOR_NOT_FOUND", "contract locator not found", location)
            if formal and status == "unverified" and critical is True:
                _issue(issues, "E_CRITICAL_UNVERIFIED", "critical unverified reference cannot enter a formal plan", location)


def _validate_plan(data: dict[str, Any], step_ids: set[str], issues: list[ValidationIssue]) -> None:
    plan = data.get("execution_plan")
    if not isinstance(plan, dict):
        _issue(issues, "E_EXECUTION_PLAN_REQUIRED", "formal state requires execution_plan")
        return
    milestones = _records(plan.get("milestones"), "milestones", issues)
    if not milestones:
        _issue(issues, "E_MILESTONES_EMPTY", "execution plan needs a milestone")
    _ids(milestones, "milestone", "E_MILESTONE_ID_DUPLICATE", issues)
    assignments: list[str] = []
    for index, milestone in enumerate(milestones):
        values = milestone.get("step_ids")
        location = f"execution_plan.milestones[{index}].step_ids"
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            _issue(issues, "E_PLAN_STEP_IDS_TYPE", "milestone step_ids must be a string list", location)
            continue
        if not values:
            _issue(issues, "E_MILESTONE_STEPS_EMPTY", "milestone must contain at least one STEP", location)
        if len(values) != len(set(values)):
            _issue(issues, "E_STEP_ASSIGNED_MULTIPLE", "STEP repeated inside a milestone", location)
        assignments.extend(values)
        for value in values:
            if value not in step_ids:
                _issue(issues, "E_PLAN_STEP_UNKNOWN", f"unknown STEP in plan: {value}", location)
    counts = Counter(assignments)
    for step_id, count in counts.items():
        if count > 1:
            _issue(issues, "E_STEP_ASSIGNED_MULTIPLE", f"STEP assigned multiple times: {step_id}")
    for step_id in sorted(step_ids - set(assignments)):
        _issue(issues, "E_STEP_UNASSIGNED", f"STEP not assigned: {step_id}")


def validate_run(data: Any, run_path: Path | None = None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(data, dict):
        return [ValidationIssue("E_ROOT_TYPE", "run document must be an object")]
    if data.get("schema_version") != 2:
        _issue(issues, "E_SCHEMA_VERSION", "schema_version must be 2")
    if not isinstance(data.get("run_id"), str) or not data.get("run_id", "").strip():
        _issue(issues, "E_RUN_ID", "run_id is required")
    state = data.get("state")
    outcome = data.get("outcome")
    if state not in STATES:
        _issue(issues, "E_STATE_INVALID", "invalid state")
    if outcome not in OUTCOMES:
        _issue(issues, "E_OUTCOME_INVALID", "invalid outcome")
    if data.get("code_status") != "NOT_STARTED":
        _issue(issues, "E_CODE_STATUS", "code_status must be NOT_STARTED")

    sources = _validate_sources(data, issues, run_path)
    artifacts = _artifact_entries(data, issues)
    stages = _validate_stages(data, artifacts, issues)
    _validate_artifact_files(data, artifacts, stages, issues, run_path)

    requirements = _records(data.get("requirements"), "requirements", issues)
    acceptance = _records(data.get("acceptance"), "acceptance", issues)
    steps = _records(data.get("steps"), "steps", issues)
    if state in STEP_STATES:
        if not requirements:
            _issue(issues, "E_REQUIREMENTS_EMPTY", "STEP state needs requirements")
        if not acceptance:
            _issue(issues, "E_ACCEPTANCE_EMPTY", "STEP state needs acceptance criteria")
        if not steps:
            _issue(issues, "E_STEPS_EMPTY", "STEP state needs STEPs")

    requirement_ids = _ids(requirements, "requirement", "E_REQUIREMENT_ID_DUPLICATE", issues)
    acceptance_ids = _ids(acceptance, "acceptance", "E_ACCEPTANCE_ID_DUPLICATE", issues)
    step_ids = _ids(steps, "step", "E_STEP_ID_DUPLICATE", issues)
    for name, records, code in (
        ("requirements", requirements, "E_REQUIREMENT_SOURCE_INVALID"),
        ("acceptance", acceptance, "E_ACCEPTANCE_SOURCE_INVALID"),
    ):
        for index, record in enumerate(records):
            if record.get("source") not in REQUIREMENT_SOURCES:
                _issue(issues, code, "requirement evidence must be user, PRD, or contract", f"{name}[{index}].source")

    mapped_requirements: set[str] = set()
    mapped_acceptance: set[str] = set()
    for index, step in enumerate(steps):
        for field, known, mapped, unknown_code, empty_code in (
            ("requirement_ids", requirement_ids, mapped_requirements, "E_REQUIREMENT_REFERENCE_UNKNOWN", "E_STEP_REQUIREMENTS_EMPTY"),
            ("acceptance_ids", acceptance_ids, mapped_acceptance, "E_ACCEPTANCE_REFERENCE_UNKNOWN", "E_STEP_ACCEPTANCE_EMPTY"),
        ):
            values = step.get(field)
            location = f"steps[{index}].{field}"
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                _issue(issues, f"E_{field.upper()}_TYPE", f"{field} must be a string list", location)
                continue
            if state in STEP_STATES and not values:
                _issue(issues, empty_code, f"each STEP needs at least one {field}", location)
            if len(values) != len(set(values)):
                _issue(issues, "E_STEP_MAPPING_DUPLICATE", f"duplicate id in {field}", location)
            for value in values:
                if value not in known:
                    _issue(issues, unknown_code, f"unknown id: {value}", location)
                else:
                    mapped.add(value)
    if state in STEP_STATES:
        for value in sorted(requirement_ids - mapped_requirements):
            _issue(issues, "E_REQUIREMENT_UNMAPPED", f"requirement has no STEP: {value}")
        for value in sorted(acceptance_ids - mapped_acceptance):
            _issue(issues, "E_ACCEPTANCE_UNMAPPED", f"acceptance has no STEP: {value}")

    _validate_dependencies(steps, step_ids, issues)
    _validate_references(steps, state in FORMAL_STATES, sources, run_path, issues)
    if state == "IMPLEMENTATION_PLAN_READY":
        if outcome not in {"PASS", "PASS_WITH_RISKS"}:
            _issue(issues, "E_FORMAL_OUTCOME", "formal plan must pass")
        _validate_plan(data, step_ids, issues)
    elif state == "PROVISIONAL_STEPS_READY":
        if outcome != "DOCUMENT_ONLY":
            _issue(issues, "E_PROVISIONAL_OUTCOME", "provisional run must be DOCUMENT_ONLY")
        if "execution_plan" in data:
            _issue(issues, "E_PROVISIONAL_PLAN", "provisional run cannot contain execution_plan")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_json", type=Path)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.run_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID\n[E_JSON_READ] {exc}")
        return 1
    issues = validate_run(data, args.run_json.resolve())
    if not issues:
        print("VALID")
        return 0
    print(f"INVALID ({len(issues)} issue(s))")
    for issue in issues:
        location = f" {issue.path}:" if issue.path else ""
        print(f"[{issue.code}]{location} {issue.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
