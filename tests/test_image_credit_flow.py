"""
Unit tests for Image Generation and Credit Flow in Sage AI.
Workflow:
User asks for image -> Check remaining free credits ->
[Available]: Black Forest FLUX.1 -> Generate image -> Deduct credit
[Not Available]: Stop + tell user credits exhausted
"""
import unittest
from engine.request_analyzer import RequestAnalyzer
from engine.providers.image_provider import ImageProvider
from database.db_manager import get_db
from config import INTENT_IMAGE


class TestImageCreditFlow(unittest.TestCase):

    def setUp(self):
        self.provider = ImageProvider()
        self.db = get_db()
        # Reset credits to 25 for predictable tests
        self.provider.refill_credits(25)

    def test_request_analyzer_colloquial_image_queries(self):
        """Verify colloquial prompts and typos route to INTENT_IMAGE."""
        queries = [
            "make piture of universe",
            "make picture of universe",
            "make an image of a red sports car",
            "show me a picture of galaxies and stars",
            "draw a majestic dragon on a mountain",
            "paint an impressionist sunset over the ocean",
            "generate a wallpaper of cyberpunk city",
            "picture of deep space",
        ]
        for q in queries:
            res = RequestAnalyzer.analyze(q)
            self.assertEqual(res["intent"], INTENT_IMAGE, f"Failed for query: {q}")

    def test_prompt_cleaning(self):
        """Verify conversational commands are cleaned for diffusion model."""
        cases = [
            ("make piture of universe", "universe"),
            ("Generate a picture of a cute cat", "a cute cat"),
            ("draw a futuristic spaceship!", "futuristic spaceship"),
            ("show me a picture of Mars rover.", "Mars rover"),
            ("paint an ocean sunset", "ocean sunset"),
        ]
        for raw, expected in cases:
            cleaned = self.provider._clean_prompt(raw)
            self.assertEqual(cleaned.lower(), expected.lower())

    def test_credits_exhaustion_stops_generation(self):
        """When credits == 0, generation must STOP and inform user without calling API."""
        # Set credits to 0
        self.db.save_provider_quota("image", {
            "total_limit": 25.0,
            "used_amount": 25.0,
            "remaining_amount": 0.0,
            "currency_or_unit": "Credits",
            "is_free_tier": True
        })
        self.db.set_setting("image_remaining_credits", "0")

        self.assertEqual(self.provider.get_remaining_credits(), 0)
        self.assertFalse(self.provider.is_available())

        # Attempt generation with 0 credits
        resp = self.provider.generate("universe with stars")

        # Must stop and inform user
        self.assertFalse(resp.success)
        self.assertFalse(resp.is_image)
        self.assertIn("Credits Exhausted", resp.text)
        self.assertIn("0", resp.text)

    def test_credits_refill(self):
        """Refilling credits restores balance to 25."""
        self.provider.refill_credits(25)
        self.assertEqual(self.provider.get_remaining_credits(), 25)
        self.assertTrue(self.provider.is_available())

    def test_credits_consumption(self):
        """Consuming a credit decrements balance by 1."""
        self.provider.refill_credits(25)
        new_bal = self.provider.consume_credit()
        self.assertEqual(new_bal, 24)
        self.assertEqual(self.provider.get_remaining_credits(), 24)


if __name__ == "__main__":
    unittest.main()
