#!/usr/bin/env python3
"""Render a noob-friendly explanation of a Clay Workflow evidence pack."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from validate_contract import analyze


PHASES: list[tuple[str, tuple[str, ...]]] = [
    ("Entry and configuration", ("trigger", "adapter", "configuration", "config", "preflight", "manifest")),
    ("Account and person selection", ("candidate", "persona", "qualified", "select up to", "company function", "person queue", "stage person")),
    ("Identity, existing-record, and safety checks", ("identity", "existing", "suppression", "blocklist", "already", "current employer")),
    ("Enrichment", ("enrich", "find & verify", "work email", "bettercontact", "provider")),
    ("Message generation and validation", ("copy", "sequence", "generate", "repair", "qa", "subject", "body")),
    ("External activation", ("audience", "salesforce", "instantly", "campaignmember", "external mutation", "activation")),
    ("Verification and terminal receipt", ("reconciliation", "readback", "receipt", "verify", "no-send", "finalize")),
]

GLOSSARY = {
    "trigger": "the event that starts one workflow run",
    "audience": "a saved group of accounts or people in Clay",
    "enrichment": "a lookup that fills in missing facts, sometimes using paid credits",
    "suppression": "a deliberate decision not to contact someone who is unsafe or already handled",
    "idempotency": "a safeguard that prevents a rerun from creating the same side effect twice",
    "reconciliation": "checking the destination after a write rather than trusting only the request",
    "canary": "a deliberately tiny live test before a larger launch",
    "fail closed": "missing configuration or proof blocks the risky action while safe inspection remains possible",
}


def load_json(path: Path, required: bool = False) -> Any:
    if not path.exists():
        if required:
            raise ValueError(f"Missing required file: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read JSON from {path}: {exc}") from exc


def clean_name(value: Any) -> str:
    name = str(value or "Unnamed step").strip()
    name = re.sub(r"^[A-Z]{0,3}\d{1,3}[A-Z0-9]*(?:\s+|\s*[-:]\s*)", "", name)
    name = re.sub(r"\[(?:READ ONLY|PAID|EXTERNAL MUTATION|AI|AI QA|AI RETRY[^\]]*)\]\s*", "", name, flags=re.I)
    return re.sub(r"\s+", " ", name).strip(" -") or "Unnamed step"


def text_for(node: dict[str, Any]) -> str:
    return " ".join(
        str(node.get(key) or "")
        for key in ("name", "description", "nodeType", "agentPrompt")
    ).lower()


def matches(node: dict[str, Any], terms: tuple[str, ...]) -> bool:
    haystack = text_for(node)
    return any(term in haystack for term in terms)


def name_matches(node: dict[str, Any], terms: tuple[str, ...]) -> bool:
    name = str(node.get("name") or "").lower()
    return any(term in name for term in terms)


def unique_names(nodes: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for node in nodes:
        name = clean_name(node.get("name"))
        if name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names


def infer_systems(nodes: list[dict[str, Any]]) -> list[str]:
    combined = " ".join(text_for(node) for node in nodes)
    candidates = [
        ("Clay Audiences", ("audience",)),
        ("Salesforce", ("salesforce", "sfdc", "campaignmember")),
        ("Instantly", ("instantly",)),
    ]
    return [label for label, terms in candidates if any(term in combined for term in terms)]


def infer_unit(nodes: list[dict[str, Any]], trigger_rows: list[dict[str, Any]]) -> str:
    entities = {str(row.get("entityType") or "").upper() for row in trigger_rows}
    combined = " ".join(text_for(node) for node in nodes)
    if "CONTACT" in entities or "person queue" in combined or "stage person" in combined:
        return "one person or queued contact"
    if "ACCOUNT" in entities or "company" in combined or "account" in combined:
        return "one company or account"
    return "one source record"


def phase_for(node: dict[str, Any]) -> str:
    name = str(node.get("name") or "").lower()
    node_type = str(node.get("nodeType") or "").lower()
    if node_type == "conditional":
        if any(term in name for term in ("persona", "qualified", "candidate", "select up to")):
            return "Account and person selection"
    if node_type == "trigger":
        return "Entry and configuration"
    if any(term in name for term in ("candidate", "persona", "qualified", "select up to", "person queue", "stage person")):
        return "Account and person selection"
    if any(term in name for term in ("reconciliation", "readback", "receipt", "verify salesforce", "verify lead", "no-send", "finalize")):
        return "Verification and terminal receipt"
    if any(term in name for term in ("existing", "suppression", "blocklist", "already", "current employer", "identity")) and "[external mutation]" not in name:
        return "Identity, existing-record, and safety checks"
    if any(term in name for term in ("enrich", "find & verify", "work email", "bettercontact", "provider")):
        return "Enrichment"
    if any(term in name for term in ("copy", "sequence", "generate", "repair", "qa", "subject", "body")):
        return "Message generation and validation"
    if any(term in name for term in ("configuration", "config", "preflight", "manifest", "adapter")):
        return "Entry and configuration"
    if any(term in name for term in ("[external mutation]", "upsert", "update", "add lead", "audience", "salesforce", "instantly", "campaignmember", "activation")):
        return "External activation"
    return "Supporting transformations"


def is_paid(node: dict[str, Any]) -> bool:
    name = str(node.get("name") or "").lower()
    node_type = str(node.get("nodeType") or "").lower()
    return "[paid]" in name or node_type == "agent" or any(
        term in name for term in ("enrich", "bettercontact", "claygent")
    )


def is_external_write(node: dict[str, Any]) -> bool:
    name = str(node.get("name") or "").lower()
    node_type = str(node.get("nodeType") or "").lower()
    if "[external mutation]" in name:
        return True
    if node_type != "tool" or "[read only]" in name or "approved?" in name:
        return False
    return any(term in name for term in ("upsert", "update", "add lead", "stage person", "create campaignmember", "finalize"))


def compact(items: list[str], limit: int) -> str:
    if not items:
        return "None identified from the available static graph."
    shown = items[:limit]
    suffix = f"; plus {len(items) - limit} more" if len(items) > limit else ""
    return "; ".join(shown) + suffix


def code_values(values: Any) -> str:
    if not isinstance(values, (list, tuple, set)):
        values = [values]
    return ", ".join(f"`{value}`" for value in values if value is not None and str(value) != "") or "none configured"


def status_counts(runs: Any) -> dict[str, int]:
    rows = list((runs or {}).get("data") or [])
    return dict(sorted(Counter(str(row.get("status") or "unknown") for row in rows).items()))


def assigned_literal_dict(code: str, target_name: str) -> dict[str, Any]:
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == target_name for target in targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict):
            return value
    return {}


def assigned_dict_keys(code: str, target_name: str) -> list[str]:
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == target_name for target in node.targets):
            continue
        if isinstance(node.value, ast.Dict):
            return [str(key.value) for key in node.value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)]
    return []


def extract_field_contract(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    approvals: dict[str, Any] = {}
    source_fields: set[str] = set()
    account_source_fields: set[str] = set()
    queue_source_fields: set[str] = set()
    salesforce_fields: list[str] = []
    salesforce_predicates: list[str] = []
    instantly_mapping: dict[str, str] = {}
    payload_fields: list[str] = []

    for node in nodes:
        code = str(node.get("code") or "")
        if not config:
            candidate = assigned_literal_dict(code, "config")
            if "campaign_state" in candidate or "target_title_include_terms" in candidate:
                config = candidate
        if not approvals:
            candidate = assigned_literal_dict(code, "approvals")
            if candidate:
                approvals = candidate
        observed_fields = set(re.findall(r"fields\.get\([\"']([^\"']+)[\"']", code))
        source_fields.update(observed_fields)
        lowered_name = str(node.get("name") or "").lower()
        account_entry_code = bool(re.search(
            r"[\"']?entry_entity_type[\"']?\s*(?::|=)\s*[\"']ACCOUNT[\"']",
            code,
        ))
        if ("adapter" in lowered_name and account_entry_code) or "audience launch-ready event adapter" in lowered_name:
            account_source_fields.update(observed_fields)
        if "person queue adapter" in lowered_name:
            queue_source_fields.update(observed_fields)
        if "crm_contact_lookup_query" in code:
            match = re.search(r"fields\s*=\s*[\"']([^\"']+)[\"']", code)
            if match:
                salesforce_fields = [item.strip() for item in match.group(1).split(",") if item.strip()]
            for predicate in (
                "AccountId = <resolved Salesforce Account ID>",
                "Email != null",
                "HasOptedOutOfEmail = false",
                "DoNotCall = false",
                "EmailBouncedReason = null",
                "No_Longer_at_Company__c = false",
                "ORDER BY LastModifiedDate DESC",
                "LIMIT 25",
            ):
                needle = predicate.replace("<resolved Salesforce Account ID>", "")
                if needle.strip() in code or predicate == "AccountId = <resolved Salesforce Account ID>":
                    salesforce_predicates.append(predicate)
        if "instantly_custom_variables" in code or "custom_variables=" in code:
            keys = assigned_dict_keys(code, "custom_variables")
            if keys:
                payload_fields = keys
        for tool in node.get("tools") or []:
            if not isinstance(tool, dict):
                continue
            action = str(tool.get("actionKey") or "")
            if "instantly" not in action or "add-lead" not in action:
                continue
            for key, mapping in (tool.get("inputMappingConfig") or {}).items():
                if not isinstance(mapping, dict):
                    continue
                if mapping.get("type") == "reference":
                    instantly_mapping[str(key)] = str(mapping.get("expression") or "")
                elif mapping.get("type") == "static":
                    instantly_mapping[str(key)] = repr(mapping.get("value"))

    account = {
        key: config.get(key)
        for key in (
            "account_employee_min", "account_employee_max", "account_countries",
            "account_industry_terms", "account_readiness_field", "account_qualification_field",
            "account_customer_fields", "account_open_opportunity_field",
        )
        if key in config
    }
    contact = {
        key: config.get(key)
        for key in (
            "people_per_company", "target_locations", "target_title_include_terms",
            "target_title_exclude_terms", "target_seniority_floor", "persona_rules",
        )
        if key in config
    }
    copy_contract = dict(config.get("campaign_copy_contract") or {})
    cache = {
        key: config.get(key)
        for key in ("person_cache_ttl_days", "email_cache_ttl_days")
        if key in config
    }
    budget = {
        key: config.get(key)
        for key in (
            "expected_account_count", "max_companies_per_campaign", "projected_credits_per_person",
            "projected_fixed_credits_per_company", "approved_total_clay_credits",
            "approved_byoa_cost_usd", "preview_count_confirmed", "segment_count_receipt",
        )
        if key in config
    }
    return {
        "account": account,
        "contact": contact,
        "copy": copy_contract,
        "cache": cache,
        "budget": budget,
        "approval_fields": list(approvals),
        "source_fields": sorted(source_fields),
        "account_source_fields": sorted(account_source_fields),
        "queue_source_fields": sorted(queue_source_fields),
        "salesforce_contact_fields": salesforce_fields,
        "salesforce_contact_predicates": salesforce_predicates,
        "instantly_add_mapping": instantly_mapping,
        "instantly_custom_variables": payload_fields,
    }


def explain_contract_finding(finding: dict[str, Any]) -> str:
    node = clean_name(finding.get("node"))
    expected = finding.get("expected")
    observed = finding.get("observed")
    evidence = finding.get("evidence") or {}
    if finding.get("code") == "internal_sequence_cardinality_mismatch":
        parts = ", ".join(f"{key.replace('_', ' ')} says {values}" for key, values in evidence.items())
        return f"{node} contradicts itself: {parts}."
    if finding.get("code") == "cross_layer_sequence_cardinality_mismatch":
        return f"{node} handles {observed} emails while the canonical campaign contract requires {expected}."
    return f"{node}: {str(finding.get('code') or 'semantic contract conflict').replace('_', ' ')}."


def build_model(
    graph: dict[str, Any],
    validation: dict[str, Any] | None = None,
    runs: dict[str, Any] | None = None,
    workflow: dict[str, Any] | None = None,
    triggers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation = validation or {}
    runs = runs or {}
    workflow = workflow or {}
    triggers = triggers or {}
    nodes = list(graph.get("nodes") or [])
    fields = extract_field_contract(nodes)
    summary = graph.get("summary") or {}
    trigger_rows = list(triggers.get("data") or [])
    trigger_nodes = [node for node in nodes if str(node.get("nodeType") or "").lower() == "trigger"]
    systems = infer_systems(nodes)
    unit = infer_unit(nodes, trigger_rows)

    paid = [node for node in nodes if is_paid(node)]
    writes = [node for node in nodes if is_external_write(node)]
    approvals = [node for node in nodes if name_matches(node, ("approved?", "approval", "preflight"))]
    decisions = [node for node in nodes if str(node.get("nodeType") or "").lower() == "conditional"]
    suppressions = [node for node in nodes if name_matches(node, ("suppression", "blocklist", "unsubscribe", "bounce", "already satisfied", "existing instantly"))]
    readbacks = [node for node in nodes if name_matches(node, ("reconciliation", "readback", "receipt", "[read only] verify", "verify salesforce", "verify lead"))]

    phase_nodes: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        phase_nodes.setdefault(phase_for(node), []).append(node)
    ordered_phases = [label for label, _ in PHASES] + ["Supporting transformations"]
    phases = [
        {"name": label, "count": len(phase_nodes[label]), "steps": unique_names(phase_nodes[label])}
        for label in ordered_phases
        if phase_nodes.get(label)
    ]

    contract = analyze(graph, validation)
    counts = status_counts(runs)
    run_count = sum(counts.values())
    semantic_blockers = int((contract.get("summary") or {}).get("blockers") or 0)
    structural_known = "valid" in validation
    structural_valid = validation.get("valid") is True and not validation.get("errors")

    if systems:
        system_phrase = ", ".join(systems)
        purpose = (
            f"This workflow moves {unit} through qualification, missing-data lookups, safety checks, "
            f"and campaign preparation. When its approval gates allow it, it may change records in {system_phrase}, "
            "then uses verification steps intended to confirm those changes."
        )
    else:
        purpose = f"This workflow moves {unit} through a series of checks and transformations before producing a terminal result."

    if semantic_blockers:
        proof_summary = (
            f"The static graph contains {semantic_blockers} semantic contract blocker(s). "
            "The configured journey should not be described as launch-ready."
        )
    elif run_count:
        proof_summary = (
            f"There are {run_count} recorded run(s) with Clay statuses {counts}. "
            "Those statuses prove orchestration state, not final destination success."
        )
    else:
        proof_summary = "No run evidence is present, so this explains configured behavior rather than observed production behavior."

    unknowns: list[str] = []
    if not structural_known:
        unknowns.append("No structural validation result was supplied.")
    elif not structural_valid:
        unknowns.append("The graph does not currently pass structural validation.")
    if semantic_blockers:
        unknowns.append(f"Resolve {semantic_blockers} semantic contract blocker(s) before behavioral testing.")
    if run_count == 0:
        unknowns.append("No bounded run proves that a record can traverse the intended branches.")
    unknowns.append("Clay run status alone does not prove Audience, CRM, or sequencer readback success.")

    if semantic_blockers:
        next_check = "Align the conflicting contract consumers, then rerun structural and semantic validation before any canary."
    elif not structural_known or not structural_valid:
        next_check = "Run Clay structural validation and resolve every error before behavioral testing."
    elif run_count == 0:
        next_check = "Run one explicitly approved bounded canary and capture its terminal receipt plus independent destination readbacks."
    else:
        next_check = "Match each terminal run outcome to independent destination readbacks before calculating success or scaling."

    return {
        "workflow": {
            "id": workflow.get("id") or summary.get("workflowId"),
            "name": workflow.get("name") or summary.get("workflowName") or "Clay Workflow",
            "url": workflow.get("url") or summary.get("workflowUrl"),
        },
        "purpose": purpose,
        "unit_of_work": unit,
        "systems": systems,
        "field_contract": fields,
        "structure": {
            "node_count": summary.get("nodeCount") or len(nodes),
            "edge_count": len(summary.get("edges") or []),
            "phases": phases,
        },
        "triggers": unique_names(trigger_nodes) or [str(row.get("name") or row.get("entityType") or "Configured trigger") for row in trigger_rows],
        "approvals": unique_names(approvals),
        "decisions": unique_names(decisions),
        "suppressions": unique_names(suppressions),
        "paid_steps": unique_names(paid),
        "external_writes": unique_names(writes),
        "readbacks": unique_names(readbacks),
        "evidence": {
            "structural_validation_known": structural_known,
            "structural_valid": structural_valid if structural_known else None,
            "semantic_blockers": semantic_blockers,
            "semantic_findings": [explain_contract_finding(item) for item in (contract.get("findings") or [])],
            "run_count": run_count,
            "run_status_counts": counts,
            "business_outcome_proven": False,
            "summary": proof_summary,
        },
        "unknowns": unknowns,
        "next_check": next_check,
    }


def render_markdown(model: dict[str, Any], audience: str = "general") -> str:
    workflow = model["workflow"]
    limit = 3 if audience == "executive" else 8
    phase_map = {phase["name"]: phase["steps"] for phase in model["structure"]["phases"]}
    triggers = model["triggers"]
    safe_trigger = any("empty" in item.lower() or "safe" in item.lower() for item in triggers)
    has_salesforce = "Salesforce" in model["systems"]
    has_audience = "Clay Audiences" in model["systems"]
    has_instantly = "Instantly" in model["systems"]
    has_queue = "person or queued contact" in model["unit_of_work"]
    systems = ", ".join(model["systems"]) or "its downstream destination"
    field_contract = model.get("field_contract") or {}
    account_filters = field_contract.get("account") or {}
    contact_filters = field_contract.get("contact") or {}
    copy_filters = field_contract.get("copy") or {}
    cache_filters = field_contract.get("cache") or {}
    budget_filters = field_contract.get("budget") or {}

    lines = [f"# {workflow['name']} — The Story of One Record", "", "## The short version", "", model["purpose"]]
    if workflow.get("url"):
        lines.extend(["", f"Workflow: {workflow['url']}"])

    lines.extend(["", "## The story", ""])
    if safe_trigger:
        lines.append(
            "The story begins with the doors deliberately closed. One configured source is an empty safety control, "
            "and the real account source must be rebound before launch. That means simply publishing the template is "
            "not supposed to release a campaign. A company only enters once an operator chooses the source and the "
            "campaign configuration passes its opening checks."
        )
    else:
        lines.append(
            f"The story begins when {model['unit_of_work']} arrives through one of the configured starting points. "
            "The workflow first checks its campaign configuration before allowing the record to move toward paid work "
            "or an external system."
        )

    if account_filters:
        employee_min = account_filters.get("account_employee_min")
        employee_max = account_filters.get("account_employee_max")
        lines.extend(["", "That opening account gate is concrete, not a vague fit score."])
        account_source_fields = field_contract.get("account_source_fields") or []
        if account_source_fields:
            lines.extend([
                "",
                f"The account adapter reads {code_values(account_source_fields)}. It normalizes those values into "
                "`company_name`, `domain`, `company_linkedin_url`, `sfdc_account_id`, `employee_count`, `industry`, "
                "`country`, `city`, and `state` before applying the campaign filters.",
            ])
        lines.extend([
            "",
            f"To continue, `{account_filters.get('account_readiness_field')}` and "
            f"`{account_filters.get('account_qualification_field')}` must be true; employee count must be between "
            f"**{employee_min} and {employee_max}**; `Domain` must exist; and "
            f"`{account_filters.get('account_open_opportunity_field')}` must be zero. Any truthy value in "
            f"{code_values(account_filters.get('account_customer_fields') or [])} stops the account as an existing customer.",
            "",
            f"The allowed country values are {code_values(account_filters.get('account_countries') or [])}. "
            f"The normalized `Industry` must contain at least one of: "
            f"{code_values(account_filters.get('account_industry_terms') or [])}.",
        ])

    if budget_filters:
        lines.extend([
            "",
            "The spend gate is also field-based. It computes `projected_worst_case_clay_credits` as "
            "`expected_account_count × (projected_fixed_credits_per_company + people_per_company × projected_credits_per_person)`. "
            "It then requires `expected_account_count > 0`, `max_companies_per_campaign > 0`, the expected count not to "
            "exceed that maximum, `preview_count_confirmed = true`, a `segment_count_receipt` beginning with the same count, "
            "and the projection not to exceed `approved_total_clay_credits`.",
            "",
            f"In this untouched template those values are `expected_account_count = {budget_filters.get('expected_account_count')}`, "
            f"`max_companies_per_campaign = {budget_filters.get('max_companies_per_campaign')}`, "
            f"`projected_credits_per_person = {budget_filters.get('projected_credits_per_person')}`, "
            f"`approved_total_clay_credits = {budget_filters.get('approved_total_clay_credits')}`, and "
            f"`preview_count_confirmed = {budget_filters.get('preview_count_confirmed')}`. Those defaults intentionally keep "
            "the story in `DRAFT_BLOCKED` until a real campaign is configured and approved.",
        ])

    if phase_map.get("Account and person selection"):
        if has_salesforce:
            selection_story = (
                "Once the company is inside, the workflow looks for people it may already know in Salesforce. It applies "
                "the campaign's title rules and exclusions, preferring qualified existing contacts before paying to discover "
                "new ones. If Salesforce has nobody suitable, the workflow can take the net-new path instead."
            )
        else:
            selection_story = (
                "Once the record is inside, the workflow applies its qualification rules and chooses the people who are "
                "allowed to continue. Records that do not match the campaign's configured audience stop here."
            )
        if has_queue:
            selection_story += (
                " Each selected person is then given a separate queue record, so five contacts from one company become "
                "five traceable journeys rather than one account-level run that can silently lose people."
            )
        lines.extend(["", selection_story])

        if contact_filters:
            lines.extend([
                "",
                f"For the person search, `people_per_company` is **{contact_filters.get('people_per_company')}** and "
                f"`target_seniority_floor` is `{contact_filters.get('target_seniority_floor')}`. The Clay search maps "
                "`target_title_keywords_csv` to `job_title_keywords`, `target_title_exclude_keywords_csv` to "
                "`job_title_exclude_keywords`, uses `job_title_seniority_match_mode = floor`, sets "
                "`include_past_experiences = false`, and searches only "
                f"{code_values(contact_filters.get('target_locations') or [])}.",
                "",
                f"A `Title` is included when it contains one of {code_values(contact_filters.get('target_title_include_terms') or [])}. "
                f"It is rejected when it contains one of {code_values(contact_filters.get('target_title_exclude_terms') or [])}. "
                "The selector also requires `full_name` and `linkedin_url`, then ranks survivors by title: "
                "`chief` = 6, `vice president`/`vp` = 5, `head` = 4, `director` = 3, "
                "`senior manager` = 2, and `manager` = 1.",
            ])

        queue_fields = field_contract.get("queue_source_fields") or []
        if has_queue and queue_fields:
            lines.extend([
                "",
                "When that person returns through the durable queue, the adapter reads the actual Clay fields "
                f"{code_values(queue_fields)}. It stops if both `Email` and `LinkedIn URL` are missing, or if any of "
                "`Campaign Key`, `Campaign Workflow ID`, `Campaign Config Hash`, or `Campaign Idempotency Key` is absent. "
                "`Campaign Queue Status` must equal `QUEUED`, and the staged campaign key, workflow ID, and config hash must "
                "still match the current manifest.",
            ])

        sf_fields = field_contract.get("salesforce_contact_fields") or []
        sf_predicates = field_contract.get("salesforce_contact_predicates") or []
        if has_salesforce and sf_fields:
            lines.extend([
                "",
                "The Salesforce-first path is equally specific. It queries `Contact` using "
                f"{code_values(sf_predicates)} and selects {code_values(sf_fields)}. Even after Salesforce returns a row, "
                "the workflow rejects it if `HasOptedOutOfEmail`, `DoNotCall`, `EmailBouncedReason`, or "
                "`No_Longer_at_Company__c` indicates risk, if `Title` misses the configured include terms or hits an "
                "exclude term, or if `LinkedIn_URL__c` is blank.",
            ])

    if phase_map.get("Identity, existing-record, and safety checks"):
        safety_story = (
            "Now the workflow slows down and asks whether this person is both real and safe to contact. It checks stable "
            "identity, current employer, title, existing records, and evidence that the person may already have been handled. "
        )
        if has_instantly:
            safety_story += (
                "Instantly is consulted before enrollment so an existing lead, reply, unsubscribe, bounce, or blocklist can "
                "turn the journey into a deliberate no-send instead of a duplicate or unsafe outreach attempt."
            )
        else:
            safety_story += "A person who is ineligible or already satisfied leaves through a safe no-action path."
        lines.extend(["", safety_story])

        if cache_filters:
            lines.extend([
                "",
                f"Cached person evidence is reused only when `cached_persona` exists, `cached_employer_match = true`, "
                f"and `cached_person_enriched_at` is no more than **{cache_filters.get('person_cache_ttl_days')} days** old. "
                f"A cached email is reused only when `cached_validated_email` exists and `cached_email_enriched_at` is no "
                f"more than **{cache_filters.get('email_cache_ttl_days')} days** old. Employer identity passes when "
                "`company_linkedin_url` exactly matches `current_employer_linkedin_url`, or normalized `domain` exactly "
                "matches `current_employer_domain`; provider evidence must also say `is_current = true`.",
                "",
                "For email routing, an existing `email` moves straight ahead only when `email_validation_status` is one of "
                "`valid`, `safe`, `safe_to_send`, or `deliverable`. A present but untrusted email is sent to validation; a "
                "missing email is sent to the email-finding function; and `employer_verified_final = false` blocks the person.",
            ])

    if phase_map.get("Enrichment"):
        lines.extend([
            "",
            "Only after those cheaper checks does the workflow spend credits to fill the remaining gaps. It tries to confirm "
            "the person's employer and obtain a usable work email, while preserving data it already trusts. The point is not "
            "to enrich every row; it is to buy only the missing evidence needed for this particular person to continue.",
        ])

    if phase_map.get("Message generation and validation"):
        lines.extend([
            "",
            "With a qualified person and enough identity in hand, the workflow prepares the campaign message. An AI step drafts "
            "the sequence, but the AI is not allowed to grade its own work. Deterministic code checks the required fields and "
            "copy contract, one bounded repair is available, and a separate quality review decides whether the result is safe "
            "to turn into a destination payload.",
        ])
        if copy_filters:
            lines.extend([
                "",
                f"The declared copy contract is `sequence_length = {copy_filters.get('sequence_length')}`, with subject lines "
                f"between **{copy_filters.get('subject_min_words')} and {copy_filters.get('subject_max_words')} words**. "
                f"The five body targets are {code_values(copy_filters.get('body_word_targets') or [])} words with "
                f"`body_word_tolerance_pct = {copy_filters.get('body_word_tolerance_pct')}`. Only email "
                f"{code_values(copy_filters.get('greeting_email_numbers') or [])} may begin with a greeting; email "
                f"`{copy_filters.get('numbered_reply_email')}` must contain numbered `1.`, `2.`, and `3.` sections; and "
                f"the prohibited terms are {code_values(copy_filters.get('prohibited_terms') or [])}.",
            ])

    lines.extend(["", "## The tension", ""])
    if model["evidence"]["semantic_findings"]:
        lines.append(
            "This is where the template's story currently breaks. The campaign says it is building a five-email sequence, "
            "and later validators and payload builders expect five. But the generation, repair, and review layer still speaks "
            "the language of a two-email sequence:"
        )
        lines.extend([""] + [f"- {item}" for item in model["evidence"]["semantic_findings"]])
        lines.extend([
            "",
            "Clay's graph validator does not catch this because every node can still be connected correctly. The disagreement "
            "is about meaning, not wiring. Until those contracts agree, a person can travel a long way through the workflow "
            "only to arrive at a payload that cannot satisfy the campaign it was meant to join.",
        ])
    else:
        lines.append(
            "At every risky boundary, the workflow is designed to prefer stopping over guessing. Missing approval blocks a write; "
            "missing identity blocks outreach; an already-handled or suppressed person becomes a valid no-send; and an uncertain "
            "external result requires verification before anyone retries it."
        )

    if phase_map.get("External activation"):
        lines.extend([
            "",
            "If the person survives the checks and the payload is complete, the workflow still does not immediately launch them. "
            "Audience, CRM, and sending-platform changes are separated behind their own approvals. Only then may the workflow "
            f"update {systems}. Each write is meant to be safe to rerun without creating the same side effect twice.",
        ])

        if field_contract.get("approval_fields"):
            lines.extend([
                "",
                "Approval is bound to the exact configuration, not just a human-readable campaign name. The gate checks "
                "`approved_config_hash`, `approval_reference`, `approver`, `approved_at`, and `expires_at`. Preview additionally "
                "requires `spend_approved`, `copy_generation_approved`, and `audience_write_approved`. Activation adds "
                "`salesforce_write_approved`, `instantly_write_approved`, `outbound_activation_approved`, "
                "`activation_write_approved`, and `byoa_cost_approved`; the configured and approved Salesforce campaign IDs "
                "must match, and the configured and approved Instantly campaign IDs must match.",
            ])

        instantly_mapping = field_contract.get("instantly_add_mapping") or {}
        payload_fields = field_contract.get("instantly_custom_variables") or []
        if instantly_mapping:
            mapped = [f"`{key}` ← `{value}`" for key, value in instantly_mapping.items()]
            lines.extend([
                "",
                "The final Instantly payload must have `email`, `title`, `linkedin_profile`, `campaign_key`, and every "
                "`subject_1`…`subject_5` plus `body_1`…`body_5`. Its custom variables are "
                f"{code_values(payload_fields)}, and the add-lead tool maps {', '.join(mapped)}. "
                "`skip_if_in_workspace` is statically `True`, and immediately before the add, a workspace-wide lookup by "
                "`email` blocks statuses `-1`, `-2`, `-3`, `bounced`, `unsubscribed`, `replied`, or `skipped`, any "
                "`email_reply_count`, any non-null `email_replied_step`, or an existing lead outside the approved campaign.",
            ])

    if phase_map.get("Verification and terminal receipt"):
        lines.extend([
            "",
            "After a write, the workflow turns around and looks back at the destination. That readback—called reconciliation—is "
            "the difference between 'we asked Salesforce or Instantly to do something' and 'we proved the intended record now "
            "exists in the right place.' The resulting receipt is supposed to preserve how this person's journey ended.",
        ])

    lines.extend([
        "",
        "## How the story can end",
        "",
        "The happy ending is not merely a green Clay run. It is a person who was activated in every approved destination and then "
        "independently found there. Other endings are also legitimate: the person was already present, was safely suppressed, "
        "needed human review, failed at a provider, was rejected by a destination, or reached a write that could not be reconciled. "
        "Those endings must remain distinct because they imply very different next actions.",
        "",
        "## What is real today",
        "",
        "The node names and descriptions tell us the intended plot. The code, conditions, schemas, mappings, and approval checks "
        "decide what the workflow can actually enforce. Run results and destination readbacks are the only proof that the story "
        "happened in the real world.",
        "",
        model["evidence"]["summary"],
    ])

    lines.extend(["", "## Receipts from the graph", ""])
    lines.extend([
        f"- **Starting points:** {compact(triggers, limit)}",
        f"- **Approval gates:** {compact(model['approvals'], limit)}",
        f"- **Potentially paid steps:** {compact(model['paid_steps'], limit)}",
        f"- **External writes:** {compact(model['external_writes'], limit)}",
        f"- **Suppression paths:** {compact(model['suppressions'], limit)}",
        f"- **Readbacks and receipts:** {compact(model['readbacks'], limit)}",
    ])

    lines.extend(["", "## What remains unknown", ""])
    lines.extend(f"- {item}" for item in model["unknowns"])

    lines.extend([
        "",
        f"In one sentence: {model['unit_of_work'].capitalize()} enters, passes configuration, eligibility, safety, and quality gates, may update {systems}, and still needs destination readback before the business outcome is proven.",
        "",
        f"Next check: {model['next_check']}",
    ])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explain a Clay Workflow evidence pack in plain English.")
    parser.add_argument("source", type=Path, help="Evidence directory or graph.json path")
    parser.add_argument("--audience", choices=("general", "executive", "operator", "technical"), default="general")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    directory = args.source if args.source.is_dir() else args.source.parent
    graph_path = directory / "graph.json" if args.source.is_dir() else args.source
    try:
        model = build_model(
            load_json(graph_path, required=True),
            load_json(directory / "validation.json"),
            load_json(directory / "runs.json"),
            load_json(directory / "workflow.json"),
            load_json(directory / "triggers.json"),
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(model, indent=2, sort_keys=True))
    else:
        print(render_markdown(model, args.audience), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
