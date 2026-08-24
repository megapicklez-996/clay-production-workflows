import json
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_workflow import audit
from explain_workflow import build_model, render_markdown
from summarize_runs import classify_error, summarize
from validate_contract import analyze
from check_evidence_compat import analyze_evidence
from validate_graph_controls import analyze_graph_controls
from validate_manifest import analyze_manifest, configuration_hash
from validate_reconciliation import analyze_reconciliation


def fixture(name):
    return json.loads((ROOT / "evals" / "fixtures" / name).read_text(encoding="utf-8"))


class ContractTests(unittest.TestCase):
    def test_valid_five_email_contract(self):
        result = analyze(fixture("valid-production-workflow.json"), {"valid": True})
        self.assertTrue(result["valid"])
        self.assertEqual(result["canonical_sequence_length"], 5)
        self.assertEqual(result["summary"]["blockers"], 0)

    def test_detects_two_vs_five_mismatch(self):
        result = analyze(fixture("sequence-contract-mismatch.json"), {"valid": True})
        self.assertFalse(result["valid"])
        self.assertEqual(result["canonical_sequence_length"], 5)
        self.assertGreaterEqual(result["summary"]["blockers"], 1)


class ManifestTests(unittest.TestCase):
    def test_valid_draft_manifest(self):
        result = analyze_manifest(fixture("valid-campaign-manifest.json"))
        self.assertTrue(result["valid"])
        self.assertTrue(result["configuration_hash"].startswith("sha256:"))

    def test_configuration_change_invalidates_approval(self):
        manifest = fixture("valid-campaign-manifest.json")
        manifest["approvals"].update({
            "paid_work": True,
            "config_hash": configuration_hash(manifest),
            "reference": "APPROVAL-1",
            "approver": "growth-lead",
            "approved_at": "2030-01-01T00:00:00Z",
            "expires_at": "2099-01-01T00:00:00Z",
        })
        self.assertTrue(analyze_manifest(manifest)["valid"])
        manifest["budgets"]["worst_case_credits_per_record"] = 3
        result = analyze_manifest(manifest)
        self.assertFalse(result["valid"])
        self.assertIn("approval_config_hash_mismatch", {item["code"] for item in result["findings"]})

    def test_template_placeholders_block_instantiation(self):
        template = json.loads((ROOT / "assets" / "campaign-manifest.template.json").read_text())
        result = analyze_manifest(template)
        self.assertFalse(result["valid"])
        self.assertIn("manifest_placeholders_present", {item["code"] for item in result["findings"]})

    def test_live_write_requires_owners_kill_switch_and_retention(self):
        manifest = fixture("valid-campaign-manifest.json")
        manifest["ownership"]["incident_owner"] = ""
        manifest["operations"]["kill_switch"]["pause_method"] = ""
        manifest["data_handling"]["evidence_retention_days"] = -1
        manifest["approvals"].update({
            "sequencer_write": True,
            "config_hash": configuration_hash(manifest),
            "reference": "APPROVAL-OPS-1",
            "approver": "growth-lead",
            "approved_at": "2030-01-01T00:00:00Z",
            "expires_at": "2099-01-01T00:00:00Z",
        })
        result = analyze_manifest(manifest)
        codes = {item["code"] for item in result["findings"]}
        self.assertFalse(result["valid"])
        self.assertIn("production_owners_missing", codes)
        self.assertIn("kill_switch_incomplete", codes)
        self.assertIn("evidence_retention_invalid", codes)


class GraphControlTests(unittest.TestCase):
    def test_valid_graph_has_payload_suppression_and_readback(self):
        result = analyze_graph_controls(
            fixture("valid-governed-graph.json"), fixture("valid-campaign-manifest.json")
        )
        self.assertTrue(result["valid"], result["findings"])

    def test_missing_payload_fields_readback_and_terminal_block(self):
        result = analyze_graph_controls(
            fixture("unsafe-governed-graph.json"), fixture("valid-campaign-manifest.json")
        )
        codes = {item["code"] for item in result["findings"]}
        self.assertFalse(result["valid"])
        self.assertIn("required_payload_fields_not_mapped", codes)
        self.assertIn("external_write_without_downstream_readback", codes)
        self.assertIn("leaf_without_terminal_outcome", codes)
        self.assertIn("idempotency_control_not_detected", codes)


class RunSummaryTests(unittest.TestCase):
    def test_completed_does_not_become_activation_rate(self):
        result = summarize(fixture("runs-mixed.json"), fixture("provider-html-failure.json"))
        self.assertIsNone(result["activation_rate"])
        self.assertTrue(result["completed_is_not_business_success"])
        self.assertEqual(result["failure_category_counts"]["provider_contract_failure"], 1)

    def test_blocklist_is_destination_rejection(self):
        category, action = classify_error("Lead is in blocklist")
        self.assertEqual(category, "destination_rejection")
        self.assertIn("do_not_bypass", action)


class ReconciliationTests(unittest.TestCase):
    def test_verified_canary_can_prove_live_ready(self):
        result = analyze_reconciliation(fixture("valid-reconciliation-receipts.json"))
        self.assertTrue(result["valid"])
        self.assertTrue(result["live_ready_proven"])

    def test_duplicate_rerun_detects_two_activations(self):
        result = analyze_reconciliation(fixture("duplicate-reconciliation-receipts.json"))
        self.assertFalse(result["valid"])
        self.assertIn(
            "duplicate_activation_for_idempotency_key",
            {item["code"] for item in result["findings"]},
        )

    def test_timeout_after_submission_requires_readback(self):
        result = analyze_reconciliation(fixture("ambiguous-timeout-receipt.json"))
        self.assertFalse(result["valid"])
        finding = next(item for item in result["findings"] if item["code"] == "external_write_side_effect_unknown")
        self.assertEqual(finding["safe_next_action"], "read_destination_before_retry")

    def test_receipt_must_match_manifest_configuration(self):
        manifest = fixture("valid-campaign-manifest.json")
        result = analyze_reconciliation(
            fixture("valid-reconciliation-receipts.json"), configuration_hash(manifest)
        )
        self.assertFalse(result["valid"])
        self.assertIn("receipt_config_hash_mismatch", {item["code"] for item in result["findings"]})


