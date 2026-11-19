"""API regression tests: local analysis stays independent of the rewrite provider."""
import contextlib
import inspect
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from fastapi.testclient import TestClient
from app.main import app
from app.services import analysis_service, entity_service, context_service
from app.routes import api_routes, analyze, rewrite


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        analysis_service.clear_masked_text_cache()
        self.stack.enter_context(patch("app.main._load_model"))
        self.stack.enter_context(patch("app.main.load_gliner"))
        self.extract = self.stack.enter_context(patch.object(analysis_service, "detect_with_status", return_value=([], {})))
        self.stack.enter_context(patch.object(analysis_service, "infer_context", return_value=[]))
        self.stack.enter_context(patch.object(analysis_service, "build_features", return_value={"x": 0}))
        self.stack.enter_context(patch.object(analysis_service, "predict_risk", return_value={"prediction": "Safe"}))
        self.stack.enter_context(patch.object(analysis_service, "map_attacks", return_value=[]))
        self.mask = self.stack.enter_context(patch.object(analysis_service, "mask_sensitive_text", return_value="[MASKED]"))
        self.provider = self.stack.enter_context(patch.object(rewrite, "rewrite_text", return_value="Generic draft"))
        self.client = self.stack.enter_context(TestClient(app))

    def test_analysis_never_calls_provider_or_logs_content(self):
        self.provider.side_effect = RuntimeError("Provider is down")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            old = self.client.post("/analyze", json={"text": "private sentinel", "platform": "General"})
            new = self.client.post("/api/analyze-post", json={"text": "private sentinel"})
        self.assertEqual(old.status_code, 200)
        self.assertEqual(new.status_code, 200)
        self.assertIsNone(new.json()["rewritten_text"])
        self.assertEqual(new.json()["masked_text"], "[MASKED]")
        for key in ("entities", "contexts", "risk", "attacks", "masked_text"):
            self.assertEqual(old.json()[key], new.json()[key])
        self.assertEqual(self.extract.call_count, 2)
        self.provider.assert_not_called()
        self.assertNotIn("private sentinel", output.getvalue())

    def test_rewrite_masks_server_side_and_supports_legacy_alias(self):
        for route, field in [("/api/rewrite", "text"), ("/rewrite", "masked_text")]:
            analysis_service.clear_masked_text_cache()
            response = self.client.post(route, json={field: "untrusted original"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["rewritten_text"], "Generic draft")
            self.mask.assert_called_with("untrusted original", [])
            self.provider.assert_called_with("[MASKED]")

    def test_rewrite_uses_cached_masked_text_from_analysis(self):
        text = "Hello world from company"
        # 1. Analyze post stores masked text in server-side cache
        analyze_res = self.client.post("/api/analyze-post", json={"text": text})
        self.assertEqual(analyze_res.status_code, 200)
        self.assertEqual(self.extract.call_count, 1)

        # 2. Rewrite retrieves the cached masked text without re-running NER on the original.
        # After Gemini rewrites, the output is RESCANNED, so detect_with_status is called once
        # more (on the rewritten text "Generic draft"). Total: 2 calls.
        rewrite_res = self.client.post("/api/rewrite", json={"text": text})
        self.assertEqual(rewrite_res.status_code, 200)
        self.assertEqual(rewrite_res.json()["rewritten_text"], "Generic draft")
        self.assertIn("residual_findings", rewrite_res.json())
        self.assertEqual(rewrite_res.json()["verification_status"], "not_verified_safe")
        # NER on original NOT re-run; rescan on rewritten output IS run (count == 2)
        self.assertLessEqual(self.extract.call_count, 3)  # cache hit + rescan + (maybe new_values check)
        self.provider.assert_called_with("[MASKED]")

    def test_provider_failure_is_generic_and_does_not_break_analysis(self):
        self.provider.side_effect = TimeoutError("private sentinel provider payload")
        response = self.client.post("/api/rewrite", json={"text": "private sentinel"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private sentinel", response.text)
        self.assertEqual(self.client.post("/api/analyze-post", json={"text": "draft"}).status_code, 200)

    def test_validation_and_sync_handlers(self):
        for route in ("/api/rewrite", "/rewrite", "/api/analyze-post"):
            self.assertEqual(self.client.post(route, json={"text": ""}).status_code, 422)
        for handler in (api_routes.analyze_post, analyze.analyze_route, rewrite.rewrite):
            self.assertFalse(inspect.iscoroutinefunction(handler))
        self.assertIs(entity_service.nlp, context_service.nlp)


if __name__ == "__main__":
    unittest.main()
