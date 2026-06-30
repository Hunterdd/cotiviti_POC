"""
tests/test_src.py — unit tests for all src modules.

No API key or network calls needed — LLM is fully mocked via src.llm.

Usage:
    source .venv/bin/activate
    python -m pytest tests/test_src.py -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── shared test fixtures ──────────────────────────────────────────────────────

SAMPLE_RULES_OLD = [
    {
        "rule_id": "R001",
        "description": "Physician order required before initiating RPM.",
        "applicable_codes": ["99453", "99454"],
        "conditions": ["physician order on file"],
        "source_citation": "Section 1.1",
    }
]

SAMPLE_RULES_NEW = [
    *SAMPLE_RULES_OLD,
    {
        "rule_id": "R002",
        "description": "Minimum 16 days of data collection per 30-day period.",
        "applicable_codes": ["99454"],
        "conditions": ["16+ days of transmitted data"],
        "source_citation": "Section 2.3",
    },
]

SAMPLE_CLAIM = {
    "claim_id": "CLM-001",
    "patient_id": "PT-1001",
    "date_of_service": "2025-03-15",
    "diagnosis_codes": ["I10"],
    "procedure_codes": ["99457"],
    "device": "FDA-cleared blood pressure monitor",
    "monitoring_duration_days": 30,
    "physician_order": True,
    "care_plan_documented": True,
    "interactive_communication_minutes": 22,
    "notes": "Hypertension RPM program.",
}


def _write_temp_json(data) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return Path(f.name)


def _mock_llm_post(content: str):
    """Fake requests.post response matching OpenRouter's shape."""
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"choices": [{"message": {"content": content}}]}
    return mock


# ── mock target: src.llm is where call_llm and API_KEY live now ───────────────
LLM_POST    = "src.llm.requests.post"
LLM_API_KEY = "src.llm.API_KEY"


# =============================================================================
# Tests — src.llm (shared utilities)
# =============================================================================

class TestLLM(unittest.TestCase):

    def setUp(self):
        from src.llm import load_json, parse_json
        self.parse     = parse_json
        self.load_json = load_json

    # parse_json — array mode
    def test_parse_array_plain(self):
        result = self.parse(json.dumps(SAMPLE_RULES_OLD), kind="array")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["rule_id"], "R001")

    def test_parse_array_with_markdown_fences(self):
        raw = f"```json\n{json.dumps(SAMPLE_RULES_OLD)}\n```"
        result = self.parse(raw, kind="array")
        self.assertEqual(result[0]["rule_id"], "R001")

    def test_parse_array_with_bare_fences(self):
        raw = f"```\n{json.dumps(SAMPLE_RULES_OLD)}\n```"
        result = self.parse(raw, kind="array")
        self.assertIsInstance(result, list)

    def test_parse_array_extracts_embedded(self):
        """Fallback: JSON buried inside prose."""
        raw = f"Here are the rules:\n{json.dumps(SAMPLE_RULES_OLD)}\nEnd."
        result = self.parse(raw, kind="array")
        self.assertEqual(result[0]["rule_id"], "R001")

    def test_parse_object_plain(self):
        obj = {"decision": "approve", "violations": []}
        result = self.parse(json.dumps(obj))
        self.assertEqual(result["decision"], "approve")

    def test_parse_object_with_fences(self):
        obj = {"summary": "No change."}
        raw = f"```json\n{json.dumps(obj)}\n```"
        result = self.parse(raw)
        self.assertEqual(result["summary"], "No change.")

    def test_parse_invalid_raises(self):
        with self.assertRaises((json.JSONDecodeError, ValueError)):
            self.parse("this is not json at all", kind="array")

    # load_json
    def test_load_json_round_trip(self):
        path = _write_temp_json(SAMPLE_RULES_OLD)
        self.assertEqual(self.load_json(path), SAMPLE_RULES_OLD)

    def test_load_json_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.load_json(Path("/nonexistent/file.json"))

    # call_llm
    @patch(LLM_API_KEY, "dummy-key")
    @patch(LLM_POST)
    def test_call_llm_returns_content(self, mock_post):
        mock_post.return_value = _mock_llm_post("hello")
        from src.llm import call_llm
        self.assertEqual(call_llm("test prompt"), "hello")

    def test_call_llm_no_key_raises(self):
        with patch(LLM_API_KEY, None):
            from src.llm import call_llm
            with self.assertRaises(EnvironmentError):
                call_llm("test")


