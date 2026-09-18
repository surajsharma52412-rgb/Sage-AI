"""
Standardized Tool Registry for SAGE Autonomous Automation Agent.
Each tool is registered with:
- Category (email, file, system, knowledge)
- is_risky: True if tool modifies external state, deletes data, or transmits messages
- is_idempotent: True if safe to retry without compounding side effects
- schema: Parameter expectations
- handler: Callable executing the action
"""
import os
import sys
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Callable, List, Optional

import inspect

logger = logging.getLogger(__name__)


class AutomationTool:
    def __init__(
        self,
        name: str,
        category: str,
        description: str,
        handler: Callable[..., Dict[str, Any]],
        is_risky: bool = False,
        is_idempotent: bool = True,
        risk_description: str = "",
        parameters_schema: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.category = category
        self.description = description
        self.handler = handler
        self.is_risky = is_risky
        self.is_idempotent = is_idempotent
        self.risk_description = risk_description
        self.parameters_schema = parameters_schema or {}

    def execute(self, **kwargs) -> Dict[str, Any]:
        sig = inspect.signature(self.handler)
        has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if has_varkw:
            return self.handler(**kwargs)
        filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return self.handler(**filtered)


class AutomationToolRegistry:
    """Central registry of executable automation tools."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self._tools: Dict[str, AutomationTool] = {}
        self._register_default_tools()

    def register(self, tool: AutomationTool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[AutomationTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "category": t.category,
                "description": t.description,
                "is_risky": t.is_risky,
                "is_idempotent": t.is_idempotent,
                "risk_description": t.risk_description,
                "parameters": t.parameters_schema
            }
            for t in self._tools.values()
        ]

    def execute_tool(self, name: str, **kwargs) -> Dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            return {
                "success": False,
                "tool": name,
                "error": f"Tool '{name}' not found in registry."
            }
        try:
            res = tool.execute(**kwargs)
            res["tool"] = name
            return res
        except Exception as e:
            logger.error("Error running tool '%s': %s", name, e, exc_info=True)
            return {
                "success": False,
                "tool": name,
                "error": str(e)
            }

    def _resolve_path(self, rel_path: str) -> Path:
        from engine.security_vault import SecurityVault
        return SecurityVault.validate_safe_path(rel_path, self.workspace_root, allow_temp=True)

    def _register_default_tools(self):
        # ── 1. EMAIL TOOLS ──────────────────────────────────────────
        def _fetch_emails(max_count: int = 5) -> Dict[str, Any]:
            from engine.automation_agent import GmailAutomationService
            service = GmailAutomationService()
            emails = service.fetch_unread_emails(max_count=max_count)
            return {
                "success": True,
                "count": len(emails),
                "emails": emails,
                "message": f"Retrieved {len(emails)} unread emails."
            }

        self.register(AutomationTool(
            name="fetch_emails",
            category="email",
            description="Fetch unread emails from Gmail or safe sandbox simulation.",
            handler=_fetch_emails,
            is_risky=False,
            is_idempotent=True,
            parameters_schema={"max_count": {"type": "integer", "default": 5}}
        ))

        def _draft_reply(email_data: Dict[str, Any], instructions: str = "", model: str = "Auto Router") -> Dict[str, Any]:
            from engine.automation_agent import GmailAutomationService
            service = GmailAutomationService()
            draft = service.draft_reply(email_data, user_instructions=instructions, model=model)
            return {
                "success": True,
                "draft": draft,
                "recipient": email_data.get("sender", ""),
                "subject": f"Re: {email_data.get('subject', '')}",
                "message": "AI reply draft generated successfully."
            }

        self.register(AutomationTool(
            name="draft_reply",
            category="email",
            description="Draft an intelligent, context-aware reply to an email without sending.",
            handler=_draft_reply,
            is_risky=False,
            is_idempotent=True,
            parameters_schema={
                "email_data": {"type": "object", "required": True},
                "instructions": {"type": "string", "default": ""},
                "model": {"type": "string", "default": "Auto Router"}
            }
        ))

        def _send_email(email_data: Dict[str, Any], reply_body: str, permission_granted: bool = False) -> Dict[str, Any]:
            if not permission_granted:
                return {
                    "success": False,
                    "status": "PERMISSION_REQUIRED",
                    "error": "Explicit permission required before transmitting email."
                }
            from engine.automation_agent import GmailAutomationService
            service = GmailAutomationService()
            # In automated pipeline with permission already granted:
            return service.execute_send_reply(
                email_data=email_data,
                reply_body=reply_body,
                permission_checker=lambda *args: True
            )

        self.register(AutomationTool(
            name="send_email",
            category="email",
            description="Transmit an email reply to external recipient via SMTP or sandbox.",
            handler=_send_email,
            is_risky=True,
            is_idempotent=False,
            risk_description="Transmits a real message to an external email address.",
            parameters_schema={
                "email_data": {"type": "object", "required": True},
                "reply_body": {"type": "string", "required": True},
                "permission_granted": {"type": "boolean", "default": False}
            }
        ))

        # ── 2. FILE & WORKSPACE TOOLS ──────────────────────────────
        def _read_file(path: str) -> Dict[str, Any]:
            full = self._resolve_path(path)
            if not full.exists():
                return {"success": False, "error": f"File not found: {path}"}
            content = full.read_text(encoding="utf-8", errors="replace")
            return {
                "success": True,
                "path": str(full),
                "size": len(content),
                "content": content
            }

        self.register(AutomationTool(
            name="read_file",
            category="file",
            description="Read content of a file in the workspace.",
            handler=_read_file,
            is_risky=False,
            is_idempotent=True,
            parameters_schema={"path": {"type": "string", "required": True}}
        ))

        def _list_directory(path: str = ".", max_depth: int = 2) -> Dict[str, Any]:
            full = self._resolve_path(path)
            if not full.exists() or not full.is_dir():
                return {"success": False, "error": f"Directory not found: {path}"}
            entries = []
            for root, dirs, files in os.walk(full):
                depth = len(Path(root).relative_to(full).parts)
                if depth > max_depth:
                    continue
                for d in dirs:
                    entries.append({"name": d, "type": "directory", "rel_path": str((Path(root) / d).relative_to(self.workspace_root))})
                for f in files:
                    entries.append({"name": f, "type": "file", "rel_path": str((Path(root) / f).relative_to(self.workspace_root))})
            return {"success": True, "count": len(entries), "entries": entries[:200]}

        self.register(AutomationTool(
            name="list_directory",
            category="file",
            description="List contents and subdirectories of workspace path.",
            handler=_list_directory,
            is_risky=False,
            is_idempotent=True,
            parameters_schema={"path": {"type": "string", "default": "."}}
        ))

        def _write_file(path: str, content: str) -> Dict[str, Any]:
            full = self._resolve_path(path)
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "path": str(full),
                "bytes_written": len(content.encode("utf-8")),
                "message": f"Wrote {len(content)} characters to {path}"
            }

        self.register(AutomationTool(
            name="write_file",
            category="file",
            description="Write or overwrite file in the workspace.",
            handler=_write_file,
            is_risky=True,
            is_idempotent=True,
            risk_description="Overwrites workspace file content with new data.",
            parameters_schema={
                "path": {"type": "string", "required": True},
                "content": {"type": "string", "required": True}
            }
        ))

        def _delete_file(path: str) -> Dict[str, Any]:
            full = self._resolve_path(path)
            if not full.exists():
                return {"success": False, "error": f"File does not exist: {path}"}
            if full.is_dir():
                shutil.rmtree(full)
            else:
                full.unlink()
            return {"success": True, "path": str(full), "message": f"Deleted {path}"}

        self.register(AutomationTool(
            name="delete_file",
            category="file",
            description="Permanently delete a file or directory in the workspace.",
            handler=_delete_file,
            is_risky=True,
            is_idempotent=False,
            risk_description="Permanently removes file or directory from the filesystem.",
            parameters_schema={"path": {"type": "string", "required": True}}
        ))

        def _clean_cache() -> Dict[str, Any]:
            cleaned_count = 0
            for root, dirs, files in os.walk(self.workspace_root):
                for d in list(dirs):
                    if d == "__pycache__":
                        p = Path(root) / d
                        shutil.rmtree(p, ignore_errors=True)
                        cleaned_count += 1
                for f in files:
                    if f.endswith((".pyc", ".tmp", ".pyo")):
                        (Path(root) / f).unlink(missing_ok=True)
                        cleaned_count += 1
            return {
                "success": True,
                "cleaned_items": cleaned_count,
                "message": f"Cleaned {cleaned_count} cache and temp artifacts."
            }

        self.register(AutomationTool(
            name="clean_workspace_cache",
            category="file",
            description="Purge temporary __pycache__ and orphan scratch files.",
            handler=_clean_cache,
            is_risky=True,
            is_idempotent=True,
            risk_description="Removes cache directories and temporary files.",
            parameters_schema={}
        ))

        # ── 3. SYSTEM & DIAGNOSTIC TOOLS ───────────────────────────
        def _execute_command(command: str, timeout: int = 30) -> Dict[str, Any]:
            from engine.security_vault import SecurityVault
            is_safe, reason = SecurityVault.validate_safe_command(command)
            if not is_safe:
                return {
                    "success": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"Security violation: {reason}"
                }

            creationflags = 0
            startupinfo = None
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            proc = subprocess.run(
                command,
                cwd=str(self.workspace_root),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=creationflags,
                startupinfo=startupinfo
            )
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout[:4000],
                "stderr": proc.stderr[:4000]
            }

        self.register(AutomationTool(
            name="execute_command",
            category="system",
            description="Execute shell or terminal command in the workspace.",
            handler=_execute_command,
            is_risky=True,
            is_idempotent=False,
            risk_description="Executes a system shell command with arbitrary side effects.",
            parameters_schema={"command": {"type": "string", "required": True}, "timeout": {"type": "integer", "default": 30}}
        ))

        def _run_unit_tests(test_target: str = "tests") -> Dict[str, Any]:
            target_path = self._resolve_path(test_target)
            if not target_path.exists():
                return {
                    "success": True,
                    "passed": True,
                    "output": f"Directory '{test_target}' not present in workspace. No unit tests to run.",
                    "message": "Test check skipped: no test suite present in workspace."
                }

            creationflags = 0
            startupinfo = None
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            cmd = [sys.executable, "-m", "unittest", "discover", test_target]
            proc = subprocess.run(
                cmd,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=creationflags,
                startupinfo=startupinfo
            )
            output = proc.stdout + "\n" + proc.stderr
            passed = "OK" in output and proc.returncode == 0
            return {
                "success": passed,
                "passed": passed,
                "output": output[:3000],
                "message": "Test suite passed." if passed else "Test suite encountered failures."
            }

        self.register(AutomationTool(
            name="run_unit_tests",
            category="system",
            description="Run unit test suites and check test health.",
            handler=_run_unit_tests,
            is_risky=False,
            is_idempotent=True,
            parameters_schema={"test_target": {"type": "string", "default": "tests"}}
        ))

        def _inspect_system_health() -> Dict[str, Any]:
            import platform
            total, used, free = shutil.disk_usage(self.workspace_root)
            return {
                "success": True,
                "os": platform.system(),
                "os_release": platform.release(),
                "python_version": platform.python_version(),
                "disk_free_gb": round(free / (1024 ** 3), 2),
                "disk_total_gb": round(total / (1024 ** 3), 2),
                "workspace": str(self.workspace_root)
            }

        self.register(AutomationTool(
            name="inspect_system_health",
            category="system",
            description="Check OS details, Python runtime, and free workspace disk space.",
            handler=_inspect_system_health,
            is_risky=False,
            is_idempotent=True,
            parameters_schema={}
        ))

        # ── 4. KNOWLEDGE & SEARCH TOOLS ────────────────────────────
        def _web_search(query: str) -> Dict[str, Any]:
            from engine.tools.tool_registry import get_tool_registry
            reg = get_tool_registry()
            res = reg.execute_tool("web_search", query=query)
            return {
                "success": res.get("success", False),
                "query": query,
                "result": res.get("result", "")
            }

        self.register(AutomationTool(
            name="web_search",
            category="knowledge",
            description="Query the web for factual data and online documentation.",
            handler=_web_search,
            is_risky=False,
            is_idempotent=True,
            parameters_schema={"query": {"type": "string", "required": True}}
        ))
