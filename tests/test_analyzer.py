"""
Unit tests for RequestAnalyzer in Sage AI.
"""
import unittest
from engine.request_analyzer import RequestAnalyzer
from config import (
    INTENT_CODING,
    INTENT_WEB_SEARCH,
    INTENT_GITHUB,
    INTENT_IMAGE,
    INTENT_LOCAL_FACTS,
    INTENT_GENERAL_CHAT,
)


class TestRequestAnalyzer(unittest.TestCase):

    def test_coding_queries(self):
        queries = [
            "Write a python function to compute fibonacci numbers",
            "How do I fix this TypeError in my PySide6 application?",
            "```python\ndef test(): pass\n```",
            "Refactor this algorithm for better time complexity",
            "Create a dockerfile for a Flask microservice"
        ]
        for q in queries:
            res = RequestAnalyzer.analyze(q)
            self.assertEqual(res["intent"], INTENT_CODING, f"Failed for query: {q}")

    def test_local_facts_queries(self):
        queries = [
            "What time is it?",
            "today's date",
            "calculate 25 * 40 + 10",
            "convert 100 usd to eur",
            "who are you",
            "what is sage ai",
            "Show me the Sage AI local knowledge base and cheatsheets.",
            "Python cheatsheet",
            "Git commands",
            "Yoooo"
        ]
        for q in queries:
            res = RequestAnalyzer.analyze(q)
            self.assertEqual(res["intent"], INTENT_LOCAL_FACTS, f"Failed for query: {q}")

    def test_image_queries(self):
        queries = [
            "Generate an image of a cyberpunk city with emerald neon lights",
            "Create a picture of an astronaut riding a horse on Mars",
            "draw a futuristic spaceship in orbit",
            "txt2img render of fantasy landscape"
        ]
        for q in queries:
            res = RequestAnalyzer.analyze(q)
            self.assertEqual(res["intent"], INTENT_IMAGE, f"Failed for query: {q}")

    def test_github_queries(self):
        queries = [
            "https://github.com/torvalds/linux",
            "Check this github repo for recent commits",
            "How many github stars does this repository have?"
        ]
        for q in queries:
            res = RequestAnalyzer.analyze(q)
            self.assertEqual(res["intent"], INTENT_GITHUB, f"Failed for query: {q}")

    def test_web_search_queries(self):
        queries = [
            "What is the latest news today?",
            "Search the web for recent advances in fusion energy",
            "What is the current stock price of Apple in 2026?",
            "who is the prime minister of india",
            "current weather in Tokyo"
        ]
        for q in queries:
            res = RequestAnalyzer.analyze(q)
            self.assertEqual(res["intent"], INTENT_WEB_SEARCH, f"Failed for query: {q}")

    def test_forced_web_toggle(self):
        res = RequestAnalyzer.analyze("Explain quantum computing", force_web=True)
        self.assertEqual(res["intent"], INTENT_WEB_SEARCH)
        self.assertTrue(res["force_web"])

    def test_general_chat(self):
        res = RequestAnalyzer.analyze("Tell me an inspiring story about perseverance.")
        self.assertEqual(res["intent"], INTENT_GENERAL_CHAT)


if __name__ == "__main__":
    unittest.main()
