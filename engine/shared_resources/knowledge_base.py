"""
Knowledge Base for Sage Multi-Agentic AI Architecture.
Stores and indexes documents, system guidelines, architectural notes, and domain facts.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from config import KNOWLEDGE_BASE_PATH

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """Manages persistent documents, cheatsheets, and project notes."""

    def __init__(self, filepath: Optional[Path] = None):
        self.filepath = Path(filepath) if filepath else KNOWLEDGE_BASE_PATH
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        self._init_defaults()
                        return
                    data = json.loads(content)

                self._entries = {}
                if isinstance(data, dict):
                    if "facts" in data and isinstance(data["facts"], list):
                        for idx, item in enumerate(data["facts"]):
                            key = item.get("id") or f"fact_{idx}"
                            self._entries[key] = {
                                "title": item.get("title", f"Fact {idx}"),
                                "content": item.get("content", ""),
                                "tags": item.get("keywords", []) or item.get("tags", [])
                            }
                    else:
                        for k, v in data.items():
                            if isinstance(v, dict):
                                self._entries[k] = v
                            else:
                                self._entries[k] = {"title": k, "content": str(v), "tags": []}
                elif isinstance(data, list):
                    for idx, item in enumerate(data):
                        if isinstance(item, dict):
                            key = item.get("id") or item.get("key") or f"entry_{idx}"
                            self._entries[key] = {
                                "title": item.get("title", f"Entry {idx}"),
                                "content": item.get("content", ""),
                                "tags": item.get("tags", [])
                            }
            except Exception as e:
                logger.warning("Failed to load knowledge base from %s: %s", self.filepath, e)
                self._init_defaults()
        else:
            self._init_defaults()

    def _init_defaults(self):
        self._entries = {
            "sage_overview": {
                "title": "Sage Multi-Agentic AI Architecture Overview",
                "content": (
                    "Sage is an autonomous multi-agent AI system powered by an Orchestrator Core Brain "
                    "(Task Decomposer, Agent Router, Workflow Manager, Self-Reflection, Memory Manager) "
                    "coordinating 7 Specialized AI Agents: Research, Coding, Image/Media, Data Analysis, "
                    "Content, Execution, and Planning Agents."
                ),
                "tags": ["architecture", "overview", "sage", "agents"]
            },
            "system_design_principles": {
                "title": "Sage Engineering Principles",
                "content": (
                    "1. Decomposed execution: Complex goals are partitioned into clear dependency steps.\n"
                    "2. Cross-agent synergy: Output from one agent feeds seamlessly into the next.\n"
                    "3. Self-reflection & Auto-retry: Code and documents are validated before final delivery.\n"
                    "4. Safe sandbox: Operations outside the workspace root are guarded against path traversal."
                ),
                "tags": ["principles", "security", "workflow"]
            }
        }
        self._save()

    def _save(self):
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2)
        except Exception as e:
            logger.error("Failed to save knowledge base: %s", e)

    def get_entry(self, key: str) -> Optional[Dict[str, Any]]:
        return self._entries.get(key)

    def list_entries(self) -> List[Dict[str, Any]]:
        out = []
        for k, v in self._entries.items():
            if isinstance(v, dict):
                out.append({"key": k, **v})
            else:
                out.append({"key": k, "title": k, "content": str(v), "tags": []})
        return out

    def add_entry(self, key: str, title: str, content: str, tags: Optional[List[str]] = None) -> bool:
        self._entries[key] = {
            "title": title,
            "content": content,
            "tags": tags or []
        }
        self._save()
        return True

    def delete_entry(self, key: str) -> bool:
        """Removes an entry from the knowledge base."""
        if key in self._entries:
            del self._entries[key]
            self._save()
            return True
        return False

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Keyword and token relevance matching across entries."""
        q_tokens = set(query.lower().split())
        scored = []
        for key, entry in self._entries.items():
            title_text = entry.get("title", "").lower()
            content_text = entry.get("content", "").lower()
            tags = [t.lower() for t in entry.get("tags", [])]

            score = 0
            for t in q_tokens:
                if t in title_text:
                    score += 3
                if t in content_text:
                    score += 1
                if t in tags:
                    score += 2

            if score > 0:
                scored.append((score, {"key": key, **entry}))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:limit]]


_knowledge_base_instance: Optional[KnowledgeBase] = None

def get_knowledge_base() -> KnowledgeBase:
    global _knowledge_base_instance
    if _knowledge_base_instance is None:
        _knowledge_base_instance = KnowledgeBase()
    return _knowledge_base_instance