def write_evidence(directory, *, graph=None, manifest=None, receipts=None, runs=None):
    values = {
        "collector-metadata.json": {"evidence_contract_version": 1, "clay_cli_version": "fixture"},
        "identity.json": {"workspace": {"id": "ws_fixture"}, "user": {"id": "user_fixture"}},
        "workflow.json": {"id": "wf_fixture_governed", "name": "Governed Fixture"},
        "graph.json": graph or fixture("valid-governed-graph.json"),
        "validation.json": {"valid": True, "errors": [], "warnings": []},
        "snapshots.json": {"data": []},
        "triggers.json": {"data": []},
        "runs.json": runs or {"data": []},
        "failed-runs.json": {"data": []},
    }
    if manifest is not None:
        values["manifest.json"] = manifest
    if receipts is not None:
        values["receipts.json"] = receipts
    for name, value in values.items():
        (directory / name).write_text(json.dumps(value), encoding="utf-8")


class EvidenceCompatibilityTests(unittest.TestCase):
    def test_current_evidence_shape_is_compatible(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            write_evidence(directory)
            self.assertTrue(analyze_evidence(directory)["compatible"])

    def test_changed_graph_shape_blocks_automated_audit(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            graph = fixture("valid-governed-graph.json")
            graph["nodes"] = {"unexpected": "shape"}
            write_evidence(directory, graph=graph)
            result = analyze_evidence(directory)
            self.assertFalse(result["compatible"])
            self.assertIn("graph_shape_changed", {item["code"] for item in result["findings"]})


class AuditTests(unittest.TestCase):
    def test_untested_mismatch_is_draft_blocked(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            write_evidence(directory, graph=fixture("sequence-contract-mismatch.json"))
            result = audit(directory)
            self.assertEqual(result["readiness_ceiling"], "DRAFT_BLOCKED")
            self.assertFalse(result["live_ready_proven"])

    def test_verified_canary_and_governance_can_reach_live_ready(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            manifest = copy.deepcopy(fixture("valid-campaign-manifest.json"))
            manifest["campaign"].update({"state": "LIVE_READY", "ready": True})
            manifest["approvals"].update({
                "sequencer_write": True,
                "outbound_activation": True,
                "config_hash": configuration_hash(manifest),
                "reference": "APPROVAL-LIVE-1",
                "approver": "growth-lead",
                "approved_at": "2030-01-01T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
            })
            receipts = copy.deepcopy(fixture("valid-reconciliation-receipts.json"))
            receipts["data"][0]["config_hash"] = configuration_hash(manifest)
            write_evidence(
                directory,
                manifest=manifest,
                receipts=receipts,
                runs={"data": [{"status": "completed"}]},
            )
            result = audit(directory)
            self.assertEqual(result["readiness_ceiling"], "LIVE_READY", result)
            self.assertTrue(result["live_ready_proven"])


class ExplainerTests(unittest.TestCase):
    def test_plain_english_model_preserves_evidence_boundaries(self):
        model = build_model(
            fixture("explainable-workflow.json"),
            {"valid": True, "errors": [], "warnings": []},
            {"data": [{"status": "completed"}]},
        )
        self.assertEqual(model["unit_of_work"], "one person or queued contact")
        self.assertIn("Salesforce", model["systems"])
        self.assertIn("Instantly", model["systems"])
        self.assertTrue(model["paid_steps"])
        self.assertTrue(model["external_writes"])
        self.assertTrue(model["readbacks"])
        self.assertFalse(model["evidence"]["business_outcome_proven"])
        self.assertEqual(model["field_contract"]["account"]["account_employee_min"], 250)
        self.assertIn("marketing operations", model["field_contract"]["contact"]["target_title_include_terms"])
        self.assertIn("HasOptedOutOfEmail = false", model["field_contract"]["salesforce_contact_predicates"])
        self.assertIn("Cleaned Domain", model["field_contract"]["account_source_fields"])

    def test_markdown_explains_journey_and_next_proof(self):
        model = build_model(fixture("explainable-workflow.json"), {"valid": True}, {"data": []})
        rendered = render_markdown(model)
        for required in (
            "The story",
            "Each selected person is then given a separate queue record",
            "Only after those cheaper checks does the workflow spend credits",
            "`Campaign Launch Ready`",
            "`# Open Oppty` must be zero",
            "`marketing operations`",
            "`HasOptedOutOfEmail = false`",
            "How the story can end",
            "What is real today",
            "Receipts from the graph",
            "In one sentence:",
            "Next check:",
        ):
            self.assertIn(required, rendered)
        self.assertLess(rendered.index("## The story"), rendered.index("## Receipts from the graph"))
        self.assertNotIn("1. **Entry and configuration:**", rendered)
        self.assertIn("configured behavior rather than observed production behavior", rendered)

    def test_explainer_translates_semantic_blocker_before_canary(self):
        model = build_model(fixture("sequence-contract-mismatch.json"), {"valid": True}, {"data": []})
        rendered = render_markdown(model)
        self.assertIn("handles 2 emails", rendered)
        self.assertIn("requires 5", rendered)
        self.assertIn("before any canary", rendered)


if __name__ == "__main__":
    unittest.main()
