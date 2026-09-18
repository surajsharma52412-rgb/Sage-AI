"""
Memory Manager for Sage Multi-Agentic AI Architecture.
Coordinates short-term working context, long-term persistence,
and semantic vector memory across all agent executions.
"""
import uuid
import logging
from typing import Dict, Any, Optional, List

from engine.shared_resources.shared_memory import get_shared_memory
from engine.shared_resources.vector_db import get_vector_db
from engine.shared_resources.knowledge_base import get_knowledge_base
from database.db_manager import get_db

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages short-term conversation context and long-term semantic memory."""

    def __init__(self):
        self.shared_memory = get_shared_memory()
        self.vector_db = get_vector_db()
        self.knowledge_base = get_knowledge_base()
        self.db = get_db()

    def store_task_outcome(self, task_id: str, goal: str, summary: str):
        """Indexes completed goal outcome in long-term memory and vector store."""
        self.shared_memory.set(
            key=f"task_{task_id}",
            value={"goal": goal, "summary": summary},
            is_long_term=True,
            memory_type="task_outcome",
            agent_source="orchestrator"
        )

        try:
            self.vector_db.add_document(
                doc_id=f"task_{task_id}",
                title=f"Goal: {goal[:50]}",
                content=summary,
                tags="completed_task,goal"
            )
        except Exception as e:
            logger.debug("Failed to index task outcome into vector DB: %s", e)

    def teach_memory(
        self,
        title: str,
        content: str,
        category: str = "directive",
        tags: str = ""
    ) -> Dict[str, Any]:
        """
        Teaches the model a persistent memory, rule, fact, preference, or project knowledge.
        Indexes across Vector DB, Shared Memory, and Knowledge Base.
        """
        mem_id = f"mem_{uuid.uuid4().hex[:8]}"
        display_title = f"[{category.capitalize()}] {title.strip()}"
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if category not in tag_list:
            tag_list.append(category)

        # 1. Index in Vector Database
        try:
            self.vector_db.add_document(
                doc_id=mem_id,
                title=display_title,
                content=content.strip(),
                tags=",".join(tag_list)
            )
        except Exception as e:
            logger.warning("Failed to store memory in vector DB: %s", e)

        # 2. Store in Shared Memory
        self.shared_memory.set(
            key=mem_id,
            value={
                "id": mem_id,
                "title": title.strip(),
                "content": content.strip(),
                "category": category,
                "tags": tag_list
            },
            is_long_term=True,
            memory_type=category,
            agent_source="user"
        )

        # 3. Store in Knowledge Base
        try:
            self.knowledge_base.add_entry(
                key=mem_id,
                title=display_title,
                content=content.strip(),
                tags=tag_list
            )
        except Exception as e:
            logger.warning("Failed to store memory in knowledge base: %s", e)

        return {
            "id": mem_id,
            "title": title.strip(),
            "display_title": display_title,
            "content": content.strip(),
            "category": category,
            "tags": tag_list
        }

    def forget_memory(self, mem_id: str) -> bool:
        """Removes a taught memory or knowledge entry from all stores."""
        success_v = self.vector_db.delete_document(mem_id)
        success_k = self.knowledge_base.delete_entry(mem_id)
        return success_v or success_k

    def list_all_memories(self) -> List[Dict[str, Any]]:
        """Retrieves all memories and custom knowledge entries."""
        memories = []
        seen_ids = set()

        # From Vector DB
        for doc in self.vector_db.list_all_documents():
            doc_id = doc.get("id", "")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                memories.append(doc)

        # From Knowledge Base
        for entry in self.knowledge_base.list_entries():
            key = entry.get("key", "")
            if key and key not in seen_ids:
                seen_ids.add(key)
                memories.append({
                    "id": key,
                    "title": entry.get("title", ""),
                    "content": entry.get("content", ""),
                    "tags": ",".join(entry.get("tags", [])) if isinstance(entry.get("tags"), list) else entry.get("tags", "")
                })

        return memories

    def retrieve_relevant_context(self, query: str, top_k: int = 5) -> str:
        """Retrieves semantically relevant memories, directives, and facts."""
        matches = self.vector_db.search(query, top_k=top_k)
        if not matches:
            # Fallback to keyword search on knowledge base
            kb_matches = self.knowledge_base.search(query, limit=top_k)
            if not kb_matches:
                return ""
            lines = ["Relevant Learned Knowledge & Directives:"]
            for m in kb_matches:
                lines.append(f"- [{m.get('title', 'Memory')}]: {m.get('content', '')[:300]}")
            return "\n".join(lines)

        context_lines = ["Relevant Learned Knowledge & Directives:"]
        for m in matches:
            context_lines.append(f"- [{m['title']}] (Relevance: {int(m['score']*100)}%): {m['content'][:300]}")
        return "\n".join(context_lines)

    def clear_session_scratchpad(self):
        """Clears short-term ephemeral memory."""
        self.shared_memory.clear_short_term()