# =============================================================================
# Tests — src/extractor.py
# =============================================================================

class TestExtractor(unittest.TestCase):

    def setUp(self):
        from src.extractor import build_extraction_prompt, extract_text_from_pdf
        self.build_prompt = build_extraction_prompt
        self.extract_text = extract_text_from_pdf

    def test_prompt_contains_required_fields(self):
        prompt = self.build_prompt("Some policy text.")
        for field in ["rule_id", "applicable_codes", "conditions", "source_citation"]:
            self.assertIn(field, prompt)

    def test_prompt_includes_policy_text(self):
        marker = "UNIQUE_MARKER_XYZ"
        self.assertIn(marker, self.build_prompt(marker))

    @patch(LLM_API_KEY, "dummy-key")
    @patch(LLM_POST)
    def test_extract_rules_writes_json(self, mock_post):
        mock_post.return_value = _mock_llm_post(json.dumps(SAMPLE_RULES_OLD))
        from src.extractor import extract_rules

        with patch("src.extractor.extract_text_from_pdf", return_value="Sample text."):
            with tempfile.TemporaryDirectory() as tmpdir:
                fake_pdf = Path(tmpdir) / "rpm_policy_2025.pdf"
                fake_pdf.write_bytes(b"%PDF-1.4 fake")

                with patch("src.extractor.RULES_DIR", Path(tmpdir)):
                    out = extract_rules(fake_pdf, "2025")

                self.assertTrue(out.exists())
                self.assertEqual(json.loads(out.read_text())[0]["rule_id"], "R001")

    @patch(LLM_API_KEY, "dummy-key")
    @patch(LLM_POST)
    def test_extract_rules_caching(self, mock_post):
        mock_post.return_value = _mock_llm_post(json.dumps(SAMPLE_RULES_OLD))
        from src.extractor import extract_rules
        
        with patch("src.extractor.extract_text_from_pdf", return_value="Sample text."):
            with tempfile.TemporaryDirectory() as tmpdir:
                fake_pdf = Path(tmpdir) / "rpm_policy_2025.pdf"
                fake_pdf.write_bytes(b"%PDF-1.4 fake")
                
                temp_rules_dir = Path(tmpdir) / "rules"
                temp_cache_dir = Path(tmpdir) / "cache"
                
                with patch("src.extractor.RULES_DIR", temp_rules_dir):
                    with patch("src.extractor.CACHE_DIR", temp_cache_dir):
                        # 1. First run: Cache Miss. Should call LLM and write to cache.
                        out1 = extract_rules(fake_pdf, "2025", use_cache=True)
                        self.assertTrue(out1.exists())
                        self.assertEqual(mock_post.call_count, 1)
                        
                        # Verify cache file created
                        self.assertEqual(len(list(temp_cache_dir.glob("*.json"))), 1)
                        
                        # 2. Second run: Cache Hit. Should NOT call LLM.
                        mock_post.reset_mock()
                        _ = extract_rules(fake_pdf, "2025", use_cache=True)
                        self.assertEqual(mock_post.call_count, 0)
                        
                        # 3. Third run (use_cache=False): Should bypass cache and call LLM.
                        mock_post.reset_mock()
                        _ = extract_rules(fake_pdf, "2025", use_cache=False)
                        self.assertEqual(mock_post.call_count, 1)



# =============================================================================
# Tests — src/differ.py
# =============================================================================

