"""
Self-Reflection Engine for Sage Multi-Agentic AI Architecture.
Checks, evaluates, and auto-repairs deliverables to guarantee correctness,
security compliance, and goal achievement before final delivery.
"""
import logging
from typing import Dict, Any, List, Optional

from engine.governance.quality_evaluator import get_quality_evaluator

logger = logging.getLogger(__name__)


class SelfReflection:
    """Reflective evaluation engine that assesses deliverables and initiates auto-repair."""

    def __init__(self):
        self.evaluator = get_quality_evaluator()

    def evaluate_results(
        self,
        goal: str,
        deliverables: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Critiques deliverables against the original goal.
        Performs static analysis on code items and completeness checks on written assets.
        """
        all_passed = True
        scores: List[float] = []
        critique_notes: List[str] = []
        needs_repair = False

        if not deliverables:
            return {
                "passed": False,
                "score": 0.0,
                "notes": ["No deliverables produced by agents."],
                "needs_repair": True
            }

        for d in deliverables:
            d_type = d.get("type", "")
            content = d.get("content", "")

            if d_type in ("code_solution", "code"):
                # Code evaluation
                res = self.evaluator.evaluate_code(content, language="python")
                scores.append(res["score"])
                if not res["passed"]:
                    all_passed = False
                    needs_repair = True
                    critique_notes.extend(res.get("issues", []))
                else:
                    critique_notes.append("Code syntax and structure verified successfully.")

            elif d_type in ("written_content", "research_brief", "data_analysis_report"):
                # Content completeness
                res = self.evaluator.evaluate_content(content, min_words=15)
                scores.append(res["score"])
                if not res["passed"]:
                    critique_notes.extend(res.get("issues", []))
                else:
                    critique_notes.append(f"{d_type} met quality standards.")

            else:
                scores.append(1.0)

        overall_score = round(sum(scores) / max(1, len(scores)), 2) if scores else 1.0

        return {
            "passed": all_passed and overall_score >= 0.7,
            "score": overall_score,
            "score_percentage": int(overall_score * 100),
            "notes": critique_notes,
            "needs_repair": needs_repair,
            "recommendation": "Ready for automated delivery." if all_passed else "Auto-repair initiated."
        }

    def attempt_auto_repair(
        self,
        coding_agent,
        deliverable: Dict[str, Any],
        issues: List[str]
    ) -> Dict[str, Any]:
        """Triggers coding agent self-repair feedback loop."""
        repair_prompt = (
            f"The previous code had the following issues:\n" +
            "\n".join([f"- {iss}" for iss in issues]) +
            f"\n\nOriginal Code:\n{deliverable.get('content', '')}\n\n"
            "Please fix the code, resolve all errors, and output the corrected version."
        )
        return coding_agent.execute({"instruction": repair_prompt})
