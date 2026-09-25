"""
Request Analyzer module for Sage AI.
Classifies user queries into specific intent categories for smart routing.
"""
import re
from typing import Dict, Any, Optional

from config import (
    INTENT_CODING,
    INTENT_WEB_SEARCH,
    INTENT_GITHUB,
    INTENT_IMAGE,
    INTENT_LOCAL_FACTS,
    INTENT_GENERAL_CHAT,
)


class RequestAnalyzer:
    """Classifies user queries into routing intent categories using heuristic & regex analyzers."""

    # Regex patterns for coding queries
    CODING_PATTERNS = [
        r"\b(write|create|implement|fix|debug|refactor|optimize)\s+(?:a|an|the|this|my|our)?\s*(?:code|function|class|script|method|program|algorithm|api|test|application|app)\b",
        r"\b(python|javascript|typescript|c\+\+|rust|golang|html|css|sql|bash|powershell|pyside6|qt)\b",
        r"\b(traceback|syntaxerror|nameerror|typeerror|attributeerror|exception|stack trace)\b",
        r"\b(def\s+\w+\(|class\s+\w+:|import\s+\w+|const\s+\w+\s*=|let\s+\w+\s*=)\b",
        r"\b(regex|regular expression|unit test|pytest|dockerfile|makefile)\b",
        r"\b(algorithm|refactor|time complexity|space complexity|big o|data structure|binary search|sorting)\b",
        r"```[\s\S]*?```",  # Markdown code fences in prompt
        r"\b(json|yaml|xml|csv)\s+parser\b",
    ]

    # Regex patterns for web search queries
    WEB_PATTERNS = [
        r"\b(search\s+(the\s+)?web|look\s+up|google|bing|duckduckgo)\b",
        r"\b(what\s+is\s+the\s+latest|who\s+won|current\s+weather|breaking\s+news|stock\s+price)\b",
        r"\b(today's|yesterday's|this\s+week's|recent\s+news)\b",
        r"\b(in\s+2025|in\s+2026|today|right\s+now)\b",
        r"\b(who\s+is|who\s+was|who's)\s+(the\s+)?(current\s+)?(prime\s+minister|pm|president|governor|ceo|founder|leader|chancellor|monarch|king|queen)\b",
        r"\b(current\s+time\s+in|weather\s+in|population\s+of|capital\s+of|currency\s+of)\b",
        r"\b(latest|current|today's|recent)\s+(news|events|updates|score|results|standings|election|prices?)\b",
    ]

    # Regex patterns for GitHub queries
    GITHUB_PATTERNS = [
        r"https?://github\.com/[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+",
        r"\b(github\s+repo|github\s+repository|pull\s+request|git\s+clone|github\s+stars)\b",
    ]

    # Regex patterns for image generation
    IMAGE_PATTERNS = [
        r"\b(generate|create|make|draw|render|paint|illustrate|produce|show\s+me|give\s+me)\s+(an?\s+|the\s+)?(image|picture|piture|photo|illustration|art|artwork|painting|drawing|wallpaper|portrait|pic|pics)\b",
        r"\b(image|picture|piture|photo|wallpaper|artwork|drawing|painting)\s+(of|about|showing|depicting)\b",
        r"\b(txt2img|text to image|stable diffusion|flux|black forest|midjourney prompt)\b",
        r"^(draw|paint|sketch|illustrate)\s+.*",
        r"^(make|create|generate)\s+.*(picture|piture|image|photo|wallpaper|artwork)",
    ]

    # Regex patterns for local system facts / math / time / knowledge base
    LOCAL_FACTS_PATTERNS = [
        r"^(what('s|\s+is)\s+(the\s+)?(current\s+)?(time|date|day|hour|timestamp)|what\s+time\s+is\s+it)\??$",
        r"^(today('s)?\s+date|current\s+time)\??$",
        r"^(calculate|compute|eval|what\s+is)\s+[\d\.\s\+\-\*\/\(\)\^\%]+$",
        r"^[\d\.\s\+\-\*\/\(\)\^\%]{3,}$",
        r"\bconvert\s+\d+(\.\d+)?\s*(usd|eur|gbp|inr|jpy|cad|aud)\s+to\s+(usd|eur|gbp|inr|jpy|cad|aud)\b",
        r"\b(who\s+are\s+you|what\s+is\s+sage\s+ai|about\s+sage|what\s+is\s+sage\s+engine)\b",
        r"\b(who\s+(created|made|built|developed|designed|founded)\s+(you|sage|sage\s+ai|this\s+(app|software|project)|sage(\s+engine)?)|who\s+is\s+(your|the)\s+(creator|developer|founder|maker|author|father)|who\s+owns\s+(you|sage)|who\s+is\s+suraj(\s+sharma)?|suraj\s+sharma)\b",
        r"\b(cheatsheet|cheat\s+sheet|knowledge\s+base|offline\s+guide|offline\s+facts|offline\s+help|what\s+can\s+you\s+do\s+offline)\b",
        r"\b(show\s+(me\s+)?(the\s+)?(sage\s+ai\s+)?(local\s+)?knowledge\s+base|show\s+cheatsheets)\b",
        r"\b(git\s+commands|git\s+cheatsheet|python\s+cheatsheet|pyside6\s+reference|markdown\s+cheatsheet|sql\s+cheatsheet|linux\s+commands)\b",
        r"^(hi|hello|hey|yoo+|yo|greetings|howdy|sup)[\s\!\.\?]*$",
    ]

    @classmethod
    def analyze(
        cls,
        prompt: str,
        force_web: bool = False,
        selected_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyzes a prompt and returns an intent dictionary.
        
        Returns:
            {
                "intent": str,
                "confidence": float,
                "matched_pattern": Optional[str],
                "force_web": bool,
                "selected_model": Optional[str],
                "clean_query": str
            }
        """
        cleaned = prompt.strip()
        lower_prompt = cleaned.lower()

        # If user explicitly toggled web search and didn't ask for an image
        if force_web:
            return {
                "intent": INTENT_WEB_SEARCH,
                "confidence": 1.0,
                "matched_pattern": "manual_web_toggle",
                "force_web": True,
                "selected_model": selected_model,
                "clean_query": cleaned,
            }

        # 1. Local facts & time (highest priority for instant responses)
        for pattern in cls.LOCAL_FACTS_PATTERNS:
            if re.search(pattern, lower_prompt):
                return {
                    "intent": INTENT_LOCAL_FACTS,
                    "confidence": 0.98,
                    "matched_pattern": pattern,
                    "force_web": False,
                    "selected_model": selected_model,
                    "clean_query": cleaned,
                }

        # 2. Image generation
        for pattern in cls.IMAGE_PATTERNS:
            if re.search(pattern, lower_prompt):
                return {
                    "intent": INTENT_IMAGE,
                    "confidence": 0.95,
                    "matched_pattern": pattern,
                    "force_web": False,
                    "selected_model": selected_model,
                    "clean_query": cleaned,
                }

        # 3. GitHub research
        for pattern in cls.GITHUB_PATTERNS:
            if re.search(pattern, lower_prompt):
                return {
                    "intent": INTENT_GITHUB,
                    "confidence": 0.92,
                    "matched_pattern": pattern,
                    "force_web": False,
                    "selected_model": selected_model,
                    "clean_query": cleaned,
                }

        # 4. Coding & App development
        for pattern in cls.CODING_PATTERNS:
            if re.search(pattern, lower_prompt):
                return {
                    "intent": INTENT_CODING,
                    "confidence": 0.90,
                    "matched_pattern": pattern,
                    "force_web": False,
                    "selected_model": selected_model,
                    "clean_query": cleaned,
                }

        # 5. Web Search
        for pattern in cls.WEB_PATTERNS:
            if re.search(pattern, lower_prompt):
                return {
                    "intent": INTENT_WEB_SEARCH,
                    "confidence": 0.85,
                    "matched_pattern": pattern,
                    "force_web": False,
                    "selected_model": selected_model,
                    "clean_query": cleaned,
                }

        # 6. Fallback to General Chat
        return {
            "intent": INTENT_GENERAL_CHAT,
            "confidence": 0.70,
            "matched_pattern": None,
            "force_web": False,
            "selected_model": selected_model,
            "clean_query": cleaned,
        }
