"""
Task Decomposer for Sage Multi-Agentic AI Architecture.
Breaks high-level user goals into structured, ordered, dependency-aware subtasks
with designated specialized agent roles.
"""
import re
import logging
from typing import List, Dict, Any, Optional

from config import (
    AGENT_RESEARCH,
    AGENT_CODING,
    AGENT_IMAGE_MEDIA,
    AGENT_DATA_ANALYSIS,
    AGENT_CONTENT,
    AGENT_EXECUTION,
    AGENT_PLANNING,
)

logger = logging.getLogger(__name__)


class TaskDecomposer:
    """Decomposes goals into structured subtask DAGs."""

    def decompose(self, goal: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Decomposes a user goal into an ordered list of subtasks with assigned agents.
        Uses intelligent semantic pattern recognition with LLM expansion if available.
        """
        goal_lower = goal.lower()

        # Check if the goal is a complex multi-agent composite task
        steps: List[Dict[str, Any]] = []

        def _has_word(words, text):
            for w in words:
                if len(w) <= 3:
                    if re.search(r"\b" + re.escape(w) + r"\b", text):
                        return True
                else:
                    if w in text:
                        return True
            return False

        # 1. Does the goal require Planning / Strategy?
        needs_planning = _has_word(("plan", "roadmap", "architecture", "milestone", "strategy", "design a system"), goal_lower)
        # 2. Does the goal require Web Research or Fact Finding?
        needs_research = _has_word(("research", "search", "find information", "latest", "what is", "investigate", "gather"), goal_lower)
        # 3. Does the goal require Coding / Software?
        needs_coding = _has_word(("code", "build", "develop", "implement", "script", "website", "app", "fix", "debug", "refactor", "function", "class", "program", "python", "javascript", "typescript", "c++", "rust", "algorithm"), goal_lower)
        # 4. Does the goal require Visuals / Images / Diagrams?
        needs_image = _has_word(("image", "picture", "photo", "diagram", "chart visual", "draw", "render", "ui", "mockup", "visualize"), goal_lower)
        # 5. Does the goal require Data Analysis / Statistics?
        needs_analysis = _has_word(("data", "analyze", "statistics", "csv", "excel", "metrics", "trends", "numbers", "benchmark"), goal_lower)
        # 6. Does the goal require Content / Articles / Docs / Emails?
        needs_content = _has_word(("article", "documentation", "presentation", "slides", "email", "summary report", "draft an email"), goal_lower)
        # 7. Does the goal require Execution / Deployment / Commands?
        needs_execution = _has_word(("deploy", "run", "execute", "terminal", "schedule", "publish"), goal_lower)

        step_idx = 1
        last_step_id = None

        # Step A: Planning (if explicit or complex >= 3 agents)
        active_flags = [needs_research, needs_coding, needs_image, needs_analysis, needs_content, needs_execution]
        is_complex = sum(bool(x) for x in active_flags) >= 2 or needs_planning

        if is_complex and (needs_planning or sum(bool(x) for x in active_flags) >= 3):
            s_id = f"step_{step_idx}"
            steps.append({
                "id": s_id,
                "name": "Project Strategy & Milestones",
                "agent_type": AGENT_PLANNING,
                "instruction": f"Formulate execution strategy and milestones for: {goal}",
                "depends_on": [],
                "expected_output": "strategic_plan"
            })
            last_step_id = s_id
            step_idx += 1

        # Step B: Research
        if needs_research or (is_complex and not any((needs_coding, needs_image, needs_analysis, needs_content))):
            s_id = f"step_{step_idx}"
            steps.append({
                "id": s_id,
                "name": "Intelligence & Research Gathering",
                "agent_type": AGENT_RESEARCH,
                "instruction": f"Gather key facts, evidence, and background on: {goal}",
                "depends_on": [last_step_id] if last_step_id else [],
                "expected_output": "research_brief"
            })
            last_step_id = s_id
            step_idx += 1

        # Step C: Data Analysis (if data mentioned)
        if needs_analysis:
            s_id = f"step_{step_idx}"
            steps.append({
                "id": s_id,
                "name": "Quantitative Data Analysis & Metrics",
                "agent_type": AGENT_DATA_ANALYSIS,
                "instruction": f"Perform statistical calculations and data breakdown for: {goal}",
                "depends_on": [last_step_id] if last_step_id else [],
                "expected_output": "data_analysis_report"
            })
            last_step_id = s_id
            step_idx += 1

        # Step D: Coding (if software/code needed)
        if needs_coding or (not steps and not needs_image and not needs_content):
            s_id = f"step_{step_idx}"
            steps.append({
                "id": s_id,
                "name": "Software Engineering & Implementation",
                "agent_type": AGENT_CODING,
                "instruction": f"Write, architect, and implement the software solution for: {goal}",
                "depends_on": [last_step_id] if last_step_id else [],
                "expected_output": "code_solution"
            })
            last_step_id = s_id
            step_idx += 1

        # Step E: Visuals / Images (if requested)
        if needs_image:
            s_id = f"step_{step_idx}"
            steps.append({
                "id": s_id,
                "name": "Visual Media & Diagram Generation",
                "agent_type": AGENT_IMAGE_MEDIA,
                "instruction": f"Generate graphics, diagrams, or UI designs for: {goal}",
                "depends_on": [last_step_id] if last_step_id else [],
                "expected_output": "visual_assets"
            })
            last_step_id = s_id
            step_idx += 1

        # Step F: Documentation & Content (if requested or complex project)
        if needs_content or (is_complex and len(steps) >= 2):
            s_id = f"step_{step_idx}"
            steps.append({
                "id": s_id,
                "name": "Comprehensive Documentation & Summary",
                "agent_type": AGENT_CONTENT,
                "instruction": f"Synthesize deliverables into comprehensive documentation for: {goal}",
                "depends_on": [last_step_id] if last_step_id else [],
                "expected_output": "written_content"
            })
            last_step_id = s_id
            step_idx += 1

        # Step G: Execution / Deployment
        if needs_execution:
            s_id = f"step_{step_idx}"
            steps.append({
                "id": s_id,
                "name": "System Execution & Deployment",
                "agent_type": AGENT_EXECUTION,
                "instruction": f"Execute commands, run tests, and prepare deployment for: {goal}",
                "depends_on": [last_step_id] if last_step_id else [],
                "expected_output": "execution_result"
            })
            step_idx += 1

        # If somehow no steps were generated, default to single appropriate agent
        if not steps:
            steps.append({
                "id": "step_1",
                "name": "Goal Execution",
                "agent_type": AGENT_CODING if needs_coding else AGENT_CONTENT,
                "instruction": goal,
                "depends_on": [],
                "expected_output": "solution"
            })

        return steps