class TestDiffer(unittest.TestCase):

    def setUp(self):
        from src.differ import build_diff_prompt
        self.build_prompt = build_diff_prompt

    def test_prompt_contains_both_years(self):
        prompt = self.build_prompt(SAMPLE_RULES_OLD, SAMPLE_RULES_NEW, "2023", "2025")
        self.assertIn("2023", prompt)
        self.assertIn("2025", prompt)

    def test_prompt_contains_all_categories(self):
        prompt = self.build_prompt(SAMPLE_RULES_OLD, SAMPLE_RULES_NEW, "2023", "2025")
        for cat in ["added", "removed", "tightened", "loosened", "unchanged", "summary"]:
            self.assertIn(cat, prompt)

    @patch(LLM_API_KEY, "dummy-key")
    @patch(LLM_POST)
    def test_diff_rules_writes_file(self, mock_post):
        diff_response = {
            "added": [{"rule_id": "R002", "description": "New rule", "impact": "test"}],
            "removed": [], "tightened": [], "loosened": [],
            "unchanged": ["R001"], "summary": "One rule added.",
        }
        mock_post.return_value = _mock_llm_post(json.dumps(diff_response))
        from src.differ import diff_rules

        with tempfile.TemporaryDirectory() as tmpdir:
            old_path = Path(tmpdir) / "rules_2023.json"
            new_path = Path(tmpdir) / "rules_2025.json"
            old_path.write_text(json.dumps(SAMPLE_RULES_OLD))
            new_path.write_text(json.dumps(SAMPLE_RULES_NEW))

            with patch("src.differ.DIFFS_DIR", Path(tmpdir)):
                out = diff_rules(old_path, new_path)

            self.assertTrue(out.exists())
            self.assertEqual(json.loads(out.read_text())["summary"], "One rule added.")

    @patch(LLM_API_KEY, "dummy-key")
    @patch(LLM_POST)
    def test_diff_rules_caching(self, mock_post):
        diff_response = {
            "added": [{"rule_id": "R002", "description": "New rule", "impact": "test"}],
            "removed": [], "tightened": [], "loosened": [],
            "unchanged": ["R001"], "summary": "One rule added.",
        }
        mock_post.return_value = _mock_llm_post(json.dumps(diff_response))
        from src.differ import diff_rules
        
        with tempfile.TemporaryDirectory() as tmpdir:
            old_path = Path(tmpdir) / "rules_2023.json"
            new_path = Path(tmpdir) / "rules_2025.json"
            old_path.write_text(json.dumps(SAMPLE_RULES_OLD))
            new_path.write_text(json.dumps(SAMPLE_RULES_NEW))
            
            temp_diffs_dir = Path(tmpdir) / "diffs"
            temp_cache_dir = Path(tmpdir) / "cache"
            
            with patch("src.differ.DIFFS_DIR", temp_diffs_dir):
                with patch("src.differ.CACHE_DIR", temp_cache_dir):
                    # 1. First run: Cache Miss. Should call LLM and write to cache.
                    out1 = diff_rules(old_path, new_path, use_cache=True)
                    self.assertTrue(out1.exists())
                    self.assertEqual(mock_post.call_count, 1)
                    
                    # Verify cache file created
                    self.assertEqual(len(list(temp_cache_dir.glob("*.json"))), 1)
                    
                    # 2. Second run: Cache Hit. Should NOT call LLM.
                    mock_post.reset_mock()
                    _ = diff_rules(old_path, new_path, use_cache=True)
                    self.assertEqual(mock_post.call_count, 0)
                    
                    # 3. Third run (use_cache=False): Should bypass cache and call LLM.
                    mock_post.reset_mock()
                    _ = diff_rules(old_path, new_path, use_cache=False)
                    self.assertEqual(mock_post.call_count, 1)



# =============================================================================
# Tests — src/auditor.py
# =============================================================================

