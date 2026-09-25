"""
Unit tests for Startup Model Tracing, Model Audit Log, and Union Alpha / Pareto 26.9 Integration.
"""
import unittest
from pathlib import Path
from database.db_manager import DatabaseManager
from engine.model_scanner import ModelScanner
from engine.auto_router.registry import ModelRegistry
from engine.auto_router.coding_router import AutoCodingRouter
from live_agent import _get_cloud_credentials, MODEL_CHOICES


class TestModelTracingAndUnionAlpha(unittest.TestCase):
    def setUp(self):
        self.test_db_path = Path("tests/test_trace.db")
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        self.db = DatabaseManager(self.test_db_path)

    def tearDown(self):
        if self.test_db_path.exists():
            try:
                self.test_db_path.unlink()
            except Exception:
                pass

    def test_model_audit_log_crud_and_summary(self):
        """Verifies model_audit_log insertion, query filtering, and summary statistics."""
        events = [
            {
                "timestamp": "2026-09-19T20:00:00",
                "provider_id": "openrouter",
                "event_type": "added_free",
                "model_name": "deepseek/deepseek-v4-flash-0731:free",
                "display_name": "DeepSeek V4 Flash",
                "is_free": 1,
                "change_summary": "New FREE model discovered",
                "details": {"context_length": 1000000}
            },
            {
                "timestamp": "2026-09-19T20:01:00",
                "provider_id": "openrouter",
                "event_type": "changed",
                "model_name": "unbiased/pareto",
                "display_name": "Pareto 26.9",
                "is_free": 0,
                "change_summary": "Pricing shifted from FREE to PAID",
                "details": {"old_free": True, "new_free": False}
            },
            {
                "timestamp": "2026-09-19T20:02:00",
                "provider_id": "openrouter",
                "event_type": "removed",
                "model_name": "deprecated/old-coder",
                "display_name": "Old Coder",
                "is_free": 1,
                "change_summary": "Model removed / discontinued",
                "details": {}
            }
        ]

        inserted = self.db.log_model_trace_events(events)
        self.assertEqual(inserted, 3)

        # Query all
        logs = self.db.get_recent_model_audit_logs(limit=10)
        self.assertEqual(len(logs), 3)

        # Query filtered
        free_logs = self.db.get_recent_model_audit_logs(event_type="added_free")
        self.assertEqual(len(free_logs), 1)
        self.assertEqual(free_logs[0]["model_name"], "deepseek/deepseek-v4-flash-0731:free")

        # Summary check
        summary = self.db.get_model_audit_summary()
        self.assertEqual(summary["total_events"], 3)
        self.assertEqual(summary["added_free"], 1)
        self.assertEqual(summary["changed"], 1)
        self.assertEqual(summary["removed"], 1)

    def test_tracer_diff_detection(self):
        """Verifies ModelScanner.trace_provider_models diff calculation."""
        # Step 1: Initial baseline scan with 2 models (1 free, 1 paid)
        initial_models = [
            {"model_name": "provider/free-coder", "display_name": "Free Coder", "is_free": 1, "context_length": 32768},
            {"model_name": "provider/paid-sota", "display_name": "Paid SOTA", "is_free": 0, "context_length": 128000},
        ]
        diff1 = ModelScanner.trace_provider_models("mock_provider", initial_models, sync_to_db=False)
        self.assertEqual(len(diff1["added_free"]), 1)
        self.assertEqual(len(diff1["added_paid"]), 1)

        # Save to DB to establish existing state
        self.db.save_discovered_models("mock_provider", initial_models)

        # Step 2: Next scan where:
        # - provider/free-coder shifts from free to paid and context expands
        # - provider/paid-sota is removed
        # - a new free model is added
        updated_models = [
            {"model_name": "provider/free-coder", "display_name": "Free Coder", "is_free": 0, "context_length": 65536},
            {"model_name": "provider/brand-new-free", "display_name": "Brand New Free", "is_free": 1, "context_length": 16384},
        ]
        # Monkeypatch get_db temporarily for test isolation
        import engine.model_scanner as ms
        orig_get_db = ms.get_db
        ms.get_db = lambda: self.db
        try:
            diff2 = ModelScanner.trace_provider_models("mock_provider", updated_models, sync_to_db=True)
            self.assertEqual(len(diff2["added_free"]), 1)
            self.assertEqual(diff2["added_free"][0]["model_name"], "provider/brand-new-free")

            self.assertEqual(len(diff2["removed"]), 1)
            self.assertEqual(diff2["removed"][0]["model_name"], "provider/paid-sota")

            self.assertEqual(len(diff2["changed"]), 1)
            self.assertEqual(diff2["changed"][0]["model_name"], "provider/free-coder")
            self.assertIn("pricing shifted", diff2["changed"][0]["change_summary"])
        finally:
            ms.get_db = orig_get_db

    def test_union_alpha_registry_and_router(self):
        """Verifies Pareto 26.9 (Union Alpha) is present in registry, scored, and ranked."""
        registry = ModelRegistry()
        pareto = registry.get_model("unbiased/pareto")
        self.assertIsNotNone(pareto)
        self.assertIn("Union Alpha", pareto.display_name)
        self.assertEqual(pareto.context_length, 262144)
        self.assertEqual(pareto.base_quality, 9.9)

        router = AutoCodingRouter(registry=registry)
        ranked = router.rank_coding_models(prompt="Build a full-stack web application with complex architecture")
        ranked_ids = [m.spec.model_id for m in ranked]
        self.assertIn("unbiased/pareto", ranked_ids)
        # Verify it achieves top-tier rank
        top_model = ranked[0]
        self.assertIn(top_model.spec.model_id, ("unbiased/pareto", "deepseek/deepseek-r1", "deepseek-ai/deepseek-r1", "qwen/qwen-2.5-coder-32b-instruct", "deepseek-r1-distill-llama-70b"))

    def test_union_alpha_credentials_and_choices(self):
        """Verifies Union Alpha / Pareto model choices and credential routing."""
        self.assertIn("Pareto 26.9 (Union Alpha)", MODEL_CHOICES)

        # Set fake OpenRouter key in db
        self.db.set_setting("openrouter_api_key", "sk-or-v1-fakekey1234567890")
        import database.db_manager as dbm
        orig_dbm_get_db = dbm.get_db
        dbm.get_db = lambda: self.db
        try:
            # Test routing for "Union Alpha"
            prov, key, m_name = _get_cloud_credentials("Union Alpha")
            self.assertEqual(prov, "openrouter")
            self.assertEqual(m_name, "unbiased/pareto")

            # Test routing for "Pareto 26.9"
            prov2, key2, m_name2 = _get_cloud_credentials("Pareto 26.9")
            self.assertEqual(prov2, "openrouter")
            self.assertEqual(m_name2, "unbiased/pareto")

            # Test routing for alias "openrouter/pareto-code"
            prov3, key3, m_name3 = _get_cloud_credentials("openrouter/pareto-code")
            self.assertEqual(prov3, "openrouter")
            self.assertEqual(m_name3, "unbiased/pareto")
        finally:
            dbm.get_db = orig_dbm_get_db


if __name__ == "__main__":
    unittest.main()
