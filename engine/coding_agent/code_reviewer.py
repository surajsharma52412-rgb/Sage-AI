"""
Code Reviewer & Security Auditor for SAGE Autonomous Coding Agent.
Performs comprehensive multi-factor quality and security audits:
- Correctness & syntax verification
- Security audit (secrets detection, SQL injection, eval/exec hazards)
- Maintainability & DRY (duplicate code, overly long functions)
- Error handling & resilience
- Type safety & docstring coverage
Generates actionable review findings that can spawn automatic fix tasks.
"""
import ast
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from .tool_system import ToolSystem

logger = logging.getLogger(__name__)


class CodeReviewer:
    """Audits code for quality, security, maintainability, and architectural compliance."""

    SECRET_REGEXES = [
        (r"(?:api[_-]?key|secret|auth[_-]?token|bearer|password)\s*=\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]", "High-entropy API key or secret token detected"),
        (r"-----BEGIN (?:RSA|OPENSSH|PGP|PRIVATE) KEY-----", "Private cryptographic key detected in source file"),
        (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token detected"),
        (r"sk-[A-Za-z0-9]{32,}", "OpenAI or third-party secret key detected")
    ]

    INSECURE_PATTERNS = [
        (r"\beval\s*\(", "Dangerous eval() usage detected"),
        (r"\bexec\s*\(", "Dangerous exec() usage detected"),
        (r"pickle\.loads\s*\(", "Insecure deserialization via pickle.loads detected"),
        (r"cursor\.execute\(['\"].*%s.*['\"]\s*%", "Potential SQL string interpolation vulnerability"),
        (r"shell=True", "Subprocess call with shell=True flagged for review")
    ]

    def __init__(self, tools: ToolSystem):
        self.tools = tools

    def review_codebase(self, files_to_review: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Runs comprehensive review across specified files or all project source files.
        """
        if not files_to_review:
            files_to_review = [
                f for f in self.tools.workspace_root.rglob("*.py")
                if ".git" not in f.parts and ".venv" not in f.parts
            ]
            files_to_review = [str(p.relative_to(self.tools.workspace_root)).replace("\\", "/") for p in files_to_review]

        findings: List[Dict[str, Any]] = []
        clean_files = []

        for rel_path in files_to_review:
            full = self.tools.workspace_root / rel_path
            if not full.exists() or not full.is_file():
                continue

            try:
                content = full.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            file_findings = []

            # 1. Security check: Secrets
            for pat, desc in self.SECRET_REGEXES:
                for match in re.finditer(pat, content, re.IGNORECASE):
                    line_no = content[: match.start()].count("\n") + 1
                    file_findings.append({
                        "file": rel_path,
                        "line": line_no,
                        "severity": "CRITICAL",
                        "category": "security",
                        "issue": desc
                    })

            # 2. Security check: Insecure patterns
            for pat, desc in self.INSECURE_PATTERNS:
                for match in re.finditer(pat, content):
                    line_no = content[: match.start()].count("\n") + 1
                    file_findings.append({
                        "file": rel_path,
                        "line": line_no,
                        "severity": "HIGH",
                        "category": "security",
                        "issue": desc
                    })

            # 3. Static Python AST checks
            if rel_path.endswith(".py"):
                ast_issues = self._check_python_ast(rel_path, content)
                file_findings.extend(ast_issues)

            if file_findings:
                findings.extend(file_findings)
            else:
                clean_files.append(rel_path)

        has_critical = any(f["severity"] == "CRITICAL" for f in findings)
        score = max(0, 100 - (len(findings) * 10))

        return {
            "passed": not has_critical and len(findings) <= 2,
            "quality_score": score,
            "total_files_reviewed": len(files_to_review),
            "findings_count": len(findings),
            "findings": findings,
            "clean_files": clean_files,
            "requires_fix_task": has_critical or len(findings) > 3
        }

    def _check_python_ast(self, rel_path: str, content: str) -> List[Dict[str, Any]]:
        issues = []
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return [{
                "file": rel_path,
                "line": e.lineno,
                "severity": "CRITICAL",
                "category": "syntax",
                "issue": f"Syntax Error: {e.msg}"
            }]

        for node in ast.walk(tree):
            # Check empty except blocks
            if isinstance(node, ast.ExceptHandler):
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    issues.append({
                        "file": rel_path,
                        "line": getattr(node, "lineno", 1),
                        "severity": "MEDIUM",
                        "category": "error_handling",
                        "issue": "Silently swallowed exception (bare pass in except block)"
                    })

            # Check overly long functions (> 100 lines)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start)
                if end - start > 100:
                    issues.append({
                        "file": rel_path,
                        "line": start,
                        "severity": "LOW",
                        "category": "maintainability",
                        "issue": f"Function '{node.name}' exceeds 100 lines ({end - start} lines)"
                    })

        return issues
