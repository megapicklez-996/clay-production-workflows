#!/usr/bin/env python3
"""Synthesize a compact launch-readiness ceiling from a Clay evidence directory."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from summarize_runs import summarize
from analyze_run_traces import analyze_run_traces
from validate_contract import analyze
from check_evidence_compat import analyze_evidence
from validate_graph_controls import analyze_graph_controls
from validate_manifest import analyze_manifest
from validate_reconciliation import analyze_reconciliation
from validate_snapshot_semantics import analyze_snapshot
from validate_trigger_safety import analyze_trigger_safety


def load_json(path: Path, required: bool = True) -> Any:
    if not path.exists() and not required:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read JSON from {path}: {exc}") from exc


def matching_names(nodes: list[dict[str, Any]], terms: tuple[str, ...]) -> list[str]:
    lowered = tuple(term.lower() for term in terms)
    return [
        str(node.get("name"))
        for node in nodes
        if any(term in str(node.get("name") or "").lower() for term in lowered)
    ]


def coverage_status(result: dict[str, Any], *, supplied: bool = True) -> str:
    if not supplied:
        return "NOT_CHECKED"
    if result.get("valid") is not True:
        return "FAILED"
    codes = {str(item.get("code")) for item in result.get("findings") or []}
    if any("unknown" in code or "not_supplied" in code for code in codes):
        return "UNKNOWN"
    return "PROVEN"


def audit(evidence_dir: Path) -> dict[str, Any]:
    graph = load_json(evidence_dir / "graph.json")
    validation = load_json(evidence_dir / "validation.json")
    runs = load_json(evidence_dir / "runs.json")
    failed = load_json(evidence_dir / "failed-runs.json", required=False)
    workflow = load_json(evidence_dir / "workflow.json", required=False)
    triggers = load_json(evidence_dir / "triggers.json", required=False)
    current_snapshot = load_json(evidence_dir / "current-snapshot.json", required=False)
    audience_segments = load_json(evidence_dir / "audience-segments.json", required=False)
    function_fingerprints = load_json(evidence_dir / "function-fingerprints.json", required=False)
    run_traces = load_json(evidence_dir / "run-traces.json", required=False)
    manifest = load_json(evidence_dir / "manifest.json", required=False)
    receipts = load_json(evidence_dir / "receipts.json", required=False)

    nodes = list(graph.get("nodes") or [])
    summary = graph.get("summary") or {}
    type_counts = Counter(str(node.get("nodeType") or "unknown") for node in nodes)
    contract = analyze(graph, validation)
    compatibility = analyze_evidence(evidence_dir)
    manifest_audit = analyze_manifest(manifest) if manifest else {
        "valid": False,
        "configuration_hash": None,
        "findings": [{"severity": "HIGH", "code": "manifest_evidence_missing"}],
        "summary": {"blockers": 0, "high": 1, "warnings": 0},
    }
    graph_controls = analyze_graph_controls(
        graph, manifest or None, function_fingerprints or None
    )
    snapshot_semantics = analyze_snapshot(current_snapshot) if current_snapshot else {
        "valid": True,
        "findings": [{"severity": "MEDIUM", "code": "current_snapshot_not_supplied"}],
        "summary": {"blockers": 0, "high": 0, "warnings": 1},
    }
    trigger_safety = analyze_trigger_safety(triggers, audience_segments or None)
    run_trace_audit = analyze_run_traces(run_traces) if run_traces else {
        "valid": True,
        "run_count": 0,
        "traced_node_count": 0,
        "findings": [{"severity": "MEDIUM", "code": "run_traces_not_supplied"}],
        "summary": {"blockers": 0, "high": 0, "warnings": 1},
    }
    reconciliation = analyze_reconciliation(
        receipts, manifest_audit.get("configuration_hash")
    ) if receipts else {
        "valid": False,
        "live_ready_proven": False,
        "receipt_count": 0,
        "outcome_counts": {},
        "findings": [{"severity": "MEDIUM", "code": "reconciliation_receipts_not_supplied"}],
        "summary": {"blockers": 0, "high": 0, "warnings": 1},
    }
    run_summary = summarize(runs, failed, graph)

    structural_ok = validation.get("valid") is True and not (validation.get("errors") or [])
    contract_ok = contract.get("valid") is True
    governance_ok = (
        compatibility.get("compatible") is True
        and manifest_audit.get("valid") is True
        and graph_controls.get("valid") is True
        and snapshot_semantics.get("valid") is True
        and trigger_safety.get("valid") is True
        and run_trace_audit.get("valid") is True
    )
    if not structural_ok or not contract_ok or not governance_ok:
        ceiling = "DRAFT_BLOCKED"
    elif run_summary["run_count"] == 0:
        ceiling = "PREVIEW_READY"
    elif (
        reconciliation.get("live_ready_proven") is True
        and run_trace_audit.get("run_count", 0) > 0
        and run_trace_audit.get("traced_node_count", 0) > 0
        and coverage_status(snapshot_semantics, supplied=bool(current_snapshot)) == "PROVEN"
        and coverage_status(trigger_safety, supplied=bool(triggers)) == "PROVEN"
        and coverage_status(run_trace_audit, supplied=bool(run_traces)) == "PROVEN"
        and (manifest.get("campaign") or {}).get("state") == "LIVE_READY"
        and (manifest.get("campaign") or {}).get("ready") is True
    ):
        ceiling = "LIVE_READY"
    else:
        ceiling = "CANARY_READY"

    warnings = validation.get("warnings") or []
    trigger_rows = list(triggers.get("data") or [])
    trigger_entities = Counter(str(row.get("entityType") or "unknown") for row in trigger_rows)
    return {
        "workflow": {
            "id": workflow.get("id") or summary.get("workflowId"),
            "name": workflow.get("name") or summary.get("workflowName"),
            "url": workflow.get("url") or summary.get("workflowUrl"),
        },
        "readiness_ceiling": ceiling,
        "live_ready_proven": ceiling == "LIVE_READY",
        "live_ready_reason": (
            "Validated reconciliation receipts contain an activated canary with verified readbacks."
            if ceiling == "LIVE_READY"
            else "Static evidence and run status cannot replace verified destination readbacks."
        ),
        "structure": {
            "node_count": summary.get("nodeCount") or len(nodes),
            "edge_count": len(summary.get("edges") or []),
            "node_type_counts": dict(sorted(type_counts.items())),
            "trigger_count": len(trigger_rows),
            "trigger_entity_counts": dict(sorted(trigger_entities.items())),
        },
        "controls": {
            "approval_gates": matching_names(nodes, ("approved?", "approval", "preflight")),
            "reconciliation_nodes": matching_names(nodes, ("reconciliation", "receipt", "readback", "verify")),
            "suppression_nodes": matching_names(nodes, ("suppression", "existing", "blocklist", "already")),
            "queue_nodes": matching_names(nodes, ("queue", "stage person", "select up to")),
        },
        "structural_validation": {
            "valid": structural_ok,
            "errors": validation.get("errors") or [],
            "warning_count": len(warnings),
            "warning_codes": sorted({str(item.get("code")) for item in warnings if item.get("code")}),
        },
        "semantic_contract": contract,
        "manifest_contract": manifest_audit,
        "graph_controls": graph_controls,
        "snapshot_semantics": snapshot_semantics,
        "trigger_safety": trigger_safety,
        "evidence_compatibility": compatibility,
        "run_evidence": run_summary,
        "run_trace_consistency": run_trace_audit,
        "reconciliation_evidence": reconciliation,
        "coverage": {
            "structural_validation": "PROVEN" if structural_ok else "FAILED",
            "semantic_contract": coverage_status(contract),
            "manifest_contract": coverage_status(manifest_audit, supplied=bool(manifest)),
            "graph_controls": coverage_status(graph_controls),
            "raw_snapshot_semantics": coverage_status(snapshot_semantics, supplied=bool(current_snapshot)),
            "trigger_safety": coverage_status(trigger_safety, supplied=bool(triggers)),
            "run_outcome_consistency": coverage_status(run_trace_audit, supplied=bool(run_traces)),
            "destination_reconciliation": coverage_status(reconciliation, supplied=bool(receipts)),
        },
        "required_next_evidence": [
            item for condition, item in (
                (not current_snapshot, "Current raw snapshot for transition and context validation"),
                (not audience_segments, "Redacted Audience segment fingerprints for trigger overlap"),
                (not run_traces, "Redacted node outcome trace for at least one bounded canary"),
                (not receipts, "Readbacks from every intended external destination"),
                (True, "Duplicate-rerun behavior"),
            ) if condition
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a compact audit from a Clay evidence directory.")
    parser.add_argument("evidence_dir", type=Path, help="Directory from collect_workflow_evidence.py")
    parser.add_argument("--strict", action="store_true", help="Exit 10 when readiness is DRAFT_BLOCKED")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = audit(args.evidence_dir)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 10 if args.strict and result["readiness_ceiling"] == "DRAFT_BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
