"""
Quality Evaluator for Sage Multi-Agentic AI Architecture.
Performs verification checks on code, documentation, and structured deliverables.
"""
import ast
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class QualityEvaluator:
    """Pre-flight and post-execution validation for deliverables."""

    def evaluate_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Validates code syntax and basic structure."""
        issues = []
        if not code or not code.strip():
            return {"passed": False, "score": 0.0, "issues": ["Code content is empty."]}

        if language.lower() in ("python", "py"):
            try:
                ast.parse(code)
            except SyntaxError as e:
                issues.append(f"Syntax error on line {e.lineno}: {e.msg}")

        score = 1.0 if not issues else max(0.0, 1.0 - (0.3 * len(issues)))
        return {
            "passed": len(issues) == 0,
            "score": round(score, 2),
            "issues": issues,
            "language": language
        }

    def evaluate_json(self, text: str) -> Dict[str, Any]:
        """Validates JSON parsing."""
        try:
            parsed = json.loads(text)
            return {"passed": True, "score": 1.0, "issues": [], "data": parsed}
        except Exception as e:
            return {"passed": False, "score": 0.0, "issues": [f"Invalid JSON: {str(e)}"]}

    def evaluate_content(self, text: str, min_words: int = 10) -> Dict[str, Any]:
        """Validates text deliverables for completeness."""
        words = text.strip().split()
        issues = []
        if len(words) < min_words:
            issues.append(f"Content too brief ({len(words)} words, minimum required: {min_words}).")

        return {
            "passed": len(issues) == 0,
            "score": 1.0 if not issues else 0.5,
            "issues": issues,
            "word_count": len(words)
        }


_quality_evaluator_instance: Optional[QualityEvaluator] = None

def get_quality_evaluator() -> QualityEvaluator:
    global _quality_evaluator_instance
    if _quality_evaluator_instance is None:
        _quality_evaluator_instance = QualityEvaluator()
    return _quality_evaluator_instance
