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
from validate_contract import analyze


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


def audit(evidence_dir: Path) -> dict[str, Any]:
    graph = load_json(evidence_dir / "graph.json")
    validation = load_json(evidence_dir / "validation.json")
    runs = load_json(evidence_dir / "runs.json")
    failed = load_json(evidence_dir / "failed-runs.json", required=False)
    workflow = load_json(evidence_dir / "workflow.json", required=False)
    triggers = load_json(evidence_dir / "triggers.json", required=False)

    nodes = list(graph.get("nodes") or [])
    summary = graph.get("summary") or {}
    type_counts = Counter(str(node.get("nodeType") or "unknown") for node in nodes)
    contract = analyze(graph, validation)
    run_summary = summarize(runs, failed)

    structural_ok = validation.get("valid") is True and not (validation.get("errors") or [])
    contract_ok = contract.get("valid") is True
    if not structural_ok or not contract_ok:
        ceiling = "DRAFT_BLOCKED"
    elif run_summary["run_count"] == 0:
        ceiling = "PREVIEW_READY"
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
        "live_ready_proven": False,
        "live_ready_reason": "Static evidence and run status cannot replace verified destination readbacks.",
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
        "run_evidence": run_summary,
        "required_next_evidence": [
            "Exact terminal business outcomes for completed runs",
            "Readbacks from every intended external destination",
            "Duplicate-rerun behavior",
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
