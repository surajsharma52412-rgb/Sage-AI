"""
Tool Registry for Sage Multi-Agentic AI Architecture.
Registers, discovers, and executes tools for all specialized AI agents.
"""
import logging
from typing import Dict, Any, Callable, List, Optional

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry of executable tools accessible by specialized agents."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ToolRegistry, cls).__new__(cls)
            cls._instance._tools = {}
            cls._instance._init_default_tools()
        return cls._instance

    def register_tool(
        self,
        name: str,
        func: Callable[..., Any],
        description: str,
        parameters_schema: Optional[Dict[str, Any]] = None,
        category: str = "general"
    ):
        """Registers an executable tool."""
        self._tools[name] = {
            "name": name,
            "func": func,
            "description": description,
            "parameters": parameters_schema or {},
            "category": category
        }
        logger.debug("Registered tool: %s (%s)", name, category)

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        if category:
            return [t for t in self._tools.values() if t.get("category") == category]
        return list(self._tools.values())

    def execute_tool(self, name: str, **kwargs) -> Dict[str, Any]:
        """Executes a registered tool by name with exception trapping."""
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "error": f"Tool '{name}' not found in registry."}

        try:
            res = tool["func"](**kwargs)
            return {"success": True, "result": res}
        except Exception as e:
            logger.error("Error executing tool '%s': %s", name, e)
            return {"success": False, "error": str(e)}

    def _init_default_tools(self):
        """Registers standard platform tools."""
        # 1. Web Search
        def _search(query: str) -> str:
            from engine.providers.search_provider import SearchProvider
            sp = SearchProvider()
            resp = sp.generate(query)
            return resp.text

        self.register_tool(
            name="web_search",
            func=_search,
            description="Search the web for real-time news, documentation, and factual evidence.",
            parameters_schema={"query": {"type": "string", "description": "Search query terms"}},
            category="research"
        )

        # 2. Workspace File Read
        def _read_file(path: str) -> str:
            from engine.shared_resources.project_workspace import get_project_workspace
            return get_project_workspace().read_file(path)

        self.register_tool(
            name="read_file",
            func=_read_file,
            description="Read the contents of a file in the project workspace.",
            parameters_schema={"path": {"type": "string", "description": "Relative file path"}},
            category="workspace"
        )

        # 3. Workspace File Write
        def _write_file(path: str, content: str) -> Dict[str, Any]:
            from engine.shared_resources.project_workspace import get_project_workspace
            return get_project_workspace().write_file(path, content)

        self.register_tool(
            name="write_file",
            func=_write_file,
            description="Write or overwrite content to a file in the project workspace.",
            parameters_schema={
                "path": {"type": "string", "description": "Relative file path"},
                "content": {"type": "string", "description": "File text content"}
            },
            category="workspace"
        )

        # 4. List Files
        def _list_files(depth: int = 3) -> List[Dict[str, Any]]:
            from engine.shared_resources.project_workspace import get_project_workspace
            return get_project_workspace().list_tree(max_depth=depth)

        self.register_tool(
            name="list_files",
            func=_list_files,
            description="List directory structure and files in project workspace.",
            parameters_schema={"depth": {"type": "integer", "default": 3}},
            category="workspace"
        )

        # 5. Vector Knowledge Search
        def _vector_search(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
            from engine.shared_resources.vector_db import get_vector_db
            return get_vector_db().search(query, top_k=top_k)

        self.register_tool(
            name="vector_search",
            func=_vector_search,
            description="Perform semantic vector search across notes and knowledge docs.",
            parameters_schema={"query": {"type": "string"}},
            category="knowledge"
        )


def get_tool_registry() -> ToolRegistry:
    return ToolRegistry()
