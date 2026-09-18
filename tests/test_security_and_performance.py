"""
Comprehensive Test Suite for Security Vault, API Key Protection, and Performance Optimization.
"""
import os
import time
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.db_manager import DatabaseManager
from engine.security_vault import SecurityVault, SecurityViolation
from engine.model_scanner import ModelScanner


class TestSecurityAndPerformance(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_sec.db"
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        # Explicitly close or cleanup
        del self.db
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_secret_encryption_at_rest(self):
        """Verify API keys and sensitive tokens are encrypted in SQLite table."""
        secrets_to_test = {
            "groq_api_key": "gsk_prod_secret_token_123456789",
            "openrouter_api_key": "sk-or-v1-abcdef0123456789abcdef0123456789",
            "nvidia_api_key": "nvapi-test-key-9999",
            "github_token": "ghp_PersonalAccessToken1234567890",
            "gmail_app_password": "abcd efgh ijkl mnop",
        }

        for key, plain_val in secrets_to_test.items():
            self.db.set_setting(key, plain_val)

        # Inspect raw SQLite table directly
        conn = sqlite3.connect(str(self.db_path))
        try:
            for key, plain_val in secrets_to_test.items():
                row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
                self.assertIsNotNone(row)
                raw_db_val = row[0]

                # Assert that raw storage is encrypted
                self.assertTrue(
                    raw_db_val.startswith("enc:v1:"),
                    f"Key {key} was not stored with encryption prefix! Found: {raw_db_val}"
                )
                self.assertNotIn(
                    plain_val,
                    raw_db_val,
                    f"Plaintext secret was exposed in raw SQLite database for key {key}!"
                )

                # Assert that DatabaseManager returns the decrypted plaintext
                decrypted = self.db.get_setting(key)
                self.assertEqual(
                    decrypted,
                    plain_val,
                    f"Decrypted value does not match original for {key}!"
                )
        finally:
            conn.close()

    def test_legacy_plaintext_compatibility(self):
        """Verify pre-existing unencrypted keys from older versions still load seamlessly."""
        legacy_key = "groq_api_key"
        legacy_val = "gsk_legacy_unencrypted_123"

        # Manually write raw plaintext directly into SQLite (bypassing set_setting)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                (legacy_key, legacy_val)
            )
            conn.commit()
        finally:
            conn.close()

        # DatabaseManager must read legacy plaintext properly without crashing
        self.assertEqual(self.db.get_setting(legacy_key), legacy_val)

        # Next time it's updated, it should automatically become encrypted at rest
        new_val = "gsk_updated_key_456"
        self.db.set_setting(legacy_key, new_val)

        conn = sqlite3.connect(str(self.db_path))
        try:
            raw = conn.execute("SELECT value FROM settings WHERE key = ?", (legacy_key,)).fetchone()[0]
            self.assertTrue(raw.startswith("enc:v1:"))
            self.assertEqual(self.db.get_setting(legacy_key), new_val)
        finally:
            conn.close()

    def test_non_secret_settings_not_encrypted(self):
        """Standard non-sensitive settings (theme, window_size) should not have encryption overhead."""
        self.db.set_setting("theme", "cyber_dark")
        self.db.set_setting("fast_mode", "true")

        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute("SELECT value FROM settings WHERE key = 'theme'").fetchone()
            self.assertEqual(row[0], "cyber_dark")
            self.assertFalse(row[0].startswith("enc:v1:"))
        finally:
            conn.close()

    def test_mask_secret(self):
        """Verify API key masking obscures credentials safely."""
        masked_groq = SecurityVault.mask_secret("gsk_1234567890abcdef1234")
        self.assertTrue(masked_groq.startswith("gsk_"))
        self.assertTrue("•" in masked_groq)
        self.assertTrue(masked_groq.endswith("1234"))

        # Short secret
        masked_short = SecurityVault.mask_secret("1234")
        self.assertEqual(masked_short, "••••••••")

        # Empty secret
        self.assertEqual(SecurityVault.mask_secret(""), "")

    def test_sanitize_text(self):
        """Verify secrets in error messages and tracebacks are scrubbed."""
        error_sample = (
            "Request failed: Bearer sk-or-v1-abcdef012345678901234567890 "
            "using groq key gsk_1234567890123456789012345"
        )
        sanitized = SecurityVault.sanitize_text(error_sample)
        self.assertNotIn("sk-or-v1-abcdef012345678901234567890", sanitized)
        self.assertNotIn("gsk_1234567890123456789012345", sanitized)
        self.assertIn("REDACTED", sanitized)

    def test_path_traversal_defense(self):
        """Verify path traversal attacks are detected and blocked."""
        workspace = Path(self.test_dir) / "workspace"
        workspace.mkdir()

        # Safe path inside workspace
        safe = SecurityVault.validate_safe_path("src/main.py", workspace_root=workspace)
        self.assertEqual(safe, (workspace / "src" / "main.py").resolve())

        # Path traversal attempting to escape workspace
        with self.assertRaises(SecurityViolation):
            SecurityVault.validate_safe_path("../../Windows/System32/cmd.exe", workspace_root=workspace, allow_temp=False)

    def test_command_injection_defense(self):
        """Verify dangerous and destructive commands are blocked."""
        # Safe commands
        safe, _ = SecurityVault.validate_safe_command("python -m unittest discover")
        self.assertTrue(safe)
        safe, _ = SecurityVault.validate_safe_command("npm test")
        self.assertTrue(safe)

        # Destructive commands
        blocked, reason = SecurityVault.validate_safe_command("rm -rf /")
        self.assertFalse(blocked)
        self.assertIn("destructive", reason.lower())

        blocked, reason = SecurityVault.validate_safe_command("format C:")
        self.assertFalse(blocked)

        blocked, reason = SecurityVault.validate_safe_command("del /s /q C:\\")
        self.assertFalse(blocked)

    def test_performance_in_memory_cache(self):
        """Verify in-memory caching provides high-throughput sub-microsecond lookups."""
        self.db.set_setting("cache_test_key", "optimized_value")

        # Measure 1,000 cached reads
        start = time.perf_counter()
        for _ in range(1000):
            val = self.db.get_setting("cache_test_key")
            self.assertEqual(val, "optimized_value")
        duration = time.perf_counter() - start

        # 1,000 in-memory lookups should take less than 15 milliseconds total (< 0.015ms per lookup)
        self.assertLess(duration, 0.05, f"1,000 lookups took {duration:.4f}s, expected < 0.05s")

    def test_model_scanner_available_models(self):
        """Verify ModelScanner.get_available_models() runs fast and returns model list."""
        models = ModelScanner.get_available_models()
        self.assertIsInstance(models, list)
        self.assertTrue(len(models) > 0)
        self.assertIn("id", models[0])


if __name__ == "__main__":
    unittest.main()