class TestAuditor(unittest.TestCase):

    def setUp(self):
        from src.auditor import build_audit_prompt
        self.build_prompt = build_audit_prompt

    def test_prompt_contains_claim_data(self):
        prompt = self.build_prompt(SAMPLE_CLAIM, SAMPLE_RULES_NEW)
        for value in ["CLM-001", "99457", "I10"]:
            self.assertIn(value, prompt)

    def test_prompt_contains_output_fields(self):
        prompt = self.build_prompt(SAMPLE_CLAIM, SAMPLE_RULES_NEW)
        for field in ["decision", "violations", "met_rules", "citations", "rationale"]:
            self.assertIn(field, prompt)

    def test_prompt_contains_rule_ids(self):
        prompt = self.build_prompt(SAMPLE_CLAIM, SAMPLE_RULES_NEW)
        self.assertIn("R001", prompt)
        self.assertIn("R002", prompt)

    @patch(LLM_API_KEY, "dummy-key")
    @patch(LLM_POST)
    def test_audit_approve(self, mock_post):
        mock_post.return_value = _mock_llm_post(json.dumps({
            "decision": "approve", "violations": [],
            "met_rules": ["R001"], "citations": ["Section 1.1"], "rationale": "All rules met.",
        }))
        from src.auditor import audit_claim

        with tempfile.TemporaryDirectory() as tmpdir:
            rules_path = Path(tmpdir) / "rules_2025.json"
            rules_path.write_text(json.dumps(SAMPLE_RULES_NEW))
            result = audit_claim(SAMPLE_CLAIM, rules_path)

        self.assertEqual(result["decision"], "approve")
        self.assertEqual(result["claim_id"], "CLM-001")
        self.assertIn("rules_version", result)

    @patch(LLM_API_KEY, "dummy-key")
    @patch(LLM_POST)
    def test_audit_deny_has_violations(self, mock_post):
        mock_post.return_value = _mock_llm_post(json.dumps({
            "decision": "deny",
            "violations": [{"rule_id": "R001", "rule_description": "Physician order required", "reason": "Not documented"}],
            "met_rules": [], "citations": ["Section 1.1"], "rationale": "Missing order.",
        }))
        from src.auditor import audit_claim

        with tempfile.TemporaryDirectory() as tmpdir:
            rules_path = Path(tmpdir) / "rules_2025.json"
            rules_path.write_text(json.dumps(SAMPLE_RULES_NEW))
            result = audit_claim({**SAMPLE_CLAIM, "physician_order": False}, rules_path)

        self.assertEqual(result["decision"], "deny")
        self.assertGreater(len(result["violations"]), 0)

    def test_missing_api_key_raises(self):
        with patch(LLM_API_KEY, None):
            from src.llm import call_llm
            with self.assertRaises(EnvironmentError):
                call_llm("test")

    def test_all_decision_values_parse(self):
        from src.llm import parse_json
        for d in ["approve", "deny", "needs_review"]:
            result = parse_json(json.dumps({"decision": d, "violations": [], "met_rules": [], "citations": [], "rationale": ""}))
            self.assertEqual(result["decision"], d)

    @patch(LLM_API_KEY, "dummy-key")
    @patch(LLM_POST)
    def test_audit_caching_behavior(self, mock_post):
        mock_post.return_value = _mock_llm_post(json.dumps({
            "decision": "approve", "violations": [],
            "met_rules": ["R001"], "citations": ["Section 1.1"], "rationale": "Rules met.",
        }))
        from src.auditor import audit_claim
        
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_path = Path(tmpdir) / "rules_2025.json"
            rules_path.write_text(json.dumps(SAMPLE_RULES_NEW))
            
            # Setup a temporary cache directory for this test
            temp_cache = Path(tmpdir) / "cache"
            with patch("src.auditor.CACHE_DIR", temp_cache):
                
                # 1. First run: Cache Miss. Should call LLM and write to cache.
                res1 = audit_claim(SAMPLE_CLAIM, rules_path, use_cache=True)
                self.assertEqual(res1["decision"], "approve")
                self.assertEqual(mock_post.call_count, 1)
                
                # Verify cache file was created
                cache_files = list(temp_cache.glob("*.json"))
                self.assertEqual(len(cache_files), 1)
                
                # 2. Second run: Cache Hit. Should NOT call LLM, return cached result.
                mock_post.reset_mock()
                res2 = audit_claim(SAMPLE_CLAIM, rules_path, use_cache=True)
                self.assertEqual(res2["decision"], "approve")
                self.assertEqual(mock_post.call_count, 0)
                
                # 3. Third run with use_cache=False: Should bypass cache and call LLM.
                mock_post.reset_mock()
                res3 = audit_claim(SAMPLE_CLAIM, rules_path, use_cache=False)
                self.assertEqual(res3["decision"], "approve")
                self.assertEqual(mock_post.call_count, 1)
                
                # 4. Modify claim: Should result in cache miss and call LLM.
                mock_post.reset_mock()
                modified_claim = {**SAMPLE_CLAIM, "physician_order": False}
                _ = audit_claim(modified_claim, rules_path, use_cache=True)
                self.assertEqual(mock_post.call_count, 1)
                
                # Verify another cache file was created
                self.assertEqual(len(list(temp_cache.glob("*.json"))), 2)

    @patch(LLM_API_KEY, "dummy-key")
    @patch(LLM_POST)
    def test_audit_claims_batch(self, mock_post):
        mock_post.return_value = _mock_llm_post(json.dumps([
            {"decision": "approve", "violations": [], "met_rules": ["R001"], "citations": ["Section 1.1"], "rationale": "Approve rationale"},
            {"decision": "deny", "violations": [], "met_rules": [], "citations": [], "rationale": "Deny rationale"}
        ]))
        from src.auditor import audit_claims_batch
        
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_path = Path(tmpdir) / "rules_2025.json"
            rules_path.write_text(json.dumps(SAMPLE_RULES_NEW))
            
            temp_cache = Path(tmpdir) / "cache"
            with patch("src.auditor.CACHE_DIR", temp_cache):
                claims = [
                    {**SAMPLE_CLAIM, "claim_id": "CLM-BATCH1"},
                    {**SAMPLE_CLAIM, "claim_id": "CLM-BATCH2"}
                ]
                
                # First run: Cache miss. Makes exactly 1 call for the batch
                results = audit_claims_batch(claims, rules_path, use_cache=True)
                self.assertEqual(len(results), 2)
                self.assertEqual(results[0]["decision"], "approve")
                self.assertEqual(results[1]["decision"], "deny")
                self.assertEqual(mock_post.call_count, 1)
                
                # Check individual cache files created
                self.assertEqual(len(list(temp_cache.glob("*.json"))), 2)
                
                # Second run: Cache hit. Bypasses LLM call entirely
                mock_post.reset_mock()
                results2 = audit_claims_batch(claims, rules_path, use_cache=True)
                self.assertEqual(mock_post.call_count, 0)
                self.assertEqual(results2[0]["decision"], "approve")

    @patch(LLM_API_KEY, "dummy-key")
    @patch(LLM_POST)
    def test_audit_claims_batch_fallback(self, mock_post):
        # Batch call returns bad response (e.g. empty array, mismatching count)
        # We also mock individual audits that follow to return valid objects
        batch_bad_mock = _mock_llm_post("[]")
        individual_mock = _mock_llm_post(json.dumps({
            "decision": "approve", "violations": [], "met_rules": ["R001"], "citations": ["Section 1.1"], "rationale": "Approve rationale"
        }))
        mock_post.side_effect = [batch_bad_mock, individual_mock, individual_mock]
        
        from src.auditor import audit_claims_batch
        
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_path = Path(tmpdir) / "rules_2025.json"
            rules_path.write_text(json.dumps(SAMPLE_RULES_NEW))
            
            temp_cache = Path(tmpdir) / "cache"
            with patch("src.auditor.CACHE_DIR", temp_cache):
                claims = [
                    {**SAMPLE_CLAIM, "claim_id": "CLM-FALLBACK1"},
                    {**SAMPLE_CLAIM, "claim_id": "CLM-FALLBACK2"}
                ]
                
                results = audit_claims_batch(claims, rules_path, use_cache=True)
                self.assertEqual(len(results), 2)
                self.assertEqual(results[0]["decision"], "approve")
                self.assertEqual(results[1]["decision"], "approve")
                # 1 batch call + 2 fallback individual calls = 3 calls
                self.assertEqual(mock_post.call_count, 3)




# =============================================================================
# Runner
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
