"""
Research Agent for Sage Multi-Agentic AI Architecture.
Capabilities:
- Web search
- Gather information
- Read documents
- Summarize research
"""
from typing import Dict, Any, Optional, Callable

from config import AGENT_RESEARCH
from .base_agent import BaseAgent


class ResearchAgent(BaseAgent):
    """Specialized in live web research, document digestion, and evidence synthesis."""

    def __init__(self):
        super().__init__(name=AGENT_RESEARCH, role_id="research")

    def execute(
        self,
        task_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        query = task_input.get("query") or task_input.get("instruction") or ""
        task_id = (context or {}).get("task_id")

        if on_stage:
            on_stage("🔍 Research Agent: Gathering intelligence and live evidence...")
        self.log("Gathering research intelligence", task_id=task_id, details={"query": query})

        # 1. Execute Web Search
        from engine.providers.search_provider import SearchProvider
        search_prov = SearchProvider()
        search_res = search_prov.generate(query)
        evidence = search_res.text or ""
        citations = search_res.citations or []

        # 2. Check Vector Knowledge Base for domain context
        vector_matches = self.vector_db.search(query, top_k=2)
        kb_context = ""
        if vector_matches:
            kb_context = "\n\nRelevant Local Knowledge:\n" + "\n".join(
                [f"- {m['title']}: {m['content']}" for m in vector_matches]
            )

        if on_stage:
            on_stage("🔍 Research Agent: Synthesizing comprehensive research summary...")

        # 3. Synthesize Findings with LLM
        system_prompt = (
            "You are Sage AI's specialized Research Agent. Your job is to gather, verify, "
            "and summarize information with precision, structured bullet points, and accurate citations."
        )
        synthesis_prompt = (
            f"Research Topic: {query}\n\n"
            f"Web Evidence:\n{evidence}\n"
            f"{kb_context}\n\n"
            "Synthesize a clear, actionable, and comprehensive briefing on this topic. "
            "Include key takeaways, current facts, and reference sources."
        )

        llm_res = self.call_llm(
            prompt=synthesis_prompt,
            system_prompt=system_prompt,
            on_chunk=on_chunk,
            preferred_providers=["groq", "gemini", "openrouter", "nvidia", "ollama", "local_facts"]
        )

        final_text = llm_res.get("text", "")
        # Save findings to Shared Memory for other agents to consume
        self.shared_memory.set(
            key=f"research_{query[:30]}",
            value={"summary": final_text, "citations": citations},
            is_long_term=False,
            memory_type="research",
            agent_source=self.name
        )

        self.send_bus_message(
            to_agent="all",
            message_type="research_completed",
            content=f"Research completed on: '{query[:40]}...'",
            task_id=task_id
        )

        return {
            "success": True,
            "agent": self.name,
            "summary": final_text,
            "citations": citations,
            "evidence": evidence,
            "deliverables": [
                {
                    "type": "research_brief",
                    "title": f"Research Brief: {query[:40]}",
                    "content": final_text,
                    "citations": citations
                }
            ]
        }
