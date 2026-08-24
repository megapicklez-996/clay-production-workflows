#!/usr/bin/env python3
"""Audit external writes, payload mappings, terminals, and readbacks in a graph."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


OUTCOMES = {
    "activated_verified", "already_satisfied", "review_only", "safely_suppressed",
    "provider_failure", "destination_rejection", "reconciliation_failure",
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read JSON from {path}: {exc}") from exc


def node_text(node: dict[str, Any]) -> str:
    return json.dumps(node, sort_keys=True).lower()


def destination_for(node: dict[str, Any]) -> str | None:
    text = node_text(node)
    if "audience" in text or "upsert-audiences-record" in text:
        return "audience"
    if any(term in text for term in ("salesforce", "hubspot", "crm", "campaignmember")):
        return "crm"
    if any(term in text for term in ("instantly", "smartlead", "outreach", "sequencer", "enroll")):
        return "sequencer"
    return None


def action_keys(node: dict[str, Any]) -> list[str]:
    return [
        str(tool.get("actionKey") or "").lower()
        for tool in node.get("tools") or []
        if isinstance(tool, dict)
    ]


def is_write(node: dict[str, Any]) -> bool:
    text = node_text(node)
    if "[external mutation]" in text:
        return True
    verbs = ("create", "update", "upsert", "enroll", "add-lead", "send", "write")
    return any(any(verb in action for verb in verbs) for action in action_keys(node))


def is_readback(node: dict[str, Any]) -> bool:
    name = str(node.get("name") or "").lower()
    if any(term in name for term in ("reconcil", "readback", "verify", "lookup receipt")):
        return True
    read_verbs = ("get", "list", "lookup", "search", "find")
    return any(any(verb in action for verb in read_verbs) for action in action_keys(node))


def edge_pair(edge: dict[str, Any]) -> tuple[str | None, str | None]:
    source = edge.get("sourceNodeId") or edge.get("sourceNode") or edge.get("source") or edge.get("from")
    target = edge.get("targetNodeId") or edge.get("targetNode") or edge.get("target") or edge.get("to")
    return (str(source) if source else None, str(target) if target else None)


def graph_edges(graph: dict[str, Any]) -> list[tuple[str, str]]:
    resolved: list[tuple[str, str]] = []
    for edge in (graph.get("summary") or {}).get("edges") or graph.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        source, target = edge_pair(edge)
        if source and target:
            resolved.append((source, target))
    for node in graph.get("nodes") or []:
        target = node.get("id")
        for edge in node.get("incomingEdges") or []:
            if not isinstance(edge, dict):
                continue
            source = edge.get("sourceNode") or edge.get("sourceNodeId")
            if source and target:
                resolved.append((str(source), str(target)))
    return sorted(set(resolved))


def reachable(start: str, adjacency: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    queue = deque(adjacency.get(start, set()))
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(adjacency.get(current, set()) - seen)
    return seen


def mapped_fields(node: dict[str, Any]) -> set[str]:
    fields: set[str] = set()
    for schema_key in ("inputSchema", "outputSchema"):
        schema = node.get(schema_key) or {}
        properties = schema.get("properties") if isinstance(schema, dict) else None
        if isinstance(properties, dict):
            fields.update(str(key) for key in properties)
        elif isinstance(schema, dict):
            fields.update(str(key) for key in schema)
    for tool in node.get("tools") or []:
        if not isinstance(tool, dict):
            continue
        mapping = tool.get("inputMappingConfig") or {}
        if isinstance(mapping, dict):
            fields.update(str(key) for key in mapping)
    code = str(node.get("code") or "")
    fields.update(re.findall(r"[\"']([A-Za-z][A-Za-z0-9_]*)[\"']\s*:", code))
    return fields


def add(findings: list[dict[str, Any]], severity: str, code: str, **detail: Any) -> None:
    findings.append({"severity": severity, "code": code, **detail})


def analyze_graph_controls(
    graph: dict[str, Any], manifest: dict[str, Any] | None = None
) -> dict[str, Any]:
    nodes = [node for node in graph.get("nodes") or [] if isinstance(node, dict)]
    by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    edges = graph_edges(graph)
    adjacency: dict[str, set[str]] = defaultdict(set)
    reverse: dict[str, set[str]] = defaultdict(set)
    for source, target in edges:
        adjacency[source].add(target)
        reverse[target].add(source)

    findings: list[dict[str, Any]] = []
    writes = [node for node in nodes if is_write(node)]
    readbacks = [node for node in nodes if is_readback(node)]
    approval_nodes = [
        node for node in nodes
        if any(term in node_text(node) for term in ("approval", "approved?", "config_hash"))
    ]
    if len(nodes) > 1 and not edges:
        add(findings, "MEDIUM", "graph_edges_unavailable", consequence="branch_and_readback_reachability_unknown")

    for write in writes:
        write_id = str(write.get("id"))
        destination = destination_for(write)
        candidates = [
            node for node in readbacks
            if destination_for(node) in {None, destination}
        ]
        if edges:
            downstream = reachable(write_id, adjacency)
            candidates = [node for node in candidates if str(node.get("id")) in downstream]
            if not candidates:
                add(
                    findings,
                    "BLOCKER",
                    "external_write_without_downstream_readback",
                    node=write.get("name"),
                    destination=destination,
                )
        elif not candidates:
            add(
                findings,
                "HIGH",
                "external_write_readback_not_detected",
                node=write.get("name"),
                destination=destination,
            )

        if not approval_nodes:
            add(
                findings,
                "HIGH",
                "external_write_approval_control_not_detected",
                node=write.get("name"),
                destination=destination,
            )
        elif edges:
            ancestors = reachable(write_id, reverse)
            if not any(str(node.get("id")) in ancestors for node in approval_nodes):
                add(
                    findings,
                    "HIGH",
                    "external_write_not_downstream_of_approval",
                    node=write.get("name"),
                    destination=destination,
                )

    payload_contract = ((manifest or {}).get("payload_contract") or {}).get("destination_fields") or {}
    approvals = (manifest or {}).get("approvals") or {}
    destination_ids = (manifest or {}).get("destinations") or {}
    approval_key = {"audience": "audience_write", "crm": "crm_write", "sequencer": "sequencer_write"}
    for destination, required in payload_contract.items():
        destination_writes = [node for node in writes if destination_for(node) == destination]
        if approvals.get(approval_key.get(destination, "")) is True and not destination_writes:
            add(findings, "BLOCKER", "approved_destination_write_not_detected", destination=destination)
            continue
        for write in destination_writes:
            evidence_nodes = [write]
            if edges:
                ancestors = reachable(str(write.get("id")), reverse)
                evidence_nodes.extend(by_id[node_id] for node_id in ancestors if node_id in by_id)
            observed: set[str] = set()
            for node in evidence_nodes:
                observed.update(mapped_fields(node))
            if not observed:
                add(
                    findings,
                    "MEDIUM",
                    "payload_mapping_not_inspectable",
                    node=write.get("name"),
                    destination=destination,
                )
                continue
            missing = sorted(set(required or []) - observed)
            if missing:
                add(
                    findings,
                    "BLOCKER",
                    "required_payload_fields_not_mapped",
                    node=write.get("name"),
                    destination=destination,
                    missing=missing,
                    observed=sorted(observed),
                )
            destination_key = {
                "audience": "audience_id", "crm": "crm_campaign_id", "sequencer": "sequencer_campaign_id"
            }.get(destination)
            destination_id = destination_ids.get(destination_key) if destination_key else None
            if destination_id and destination_id not in " ".join(node_text(node) for node in evidence_nodes):
                add(
                    findings,
                    "MEDIUM",
                    "destination_binding_not_statically_verified",
                    node=write.get("name"),
                    destination=destination,
                    expected_id=destination_id,
                )

    idempotency_nodes = [node for node in nodes if "idempot" in node_text(node)]
    if writes and not idempotency_nodes:
        add(findings, "HIGH", "idempotency_control_not_detected")
    elif edges:
        for write in writes:
            ancestors = reachable(str(write.get("id")), reverse)
            if not any(str(node.get("id")) in ancestors for node in idempotency_nodes):
                add(
                    findings,
                    "HIGH",
                    "external_write_not_downstream_of_idempotency",
                    node=write.get("name"),
                )

    sequencer_writes = [node for node in writes if destination_for(node) == "sequencer"]
    if sequencer_writes:
        suppression_nodes = [
            node for node in nodes
            if any(term in node_text(node) for term in ("suppress", "unsubscribe", "blocklist", "bounce", "prior reply"))
        ]
        if not suppression_nodes:
            add(findings, "HIGH", "sequencer_write_without_suppression_control")
        elif edges:
            for write in sequencer_writes:
                ancestors = reachable(str(write.get("id")), reverse)
                if not any(str(node.get("id")) in ancestors for node in suppression_nodes):
                    add(
                        findings,
                        "HIGH",
                        "sequencer_write_not_downstream_of_suppression",
                        node=write.get("name"),
                    )

    if edges:
        leaves = [node for node in nodes if node.get("nodeType") != "trigger" and not adjacency.get(str(node.get("id")))]
        for leaf in leaves:
            text = node_text(leaf)
            if not any(outcome in text for outcome in OUTCOMES):
                add(
                    findings,
                    "HIGH",
                    "leaf_without_terminal_outcome",
                    node=leaf.get("name"),
                    node_id=leaf.get("id"),
                )

    blockers = sum(item["severity"] == "BLOCKER" for item in findings)
    high = sum(item["severity"] == "HIGH" for item in findings)
    return {
        "valid": blockers == 0 and high == 0,
        "write_nodes": [{"id": node.get("id"), "name": node.get("name"), "destination": destination_for(node)} for node in writes],
        "readback_nodes": [{"id": node.get("id"), "name": node.get("name"), "destination": destination_for(node)} for node in readbacks],
        "findings": findings,
        "summary": {"blockers": blockers, "high": high, "warnings": len(findings) - blockers - high},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit production controls in a Clay graph.")
    parser.add_argument("graph", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        graph = load_json(args.graph)
        manifest = load_json(args.manifest) if args.manifest else None
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    result = analyze_graph_controls(graph, manifest)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 10 if args.strict and not result["valid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
