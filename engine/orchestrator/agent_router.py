"""
Agent Router for Sage Multi-Agentic AI Architecture.
Selects and assigns the optimal specialized AI agent based on subtask requirements,
capabilities, and user model/agent selections.
"""
import re
import logging
from typing import Dict, Any, Optional

from config import (
    AGENT_RESEARCH,
    AGENT_CODING,
    AGENT_IMAGE_MEDIA,
    AGENT_DATA_ANALYSIS,
    AGENT_CONTENT,
    AGENT_EXECUTION,
    AGENT_PLANNING,
    INTENT_CODING,
    INTENT_WEB_SEARCH,
    INTENT_GITHUB,
    INTENT_IMAGE,
    INTENT_LOCAL_FACTS,
    INTENT_GENERAL_CHAT,
)

logger = logging.getLogger(__name__)


class AgentRouter:
    """Intelligently routes goals and subtasks to specialized AI agents."""

    def route_query(
        self,
        prompt: str,
        force_web: bool = False,
        selected_agent: Optional[str] = None
    ) -> str:
        """
        Determines the primary specialized agent for a single turn query.
        """
        # 1. Manual user override
        if selected_agent and selected_agent in (
            AGENT_RESEARCH, AGENT_CODING, AGENT_IMAGE_MEDIA, AGENT_DATA_ANALYSIS,
            AGENT_CONTENT, AGENT_EXECUTION, AGENT_PLANNING
        ):
            return selected_agent

        prompt_clean = prompt.strip().lower()

        # 2. Force web toggle
        if force_web:
            return AGENT_RESEARCH

        # 3. Image / Visual Patterns
        if any(w in prompt_clean for w in ("generate image", "create image", "draw", "render image", "paint", "txt2img", "diagram", "ui mockup")):
            return AGENT_IMAGE_MEDIA

        # 4. Data Analysis Patterns
        if any(w in prompt_clean for w in ("analyze data", "csv", "excel", "calculate stats", "statistics", "dataset", "dataframe")):
            return AGENT_DATA_ANALYSIS

        # 5. Planning / Roadmap Patterns
        if any(w in prompt_clean for w in ("plan a project", "create roadmap", "project milestones", "architecture design", "strategy for")):
            return AGENT_PLANNING

        # 6. Execution / Deployment Patterns
        if prompt_clean.startswith("run ") or prompt_clean.startswith("exec ") or any(w in prompt_clean for w in ("deploy to", "execute command", "schedule task", "send email")):
            return AGENT_EXECUTION

        # 7. Web Research Patterns
        if any(w in prompt_clean for w in ("search web", "look up", "latest news", "current price", "who won", "what happened in 2026", "what happened today")):
            return AGENT_RESEARCH

        # 8. Coding Patterns
        coding_keywords = (
            "code", "python", "javascript", "typescript", "c++", "rust", "html", "css",
            "function", "class", "def ", "import ", "const ", "refactor", "debug", "traceback",
            "syntaxerror", "pytest", "unit test", "algorithm", "fix the bug", "write an app"
        )
        if any(w in prompt_clean for w in coding_keywords) or "```" in prompt:
            return AGENT_CODING

        # 9. Default to Content Agent for general conversation, writing, and explanations
        return AGENT_CONTENT

    def get_agent_instance(self, agent_name: str):
        """Instantiates or retrieves the requested specialized agent."""
        from engine.agents.research_agent import ResearchAgent
        from engine.agents.coding_agent import CodingAgent
        from engine.agents.image_media_agent import ImageMediaAgent
        from engine.agents.data_analysis_agent import DataAnalysisAgent
        from engine.agents.content_agent import ContentAgent
        from engine.agents.execution_agent import ExecutionAgent
        from engine.agents.planning_agent import PlanningAgent

        agent_map = {
            AGENT_RESEARCH: ResearchAgent,
            AGENT_CODING: CodingAgent,
            AGENT_IMAGE_MEDIA: ImageMediaAgent,
            AGENT_DATA_ANALYSIS: DataAnalysisAgent,
            AGENT_CONTENT: ContentAgent,
            AGENT_EXECUTION: ExecutionAgent,
            AGENT_PLANNING: PlanningAgent,
        }

        agent_cls = agent_map.get(agent_name, ContentAgent)
        return agent_cls()
