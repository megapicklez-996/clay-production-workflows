#!/usr/bin/env python3
"""Validate a governed Clay campaign manifest and its approval binding."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APPROVAL_KEYS = (
    "paid_work",
    "copy_generation",
    "audience_write",
    "crm_write",
    "sequencer_write",
    "outbound_activation",
)
OWNER_KEYS = (
    "business_owner",
    "builder",
    "approver",
    "reconciliation_owner",
    "incident_owner",
)
PLACEHOLDER_MARKERS = ("REPLACE_ME", "REPLACE_WITH_")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read JSON from {path}: {exc}") from exc


def normalized_configuration(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the approval-independent configuration that approvals bind to."""
    return {key: value for key, value in manifest.items() if key != "approvals"}


def configuration_hash(manifest: dict[str, Any]) -> str:
    encoded = json.dumps(
        normalized_configuration(manifest),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def placeholder_paths(value: Any, prefix: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.extend(placeholder_paths(item, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(placeholder_paths(item, f"{prefix}[{index}]"))
    elif isinstance(value, str) and any(marker in value for marker in PLACEHOLDER_MARKERS):
        found.append(prefix)
    return found


def add(findings: list[dict[str, Any]], severity: str, code: str, **detail: Any) -> None:
    findings.append({"severity": severity, "code": code, **detail})


def exact_sequence_fields(prefix: str, count: int) -> list[str]:
    return [f"{prefix}{index}" for index in range(1, count + 1)]


def analyze_manifest(
    manifest: dict[str, Any], now: datetime | None = None
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not isinstance(manifest, dict):
        return {
            "valid": False,
            "configuration_hash": None,
            "findings": [{"severity": "BLOCKER", "code": "manifest_not_an_object"}],
            "summary": {"blockers": 1, "high": 0, "warnings": 0},
        }

    required_sections = (
        "template", "campaign", "sources", "eligibility", "copy_contract",
        "payload_contract", "destinations", "budgets", "approvals",
        "ownership", "operations", "data_handling", "reconciliation", "dependencies",
    )
    for section in required_sections:
        if not isinstance(manifest.get(section), dict):
            add(findings, "BLOCKER", "manifest_section_missing", section=section)

    placeholders = placeholder_paths(manifest)
    if placeholders:
        add(findings, "BLOCKER", "manifest_placeholders_present", paths=placeholders)

    expected_hash = configuration_hash(manifest)
    campaign = manifest.get("campaign") or {}
    approvals = manifest.get("approvals") or {}
    ownership = manifest.get("ownership") or {}
    operations = manifest.get("operations") or {}
    data_handling = manifest.get("data_handling") or {}
    budgets = manifest.get("budgets") or {}
    copy_contract = manifest.get("copy_contract") or {}
    payload_contract = manifest.get("payload_contract") or {}
    dependencies = manifest.get("dependencies") or {}

    state = campaign.get("state")
    if state not in {"DRAFT", "PREVIEW_READY", "CANARY_READY", "LIVE_READY"}:
        add(findings, "BLOCKER", "campaign_state_invalid", observed=state)

    sequence_length = copy_contract.get("sequence_length")
    if not isinstance(sequence_length, int) or isinstance(sequence_length, bool) or sequence_length < 1:
        add(findings, "BLOCKER", "sequence_length_invalid", observed=sequence_length)
    else:
        for key, prefix in (("subject_fields", "subject"), ("body_fields", "body")):
            expected = exact_sequence_fields(prefix, sequence_length)
            observed = copy_contract.get(key)
            if observed != expected:
                add(
                    findings,
                    "BLOCKER",
                    "sequence_field_contract_mismatch",
                    field=key,
                    expected=expected,
                    observed=observed,
                )

    destination_fields = payload_contract.get("destination_fields")
    if not isinstance(destination_fields, dict):
        add(findings, "BLOCKER", "payload_destination_contract_missing")
    else:
        for destination, fields in destination_fields.items():
            if not isinstance(fields, list) or not fields or not all(isinstance(item, str) and item for item in fields):
                add(
                    findings,
                    "BLOCKER",
                    "payload_required_fields_invalid",
                    destination=destination,
                    observed=fields,
                )

    numeric_budget_keys = (
        "expected_records", "worst_case_credits_per_record",
        "approved_total_clay_credits", "approved_byoa_cost_usd",
    )
    for key in numeric_budget_keys:
        value = budgets.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            add(findings, "BLOCKER", "budget_invalid", field=key, observed=value)

    custom_functions = dependencies.get("custom_functions")
    if not isinstance(custom_functions, list):
        add(findings, "BLOCKER", "custom_function_dependencies_invalid")
    else:
        seen_function_ids: set[str] = set()
        for index, row in enumerate(custom_functions):
            if not isinstance(row, dict) or not row.get("id"):
                add(findings, "BLOCKER", "custom_function_dependency_invalid", index=index)
                continue
            function_id = str(row["id"])
            if function_id in seen_function_ids:
                add(findings, "BLOCKER", "custom_function_dependency_duplicated", function_id=function_id)
            seen_function_ids.add(function_id)
            digest = str(row.get("sha256") or "")
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                add(
                    findings,
                    "BLOCKER",
                    "custom_function_dependency_hash_invalid",
                    function_id=function_id,
                    observed=digest,
                )

    enabled_approvals = [key for key in APPROVAL_KEYS if approvals.get(key) is True]
    missing_approval_flags = [key for key in APPROVAL_KEYS if key not in approvals]
    if missing_approval_flags:
        add(findings, "BLOCKER", "approval_flags_missing", fields=missing_approval_flags)
    invalid_approval_values = [
        key for key in APPROVAL_KEYS
        if key in approvals and not isinstance(approvals.get(key), bool)
    ]
    if invalid_approval_values:
        add(findings, "BLOCKER", "approval_flags_not_boolean", fields=invalid_approval_values)

    if enabled_approvals:
        if approvals.get("config_hash") != expected_hash:
            add(
                findings,
                "BLOCKER",
                "approval_config_hash_mismatch",
                expected=expected_hash,
                observed=approvals.get("config_hash"),
            )
        for key in ("reference", "approver", "approved_at", "expires_at"):
            if not approvals.get(key):
                add(findings, "BLOCKER", "approval_evidence_missing", field=key)
        approved_at = parse_time(approvals.get("approved_at"))
        expires_at = parse_time(approvals.get("expires_at"))
        if approvals.get("approved_at") and approved_at is None:
            add(findings, "BLOCKER", "approval_timestamp_invalid", field="approved_at")
        if approvals.get("expires_at") and expires_at is None:
            add(findings, "BLOCKER", "approval_timestamp_invalid", field="expires_at")
        if expires_at and expires_at <= now:
            add(findings, "BLOCKER", "approval_expired", expires_at=expires_at.isoformat())
        if approved_at and expires_at and approved_at >= expires_at:
            add(findings, "BLOCKER", "approval_window_invalid")

    if approvals.get("paid_work") is True:
        expected_records = budgets.get("expected_records")
        per_record = budgets.get("worst_case_credits_per_record")
        approved_total = budgets.get("approved_total_clay_credits")
        if all(isinstance(value, (int, float)) for value in (expected_records, per_record, approved_total)):
            worst_total = expected_records * per_record
            if approved_total < worst_total:
                add(
                    findings,
                    "BLOCKER",
                    "approved_clay_credits_below_worst_case",
                    required=worst_total,
                    approved=approved_total,
                )

    if approvals.get("outbound_activation") is True and approvals.get("sequencer_write") is not True:
        add(findings, "BLOCKER", "activation_without_sequencer_write_approval")

    # A LIVE_READY claim must carry approval for every destination the payload
    # contract actually writes to, plus the separate activation approval.  A
    # manifest with configured writes and all-false approvals must never pass
    # merely because it has otherwise complete governance metadata.
    if state == "LIVE_READY":
        destination_approval_keys = {
            "audience": "audience_write",
            "crm": "crm_write",
            "sequencer": "sequencer_write",
        }
        configured_destinations = sorted(
            destination
            for destination in (payload_contract.get("destination_fields") or {})
            if destination in destination_approval_keys
        )
        missing_destination_approvals = [
            destination_approval_keys[destination]
            for destination in configured_destinations
            if approvals.get(destination_approval_keys[destination]) is not True
        ]
        if missing_destination_approvals:
            add(
                findings,
                "BLOCKER",
                "live_ready_destination_approvals_missing",
                fields=missing_destination_approvals,
            )
        if approvals.get("outbound_activation") is not True:
            add(findings, "BLOCKER", "live_ready_outbound_activation_approval_missing")

    production_claim = bool(enabled_approvals or campaign.get("ready") or state == "LIVE_READY")
    if production_claim:
        missing_owners = [key for key in OWNER_KEYS if not ownership.get(key)]
        if missing_owners:
            add(findings, "HIGH", "production_owners_missing", fields=missing_owners)
        if approvals.get("approver") and ownership.get("approver") and approvals.get("approver") != ownership.get("approver"):
            add(findings, "HIGH", "approval_owner_mismatch")
        reconciliation_owner = (manifest.get("reconciliation") or {}).get("owner")
        if reconciliation_owner and ownership.get("reconciliation_owner") and reconciliation_owner != ownership.get("reconciliation_owner"):
            add(findings, "HIGH", "reconciliation_owner_mismatch")

    external_write_approved = any(
        approvals.get(key) is True for key in ("audience_write", "crm_write", "sequencer_write")
    )
    if external_write_approved:
        kill_switch = operations.get("kill_switch") or {}
        missing_kill_switch = [
            key for key in ("owner", "pause_method", "rollback_snapshot_id", "downstream_remediation_owner")
            if not kill_switch.get(key)
        ]
        if missing_kill_switch:
            add(findings, "HIGH", "kill_switch_incomplete", fields=missing_kill_switch)

    retention_days = data_handling.get("evidence_retention_days")
    if not isinstance(retention_days, int) or isinstance(retention_days, bool) or retention_days < 0:
        add(findings, "HIGH", "evidence_retention_invalid", observed=retention_days)
    redacted = data_handling.get("redacted_fields")
    if not isinstance(redacted, list) or not redacted:
        add(findings, "HIGH", "redacted_fields_missing")
        redacted = []
    raw_retention = data_handling.get("raw_payload_retention_days")
    if not isinstance(raw_retention, int) or isinstance(raw_retention, bool) or raw_retention < 0:
        add(findings, "HIGH", "raw_payload_retention_invalid", observed=raw_retention)
    allowed_logs = data_handling.get("allowed_log_fields")
    if not isinstance(allowed_logs, list):
        add(findings, "HIGH", "allowed_log_fields_invalid")
        allowed_logs = []
    overlap = sorted(set(str(item) for item in allowed_logs) & set(str(item) for item in redacted))
    if overlap:
        add(findings, "BLOCKER", "redacted_fields_allowed_in_logs", fields=overlap)
    if not any(any(term in str(item).lower() for term in ("credential", "secret", "token", "api_key")) for item in redacted):
        add(findings, "HIGH", "credential_redaction_not_declared")
    if not data_handling.get("classification"):
        add(findings, "HIGH", "data_classification_missing")

    blockers = sum(item["severity"] == "BLOCKER" for item in findings)
    high = sum(item["severity"] == "HIGH" for item in findings)
    return {
        "valid": blockers == 0 and high == 0,
        "configuration_hash": expected_hash,
        "enabled_approvals": enabled_approvals,
        "findings": findings,
        "summary": {
            "blockers": blockers,
            "high": high,
            "warnings": len(findings) - blockers - high,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a governed Clay campaign manifest.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--strict", action="store_true", help="Exit 10 for BLOCKER or HIGH findings")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = load_json(args.manifest)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    result = analyze_manifest(manifest)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 10 if args.strict and not result["valid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
