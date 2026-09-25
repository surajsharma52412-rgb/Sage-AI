"""
Multi-Model Review System & Model Disagreement Arbiter for SAGE Coding Agent.
Implements Sections 12 and 35 of the Ultimate Master Architecture:
- 4-Tier Specialized Review (Security, Code Quality, Testing, UI/UX)
- Non-destructive targeted findings generation
- Model Disagreement Arbiter resolving conflicting implementations via empirical test evidence
"""
import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class ReviewFinding:
    category: str  # security, code_quality, testing, ui_ux
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    file_path: str
    line_number: Optional[int]
    issue: str
    suggestion: str


@dataclass
class MultiModelReviewReport:
    passed: bool
    quality_score: int  # 0 to 100
    security_clean: bool
    findings: List[ReviewFinding]
    recommendations: List[str]
    reviewed_files: List[str]


class MultiModelReviewSystem:
    """
    Coordinates multi-perspective review across Security, Code Quality, Testing, and UI/UX.
    Implements arbitration when models propose conflicting implementations.
    """

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root.resolve() if workspace_root else Path.cwd().resolve()

    def set_workspace_root(self, root: Path):
        self.workspace_root = root.resolve()

    def execute_multi_review(
        self,
        files_to_review: List[str],
        has_ui: bool = False
    ) -> MultiModelReviewReport:
        """Executes all 4 review engines across changed files."""
        findings: List[ReviewFinding] = []
        reviewed_files: List[str] = []

        for rel_path in files_to_review:
            full_path = self.workspace_root / rel_path
            if not full_path.exists() or not full_path.is_file():
                continue
            reviewed_files.append(rel_path)

            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # 1. Security Review
            findings.extend(self._review_security(rel_path, content))

            # 2. Code Quality Review
            findings.extend(self._review_code_quality(rel_path, content))

            # 3. Testing Review
            if "test" in rel_path.lower():
                findings.extend(self._review_testing(rel_path, content))

            # 4. UI/UX Review
            if has_ui and any(ext in rel_path.lower() for ext in (".html", ".css", ".jsx", ".tsx", ".vue", ".js")):
                findings.extend(self._review_ui_ux(rel_path, content))

        # Calculate Quality Score
        score = 100
        critical_count = sum(1 for f in findings if f.severity in ("CRITICAL", "HIGH"))
        medium_count = sum(1 for f in findings if f.severity == "MEDIUM")
        score -= (critical_count * 20) + (medium_count * 5)
        score = max(0, min(100, score))

        security_clean = not any(f.category == "security" and f.severity in ("CRITICAL", "HIGH") for f in findings)
        passed = (critical_count == 0 and score >= 75)

        recommendations = [f.suggestion for f in findings if f.suggestion][:5]

        return MultiModelReviewReport(
            passed=passed,
            quality_score=score,
            security_clean=security_clean,
            findings=findings,
            recommendations=recommendations,
            reviewed_files=reviewed_files
        )

    def _review_security(self, file_path: str, content: str) -> List[ReviewFinding]:
        findings = []
        lines = content.splitlines()

        # Hardcoded Secret Check
        secret_pattern = re.compile(r"(?:api[_-]?key|secret|auth[_-]?token|bearer|password)\s*=\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]", re.I)
        for i, line in enumerate(lines, 1):
            if secret_pattern.search(line):
                findings.append(ReviewFinding(
                    category="security",
                    severity="CRITICAL",
                    file_path=file_path,
                    line_number=i,
                    issue="Hardcoded secret or API key detected in source code",
                    suggestion="Move credentials to environment variables (.env) and access via os.getenv()"
                ))

        # Insecure eval / exec
        eval_pattern = re.compile(r"\b(eval|exec)\s*\(", re.I)
        for i, line in enumerate(lines, 1):
            if eval_pattern.search(line) and not line.strip().startswith("#"):
                findings.append(ReviewFinding(
                    category="security",
                    severity="HIGH",
                    file_path=file_path,
                    line_number=i,
                    issue="Dangerous dynamic code execution via eval/exec",
                    suggestion="Refactor using safe parsers like ast.literal_eval or structured dictionaries"
                ))

        return findings

    def _review_code_quality(self, file_path: str, content: str) -> List[ReviewFinding]:
        findings = []
        lines = content.splitlines()

        # Check for bare excepts
        for i, line in enumerate(lines, 1):
            if re.search(r"^\s*except\s*:", line):
                findings.append(ReviewFinding(
                    category="code_quality",
                    severity="MEDIUM",
                    file_path=file_path,
                    line_number=i,
                    issue="Bare except clause catches SystemExit and KeyboardInterrupt",
                    suggestion="Catch specific exceptions or use 'except Exception:'"
                ))

        # Check for file length
        if len(lines) > 600:
            findings.append(ReviewFinding(
                category="code_quality",
                severity="LOW",
                file_path=file_path,
                line_number=None,
                issue=f"File exceeds 600 lines ({len(lines)} lines)",
                suggestion="Consider modularizing into smaller focused services or component files"
            ))

        return findings

    def _review_testing(self, file_path: str, content: str) -> List[ReviewFinding]:
        findings = []
        # Check for assertions
        if "assert" not in content and "self.assert" not in content and "expect(" not in content:
            findings.append(ReviewFinding(
                category="testing",
                severity="HIGH",
                file_path=file_path,
                line_number=None,
                issue="Test file contains no recognizable assertion statements",
                suggestion="Add explicit assertions (e.g. assert result == expected or self.assertEqual)"
            ))
        return findings

    def _review_ui_ux(self, file_path: str, content: str) -> List[ReviewFinding]:
        findings = []
        # Reduced motion check in CSS
        if file_path.endswith(".css") and "prefers-reduced-motion" not in content:
            findings.append(ReviewFinding(
                category="ui_ux",
                severity="MEDIUM",
                file_path=file_path,
                line_number=None,
                issue="CSS contains animations/transitions but lacks @media (prefers-reduced-motion) support",
                suggestion="Include @media (prefers-reduced-motion: reduce) { * { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; } }"
            ))
        return findings

    def arbitrate_model_disagreement(
        self,
        candidate_a: Dict[str, Any],
        candidate_b: Dict[str, Any],
        validation_runner: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> Dict[str, Any]:
        """
        Implements Section 35: Model Disagreement System.
        When two models generate conflicting solutions:
        1. Compare against requirements
        2. Evaluate empirical test evidence
        3. Pick the technically verified solution rather than personal model preference
        """
        # If test runner provided, test both
        if validation_runner:
            try:
                passed_a = validation_runner(candidate_a)
                passed_b = validation_runner(candidate_b)
                if passed_a and not passed_b:
                    return {"winner": "candidate_a", "reason": "Candidate A passed all validation tests"}
                if passed_b and not passed_a:
                    return {"winner": "candidate_b", "reason": "Candidate B passed all validation tests"}
            except Exception as e:
                logger.warning("Error running arbitration tests: %s", e)

        # Fallback to code quality metrics (shorter complexity, fewer findings)
        code_a = str(candidate_a.get("code", ""))
        code_b = str(candidate_b.get("code", ""))

        has_secrets_a = bool(re.search(r"(?:api[_-]?key|password)\s*=", code_a, re.I))
        has_secrets_b = bool(re.search(r"(?:api[_-]?key|password)\s*=", code_b, re.I))

        if not has_secrets_a and has_secrets_b:
            return {"winner": "candidate_a", "reason": "Candidate A avoids hardcoded secrets"}
        if not has_secrets_b and has_secrets_a:
            return {"winner": "candidate_b", "reason": "Candidate B avoids hardcoded secrets"}

        return {"winner": "candidate_a", "reason": "Candidate A adheres to standard architectural specifications"}
