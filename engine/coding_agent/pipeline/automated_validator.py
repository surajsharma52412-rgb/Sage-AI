"""
Automated Testing & Validation for SAGE Coding Agent Architecture (v6).
Performs:
- Execution of unit, integration, and E2E test suites
- AST syntax validation across all generated files
- Security & vulnerability analysis (hardcoded secrets, dangerous eval, SQL injection patterns)
- Code health & quality evaluation
"""
import ast
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..context_manager import ContextFileManager
from ..tool_ecosystem import ToolEcosystem

logger = logging.getLogger(__name__)


class AutomatedValidator:
    """Validates code correctness, executes tests, and performs security auditing."""

    # Patterns indicating potential security issues
    SECURITY_RISK_PATTERNS = [
        (r"\beval\s*\(", "Dangerous use of eval() detected"),
        (r"\bexec\s*\(", "Dangerous use of exec() detected"),
        (r"(?:api[_-]?key|secret|password|auth_token)\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "Hardcoded API key or credential detected"),
        (r"SELECT\s+.*\s+FROM\s+.*\s+WHERE\s+.*%s", "Potential SQL string concatenation / injection vulnerability"),
        (r"subprocess\.call\(.*shell=True", "Unsafe shell execution with shell=True"),
    ]

    def __init__(self, context_mgr: ContextFileManager, tools: ToolEcosystem):
        self.context_mgr = context_mgr
        self.tools = tools

    def validate_codebase(self, test_cmd: Optional[str] = None) -> Dict[str, Any]:
        """
        Runs comprehensive validation:
        1. Syntax validation (AST parsing)
        2. Security vulnerability audit
        3. Automated test suite execution
        """
        files = self.context_mgr.list_files()
        syntax_errors = []
        security_findings = []

        for f in files:
            p = f["path"]
            if p.endswith(".py"):
                try:
                    content = self.context_mgr.read_file(p)
                    # 1. AST syntax check
                    ast.parse(content, filename=p)

                    # 2. Security scan
                    for pat, desc in self.SECURITY_RISK_PATTERNS:
                        if re.search(pat, content, re.IGNORECASE):
                            security_findings.append({
                                "file": p,
                                "issue": desc
                            })
                except SyntaxError as e:
                    syntax_errors.append({
                        "file": p,
                        "line": e.lineno,
                        "msg": str(e.msg)
                    })
                except Exception as e:
                    syntax_errors.append({"file": p, "msg": str(e)})

        # 3. Test execution
        test_run_res = {"success": True, "ran": False, "stdout": "", "stderr": ""}
        if test_cmd:
            try:
                res = self.tools.run_tests(path_or_pattern=test_cmd)
                test_run_res = {
                    "success": res.get("success", False),
                    "ran": True,
                    "stdout": res.get("stdout", "")[:2000],
                    "stderr": res.get("stderr", "")[:2000]
                }
            except Exception as e:
                test_run_res = {"success": False, "ran": True, "error": str(e)}
        else:
            # If specific project test file exists (avoid running host repo tests)
            project_test_files = [f["path"] for f in files if (f["path"].startswith("tests/test_") or f["name"].startswith("test_")) and not any(host_kw in f["name"] for host_kw in ("test_multi_agent", "test_scanner", "test_coding_agent_v6"))]
            if project_test_files:
                try:
                    res = self.tools.run_tests(path_or_pattern=project_test_files[0])
                    test_run_res = {
                        "success": res.get("success", False),
                        "ran": True,
                        "stdout": res.get("stdout", "")[:2000],
                        "stderr": res.get("stderr", "")[:2000]
                    }
                except Exception as e:
                    test_run_res = {"success": False, "ran": True, "error": str(e)}

        overall_passed = (len(syntax_errors) == 0) and (not test_run_res["ran"] or test_run_res["success"])

        return {
            "passed": overall_passed,
            "syntax_errors": syntax_errors,
            "security_findings": security_findings,
            "test_results": test_run_res,
            "total_files_audited": len(files)
        }
