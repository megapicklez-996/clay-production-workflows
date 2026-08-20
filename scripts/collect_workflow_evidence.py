#!/usr/bin/env python3
"""Collect a bounded, read-only evidence bundle for one Clay Workflow."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

WORKFLOW_RE = re.compile(r"^wf_[A-Za-z0-9]+$")


class CollectError(RuntimeError):
    def __init__(self, message: str, exit_code: int = 5):
        super().__init__(message)
        self.exit_code = exit_code


def run_clay(args: list[str], timeout: int = 90) -> Any:
    allowed = {
        ("whoami",),
        ("workflows", "get"),
        ("workflows", "graph", "get"),
        ("workflows", "graph", "validate"),
        ("workflows", "diagram"),
        ("workflows", "snapshots", "list"),
        ("workflows", "triggers", "get"),
        ("workflows", "runs", "list"),
        ("workflows", "runs", "get"),
    }
    if not any(tuple(args[: len(prefix)]) == prefix for prefix in allowed):
        raise CollectError(f"Refusing non-read-only Clay command: {' '.join(args)}", 2)

    completed = subprocess.run(
        ["clay", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        auth = any(term in detail.lower() for term in ("login", "auth", "unauthorized", "forbidden"))
        raise CollectError(
            f"Clay command failed ({' '.join(args)}): {detail[:1200]}",
            4 if auth else 5,
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CollectError(
            f"Clay returned non-JSON for {' '.join(args)}: {completed.stdout[:300]!r}", 5
        ) from exc


def write_json(path: Path, value: Any) -> None:
    try:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise CollectError(f"Unable to write {path}: {exc}", 6) from exc


def graph_trigger_ids(graph: dict[str, Any]) -> list[str]:
    summary = graph.get("summary") or {}
    return [str(item["id"]) for item in summary.get("triggers", []) if item.get("id")]


def compact_failed_run(run: dict[str, Any]) -> dict[str, Any]:
    failed = []
    for node in run.get("nodes") or []:
        if node.get("status") == "failed":
            failed.append(
                {
                    "nodeId": node.get("nodeId") or node.get("id"),
                    "name": node.get("name"),
                    "errors": node.get("errors") or [],
                    "waitingReason": node.get("waitingReason"),
                }
            )
    return {
        "runId": run.get("runId"),
        "status": run.get("status"),
        "progress": run.get("progress"),
        "failed_nodes": failed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect read-only Clay Workflow evidence into JSON files."
    )
    parser.add_argument("workflow_id", help="Clay Workflow ID, for example wf_abc123")
    parser.add_argument("--output", required=True, type=Path, help="Evidence output directory")
    parser.add_argument("--run-limit", type=int, default=50, help="Maximum run metadata rows (default: 50)")
    parser.add_argument(
        "--failed-runs-limit",
        type=int,
        default=5,
        help="Maximum failed runs to inspect without verbose inputs/outputs (default: 5)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not WORKFLOW_RE.fullmatch(args.workflow_id):
        print("Error: workflow_id must match ^wf_[A-Za-z0-9]+$", file=sys.stderr)
        return 2
    if args.run_limit < 0 or args.failed_runs_limit < 0:
        print("Error: run limits must be non-negative", file=sys.stderr)
        return 2
    if shutil.which("clay") is None:
        print("Error: clay CLI is not available. Install or enable the Clay plugin.", file=sys.stderr)
        return 3

    try:
        args.output.mkdir(parents=True, exist_ok=True)
        identity = run_clay(["whoami"])
        workflow = run_clay(["workflows", "get", args.workflow_id])
        graph = run_clay(["workflows", "graph", "get", args.workflow_id, "--mode", "full"])
        validation = run_clay(["workflows", "graph", "validate", args.workflow_id])
        diagram = run_clay(["workflows", "diagram", args.workflow_id])
        snapshots = run_clay(["workflows", "snapshots", "list", args.workflow_id])
        runs = run_clay(["workflows", "runs", "list", args.workflow_id])

        run_rows = list(runs.get("data") or [])[: args.run_limit]
        runs = {**runs, "data": run_rows}
        triggers = [
            run_clay(["workflows", "triggers", "get", trigger_id])
            for trigger_id in graph_trigger_ids(graph)
        ]

        failed_runs = []
        for row in (item for item in run_rows if item.get("status") == "failed"):
            if len(failed_runs) >= args.failed_runs_limit:
                break
            run_id = row.get("runId")
            if not run_id:
                continue
            detail = run_clay(
                ["workflows", "runs", "get", args.workflow_id, str(run_id), "--nodes"]
            )
            failed_runs.append(compact_failed_run(detail))

        bundle = {
            "identity.json": identity,
            "workflow.json": workflow,
            "graph.json": graph,
            "validation.json": validation,
            "diagram.json": diagram,
            "snapshots.json": snapshots,
            "triggers.json": {"data": triggers},
            "runs.json": runs,
            "failed-runs.json": {"data": failed_runs},
        }
        for filename, payload in bundle.items():
            write_json(args.output / filename, payload)

        statuses: dict[str, int] = {}
        for row in run_rows:
            status = str(row.get("status") or "unknown")
            statuses[status] = statuses.get(status, 0) + 1
        print(
            json.dumps(
                {
                    "workflow_id": args.workflow_id,
                    "workflow_name": workflow.get("name"),
                    "workspace_id": (identity.get("workspace") or {}).get("id"),
                    "output": str(args.output),
                    "node_count": (graph.get("summary") or {}).get("nodeCount"),
                    "trigger_count": len(triggers),
                    "run_count": len(run_rows),
                    "run_status_counts": statuses,
                    "failed_runs_inspected": len(failed_runs),
                },
                sort_keys=True,
            )
        )
        return 0
    except CollectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.exit_code
    except subprocess.TimeoutExpired as exc:
        print(f"Error: Clay command timed out: {exc}", file=sys.stderr)
        return 5
    except OSError as exc:
        print(f"Error: filesystem failure: {exc}", file=sys.stderr)
        return 6


if __name__ == "__main__":
    raise SystemExit(main())
