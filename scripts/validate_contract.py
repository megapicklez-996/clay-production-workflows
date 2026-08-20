#!/usr/bin/env python3
"""Detect semantic sequence-cardinality mismatches in a Clay Workflow graph."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
FIELD_RE = re.compile(r"^(?:subject|body)_?(\d+)$", re.I)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read JSON from {path}: {exc}") from exc


def schema_properties(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    props = schema.get("properties")
    return props if isinstance(props, dict) else schema


def field_count(keys: Iterable[str]) -> int | None:
    numbers = [int(match.group(1)) for key in keys if (match := FIELD_RE.match(str(key)))]
    return max(numbers) if numbers else None


def text_counts(text: str) -> set[int]:
    counts: set[int] = set()
    lower = text.lower()
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{word}[- ]email\b", lower):
            counts.add(value)
    for match in re.finditer(r"\b(\d{1,2})[- ]email\b", lower):
        counts.add(int(match.group(1)))
    return counts


def code_counts(code: str) -> set[int]:
    counts = text_counts(code)
    for match in re.finditer(r"['\"]sequence_length['\"]\s*:\s*(\d+)", code):
        counts.add(int(match.group(1)))
    for match in re.finditer(r"range\(\s*1\s*,\s*(\d+)\s*\)", code):
        upper = int(match.group(1))
        if upper > 1 and re.search(r"subject|body", code, re.I):
            counts.add(upper - 1)
    numbered = [int(value) for value in re.findall(r"(?:subject|body)_?(\d+)", code, re.I)]
    if numbered:
        counts.add(max(numbered))
    return counts


def role_for(node: dict[str, Any]) -> str | None:
    name = str(node.get("name") or "").lower()
    prompt = str(node.get("agentPrompt") or "").lower()
    code = str(node.get("code") or "").lower()
    node_type = node.get("nodeType")
    if node_type == "agent" and re.search(r"repair|retry", name + " " + prompt):
        return "repair"
    if node_type == "agent" and re.search(r"\bqa\b|review", name + " " + prompt):
        return "qa"
    if node_type == "agent" and re.search(r"generate|write.*sequence|sequence", name + " " + prompt):
        return "generator"
    if node_type == "code" and re.search(r"validator|copy contract|copy_validation", name + " " + code):
        return "validator"
    if node_type in {"code", "conditional"} and re.search(
        r"payload|custom variables|custom_variables", name + " " + code
    ):
        return "payload"
    if node_type == "code" and "sequence_length" in code:
        return "manifest"
    return None


def node_counts(node: dict[str, Any]) -> dict[str, list[int]]:
    sources: dict[str, set[int]] = {}
    name = str(node.get("name") or "")
    prompt = str(node.get("agentPrompt") or "")
    code = str(node.get("code") or "")
    for label, values in (
        ("name", text_counts(name)),
        ("prompt", text_counts(prompt)),
        ("code", code_counts(code)),
    ):
        if values:
            sources[label] = values
    output_count = field_count(schema_properties(node.get("outputSchema")).keys())
    input_count = field_count(schema_properties(node.get("inputSchema")).keys())
    if output_count:
        sources["output_schema"] = {output_count}
    if input_count:
        sources["input_schema"] = {input_count}
    return {key: sorted(value) for key, value in sources.items()}


def choose_canonical(layers: list[dict[str, Any]]) -> int | None:
    manifest = [
        count
        for layer in layers
        if layer["role"] == "manifest"
        for counts in layer["counts"].values()
        for count in counts
    ]
    if manifest:
        return Counter(manifest).most_common(1)[0][0]
    values = [count for layer in layers for counts in layer["counts"].values() for count in counts]
    return Counter(values).most_common(1)[0][0] if values else None


def analyze(graph: dict[str, Any], validation: dict[str, Any] | None = None) -> dict[str, Any]:
    nodes = graph.get("nodes") or []
    layers = []
    for node in nodes:
        role = role_for(node)
        if role:
            layers.append(
                {
                    "node_id": node.get("id"),
                    "name": node.get("name"),
                    "role": role,
                    "counts": node_counts(node),
                }
            )
    canonical = choose_canonical(layers)
    findings = []
    for layer in layers:
        values = sorted({value for counts in layer["counts"].values() for value in counts})
        if len(values) > 1:
            findings.append(
                {
                    "severity": "BLOCKER",
                    "code": "internal_sequence_cardinality_mismatch",
                    "node": layer["name"],
                    "evidence": layer["counts"],
                }
            )
        elif canonical is not None and values and values[0] != canonical:
            findings.append(
                {
                    "severity": "BLOCKER",
                    "code": "cross_layer_sequence_cardinality_mismatch",
                    "node": layer["name"],
                    "expected": canonical,
                    "observed": values[0],
                    "evidence": layer["counts"],
                }
            )
    roles = {layer["role"] for layer in layers}
    missing_roles = [role for role in ("generator", "validator", "qa", "payload") if role not in roles]
    if canonical and missing_roles:
        findings.append(
            {
                "severity": "MEDIUM",
                "code": "sequence_contract_layer_not_detected",
                "roles": missing_roles,
            }
        )
    warnings = (validation or {}).get("warnings") or []
    blockers = sum(1 for item in findings if item["severity"] == "BLOCKER")
    return {
        "valid": blockers == 0,
        "canonical_sequence_length": canonical,
        "layers": layers,
        "findings": findings,
        "structural_validation": {
            "valid": (validation or {}).get("valid") if validation else None,
            "error_count": len((validation or {}).get("errors") or []),
            "warning_count": len(warnings),
            "warning_codes": sorted({str(item.get("code")) for item in warnings if item.get("code")}),
        },
        "summary": {
            "blockers": blockers,
            "other_findings": len(findings) - blockers,
            "layers_checked": len(layers),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit sequence-contract consistency in a Clay graph JSON file.")
    parser.add_argument("graph", type=Path, help="Graph JSON from `clay workflows graph get --mode full`")
    parser.add_argument("--validation", type=Path, help="Optional structural validation JSON")
    parser.add_argument("--strict", action="store_true", help="Exit 10 when blockers are found")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        graph = load_json(args.graph)
        validation = load_json(args.validation) if args.validation else None
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    result = analyze(graph, validation)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 10 if args.strict and not result["valid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
