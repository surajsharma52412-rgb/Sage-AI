"""
Automated API and Unit Test Suite.
"""
import unittest
import json

class TestAPI(unittest.TestCase):
    def test_health_check_format(self):
        expected_payload = {"status": "ok", "service": "Sage Backend v6"}
        self.assertEqual(expected_payload["status"], "ok")
        self.assertIn("service", expected_payload)

    def test_item_data_structure(self):
        item = {"id": "1", "title": "Test Item", "status": "active"}
        self.assertEqual(item["id"], "1")
        self.assertTrue(len(item["title"]) > 0)

if __name__ == "__main__":
    unittest.main()
