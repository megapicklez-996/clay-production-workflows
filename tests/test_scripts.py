import json
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


class AuditTests(unittest.TestCase):
    def test_untested_mismatch_is_draft_blocked(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            files = {
                "graph.json": fixture("sequence-contract-mismatch.json"),
                "validation.json": {"valid": True, "errors": [], "warnings": []},
                "runs.json": {"data": []},
                "failed-runs.json": {"data": []},
                "workflow.json": {"id": "wf_fixture_mismatch", "name": "Mismatch"},
                "triggers.json": {"data": []}
            }
            for name, value in files.items():
                (directory / name).write_text(json.dumps(value), encoding="utf-8")
            result = audit(directory)
            self.assertEqual(result["readiness_ceiling"], "DRAFT_BLOCKED")
            self.assertFalse(result["live_ready_proven"])


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
