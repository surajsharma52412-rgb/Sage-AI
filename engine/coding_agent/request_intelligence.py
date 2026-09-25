"""
Request Intelligence Engine for SAGE Autonomous Coding Agent.
Implements Sections 3, 4, and 5 of the Ultimate Master Architecture:
- Intent, Scope, and Complexity Classification (TRIVIAL, SMALL, MEDIUM, LARGE, COMPLEX, ENTERPRISE)
- Project Mode Classification (NEW_PROJECT, MODIFY_EXISTING, DEBUG_EXISTING, REFACTOR_EXISTING)
- Risk & Destructive Action Assessment
- Structured Requirements Extraction (Functional, Non-Functional, Technical, UI, Backend, DB, Security, Testing, Deployment, Performance, Accessibility, Animation)
- Ambiguity Engine (Safe Assumption vs Non-Critical vs Critical Ambiguity with Minimal Clarification Question)
"""
import re
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Set


class ComplexityLevel(str, Enum):
    TRIVIAL = "TRIVIAL"          # 1-file snippet or one-line tweak
    SMALL = "SMALL"              # Small utility or single component
    MEDIUM = "MEDIUM"            # Standard feature, API endpoint, or multi-component view
    LARGE = "LARGE"              # Full-stack module with backend, frontend, and tests
    COMPLEX = "COMPLEX"          # Multi-service application with DB, auth, and state management
    ENTERPRISE = "ENTERPRISE"    # Scalable production system with CI/CD, security compliance, and caching


class ProjectMode(str, Enum):
    NEW_PROJECT = "NEW_PROJECT"
    MODIFY_EXISTING = "MODIFY_EXISTING"
    DEBUG_EXISTING = "DEBUG_EXISTING"
    REFACTOR_EXISTING = "REFACTOR_EXISTING"


class AmbiguityLevel(str, Enum):
    SAFE_ASSUMPTION = "SAFE_ASSUMPTION"      # Clear intent, default to best engineering standard
    NON_CRITICAL = "NON_CRITICAL"            # Some design freedom, choose modern default
    CRITICAL = "CRITICAL"                    # Missing fundamental requirement that cannot be assumed


@dataclass
class RiskAssessment:
    """Evaluates risks and potential destructive impact of a request."""
    has_destructive_ops: bool = False
    destructive_reason: Optional[str] = None
    security_risks: List[str] = field(default_factory=list)
    data_loss_risk: bool = False
    requires_approval: bool = False
    approval_prompt: Optional[str] = None


@dataclass
class StructuredRequirements:
    """Structured engineering requirements converted from natural language."""
    functional: List[str] = field(default_factory=list)
    non_functional: List[str] = field(default_factory=list)
    technical: List[str] = field(default_factory=list)
    ui: List[str] = field(default_factory=list)
    backend: List[str] = field(default_factory=list)
    database: List[str] = field(default_factory=list)
    security: List[str] = field(default_factory=list)
    testing: List[str] = field(default_factory=list)
    deployment: List[str] = field(default_factory=list)
    performance: List[str] = field(default_factory=list)
    accessibility: List[str] = field(default_factory=list)
    animation: List[str] = field(default_factory=list)


@dataclass
class RequestIntelligenceReport:
    """Comprehensive output of the Request Intelligence Engine."""
    user_request: str
    intent: str
    scope: str
    complexity: ComplexityLevel
    project_mode: ProjectMode
    tech_stack: Dict[str, str]
    risk: RiskAssessment
    requirements: StructuredRequirements
    ambiguity_level: AmbiguityLevel
    clarification_question: Optional[str] = None
    has_ui: bool = False
    archetype: str = "full_stack_app"


class RequestIntelligenceEngine:
    """
    Analyzes user requests before sending to any coding model.
    Transforms raw user intent into an exhaustive, multi-dimensional engineering assessment.
    """

    DESTRUCTIVE_KEYWORDS = (
        "delete database", "drop database", "drop table", "truncate table",
        "rm -rf", "delete all", "wipe", "format disk", "git reset --hard",
        "clean -fdx", "kill -9", "purge data", "overwrite everything"
    )

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root.resolve() if workspace_root else Path.cwd().resolve()

    def analyze_request(
        self,
        user_request: str,
        workspace_context: Optional[Dict[str, Any]] = None
    ) -> RequestIntelligenceReport:
        """Runs complete multi-stage analysis pipeline on user input."""
        req_clean = user_request.strip()
        req_lower = req_clean.lower()
        words = set(re.findall(r"\b[a-z0-9_-]+\b", req_lower))

        ws_has_files = False
        ws_lang = "Python"
        if workspace_context:
            ws_has_files = bool(workspace_context.get("exists") or workspace_context.get("files"))
            ws_lang = workspace_context.get("primary_lang", "Python")

        # 1. Project Mode Determination
        mode = self._determine_project_mode(words, req_lower, ws_has_files)

        # 2. Complexity & Scope Classification
        complexity = self._classify_complexity(words, req_lower, mode)
        scope = self._describe_scope(complexity, req_lower)

        # 3. Risk Assessment
        risk = self._assess_risk(req_lower, mode)

        # 4. Tech Stack Deduction
        tech_stack, has_ui = self._deduce_tech_stack(words, req_lower, ws_lang)

        # 5. Ambiguity Engine
        ambiguity_level, clar_q = self._evaluate_ambiguity(req_clean, req_lower, words)

        # 6. Structured Requirements Extraction
        requirements = self._extract_structured_requirements(req_clean, req_lower, words, tech_stack, has_ui)

        # 7. Task Archetype
        archetype = self._determine_archetype(words, req_lower, has_ui)

        intent = f"Build and verify: {req_clean[:90]}"

        return RequestIntelligenceReport(
            user_request=req_clean,
            intent=intent,
            scope=scope,
            complexity=complexity,
            project_mode=mode,
            tech_stack=tech_stack,
            risk=risk,
            requirements=requirements,
            ambiguity_level=ambiguity_level,
            clarification_question=clar_q,
            has_ui=has_ui,
            archetype=archetype
        )

    def _determine_project_mode(self, words: Set[str], req_lower: str, ws_has_files: bool) -> ProjectMode:
        if any(w in words for w in ("fix", "debug", "error", "traceback", "bug", "crash", "broken", "failing")):
            return ProjectMode.DEBUG_EXISTING
        if any(w in words for w in ("refactor", "restructure", "clean", "rewrite", "modularize", "reorganize")):
            return ProjectMode.REFACTOR_EXISTING
        if any(w in words for w in ("add", "update", "modify", "integrate", "extend", "enhance")) and ws_has_files:
            return ProjectMode.MODIFY_EXISTING
        if not ws_has_files or any(w in words for w in ("create", "build", "new", "scaffold", "init", "from scratch")):
            return ProjectMode.NEW_PROJECT
        return ProjectMode.MODIFY_EXISTING

    def _classify_complexity(self, words: Set[str], req_lower: str, mode: ProjectMode) -> ComplexityLevel:
        # Check Trivial
        if len(words) <= 5 and any(w in words for w in ("calc", "format", "sort", "reverse", "snippet", "helper")):
            return ComplexityLevel.TRIVIAL

        # Check Enterprise / Complex
        if any(w in words for w in ("microservice", "kubernetes", "distributed", "cluster", "enterprise", "multi-tenant")):
            return ComplexityLevel.ENTERPRISE
        if any(w in words for w in ("auth", "database", "fullstack", "saas", "platform", "dashboard", "portal", "payment")):
            return ComplexityLevel.COMPLEX

        # Check Large
        if any(w in words for w in ("full", "complete", "api", "crud", "frontend", "backend", "system")):
            return ComplexityLevel.LARGE

        # Check Medium
        if any(w in words for w in ("component", "page", "table", "chart", "view", "route", "service", "widget")):
            return ComplexityLevel.MEDIUM

        # Check Small
        if any(w in words for w in ("script", "function", "utility", "tool", "parser", "validator")):
            return ComplexityLevel.SMALL

        return ComplexityLevel.MEDIUM

    def _describe_scope(self, complexity: ComplexityLevel, req_lower: str) -> str:
        descriptions = {
            ComplexityLevel.TRIVIAL: "Single-file helper or inline tweak with direct verification",
            ComplexityLevel.SMALL: "Modular utility or standalone function with unit test",
            ComplexityLevel.MEDIUM: "Feature module with component views, state, and test suites",
            ComplexityLevel.LARGE: "End-to-end full-stack solution with frontend, backend, APIs, and tests",
            ComplexityLevel.COMPLEX: "Multi-layered application with persistent database, auth, UI design, and animations",
            ComplexityLevel.ENTERPRISE: "High-resilience enterprise architecture with complete security, caching, and CI/CD"
        }
        return descriptions.get(complexity, "Standard production feature implementation")

    def _assess_risk(self, req_lower: str, mode: ProjectMode) -> RiskAssessment:
        for pattern in self.DESTRUCTIVE_KEYWORDS:
            if pattern in req_lower:
                return RiskAssessment(
                    has_destructive_ops=True,
                    destructive_reason=f"Detected potentially destructive phrase: '{pattern}'",
                    security_risks=["Potential irreversible loss of database tables or filesystem assets"],
                    data_loss_risk=True,
                    requires_approval=True,
                    approval_prompt=f"The requested operation contains '{pattern}'. Do you confirm this destructive operation?"
                )

        security_risks = []
        if "auth" in req_lower or "password" in req_lower or "token" in req_lower:
            security_risks.append("Credential and secret management must strictly use environment variables (.env)")
        if "sql" in req_lower or "query" in req_lower:
            security_risks.append("SQL parameterization required to eliminate SQL injection vulnerabilities")
        if "html" in req_lower or "input" in req_lower:
            security_risks.append("Input sanitization required to guard against Cross-Site Scripting (XSS)")

        return RiskAssessment(
            has_destructive_ops=False,
            destructive_reason=None,
            security_risks=security_risks,
            data_loss_risk=False,
            requires_approval=False,
            approval_prompt=None
        )

    def _deduce_tech_stack(self, words: Set[str], req_lower: str, ws_lang: str) -> Tuple[Dict[str, str], bool]:
        lang = ws_lang if ws_lang != "Unknown" else "Python"
        framework = "Standard"
        runtime = "Python 3.11+"
        database = "SQLite (Zero-Config Embedded)"
        has_ui = False

        if "react" in req_lower or "next" in req_lower:
            lang = "TypeScript"
            framework = "Next.js / React"
            runtime = "Node.js 20+ (LTS)"
            has_ui = True
        elif "vue" in req_lower:
            lang = "TypeScript"
            framework = "Vue 3"
            runtime = "Node.js 20+ (LTS)"
            has_ui = True
        elif "fastapi" in req_lower:
            lang = "Python"
            framework = "FastAPI"
            runtime = "Python 3.11+ / Uvicorn"
        elif "flask" in req_lower:
            lang = "Python"
            framework = "Flask"
            runtime = "Python 3.11+"
        elif "pyside" in req_lower or "pyqt" in req_lower or "qt" in req_lower:
            lang = "Python"
            framework = "PySide6 (Qt)"
            runtime = "Python 3.11+"
            has_ui = True
        elif any(w in words for w in ("website", "web", "html", "css", "frontend", "ui", "ux", "dashboard", "interface", "fullstack", "saas", "platform", "portal", "kanban", "board", "app")):
            lang = "JavaScript / HTML5"
            framework = "Vanilla Modern Web Components & CSS"
            runtime = "Browser Modern Standards"
            has_ui = True

        if any(w in words for w in ("postgres", "postgresql")):
            database = "PostgreSQL"
        elif any(w in words for w in ("mongo", "mongodb")):
            database = "MongoDB"
        elif any(w in words for w in ("redis", "cache")):
            database = "Redis + SQLite"

        return {
            "language": lang,
            "framework": framework,
            "runtime": runtime,
            "database": database,
            "deployment": "Self-contained / Local Dev Server"
        }, has_ui

    def _evaluate_ambiguity(
        self,
        req_clean: str,
        req_lower: str,
        words: Set[str]
    ) -> Tuple[AmbiguityLevel, Optional[str]]:
        # Critical ambiguity: empty or unintelligible input
        if len(req_clean) <= 3 and not req_clean.isalnum():
            return AmbiguityLevel.CRITICAL, "Could you specify what feature or application you would like to build?"

        # Critical ambiguity: payment system with zero details
        if "payment" in words and not any(w in words for w in ("stripe", "razorpay", "paypal", "dummy", "mock", "test")):
            if len(req_clean.split()) <= 4:
                return AmbiguityLevel.CRITICAL, "Which payment provider would you prefer (e.g. Stripe, Razorpay, or simulated mock payment)?"

        # Non-critical ambiguity: generic dashboard / website
        if any(w in words for w in ("dashboard", "website", "app", "portal", "system")):
            return AmbiguityLevel.NON_CRITICAL, None

        # Safe assumption
        return AmbiguityLevel.SAFE_ASSUMPTION, None

    def _extract_structured_requirements(
        self,
        req_clean: str,
        req_lower: str,
        words: Set[str],
        tech_stack: Dict[str, str],
        has_ui: bool
    ) -> StructuredRequirements:
        functional = [
            f"Implement primary objective: {req_clean}",
            "Validate all inputs and return clear, descriptive status or error messages",
            "Maintain complete state consistency without data degradation or deadlocks"
        ]

        non_functional = [
            "Maintain zero-dependency footprint where standard library suffices",
            "Ensure low execution latency with responsive non-blocking operations",
            "Enforce strict modular separation between presentation, logic, and data layers"
        ]

        technical = [
            f"Language: {tech_stack.get('language')}",
            f"Framework: {tech_stack.get('framework')}",
            f"Runtime: {tech_stack.get('runtime')}"
        ]

        ui_reqs = []
        anim_reqs = []
        if has_ui:
            ui_reqs = [
                "Modern, high-contrast visual design with curated color harmony and glassmorphic cards",
                "Responsive layout adapting seamlessly across mobile (<640px), tablet, and desktop viewports",
                "Explicit visual feedback for default, hover, focus-visible, active, loading, and disabled states",
                "Accessible semantic HTML elements with descriptive labels and ARIA attributes"
            ]
            anim_reqs = [
                "Fast micro-interactions for button clicks and hover states (120ms - 180ms)",
                "Medium transitions for component entrances, cards, and modal backdrops (200ms - 280ms)",
                "Slow transitions for page switches and view changes (300ms - 400ms)",
                "Cubic-bezier(0.16, 1, 0.3, 1) out-expo easing curve across all transitions",
                "Full compliance with @media (prefers-reduced-motion: reduce) by zeroing transition durations"
            ]

        backend = [
            "Clean service and controller separation with uniform structured JSON/data responses",
            "Robust exception handling with sanitized error output (never leak stack traces to client)"
        ]

        database = [
            f"Schema storage engine: {tech_stack.get('database')}",
            "Idempotent database migrations or schema table initialization on startup"
        ]

        security = [
            "No hardcoded API keys, tokens, or credentials in source code",
            "Environment configuration (.env) for all external endpoints and secrets",
            "Input sanitization and parameter binding to prevent injection attacks"
        ]

        testing = [
            "Automated unit test coverage verifying core functional paths",
            "Edge-case tests covering empty states, invalid inputs, and network/timeout failures",
            "Smart test validation guaranteeing 100% pass rate before delivery"
        ]

        deployment = [
            "Zero-friction local execution (e.g. single command dev server or runnable script)",
            "Detailed README with step-by-step installation, test, and run instructions"
        ]

        performance = [
            "Sub-second initial render / execution for local workflows",
            "Optimized payload sizes with minimal redundant computation and lazy-loading where appropriate"
        ]

        accessibility = [
            "WCAG 2.1 AA compliant contrast ratios for all textual elements",
            "Full keyboard navigability with visible focus indicators"
        ]

        return StructuredRequirements(
            functional=functional,
            non_functional=non_functional,
            technical=technical,
            ui=ui_reqs,
            backend=backend,
            database=database,
            security=security,
            testing=testing,
            deployment=deployment,
            performance=performance,
            accessibility=accessibility,
            animation=anim_reqs
        )

    def _determine_archetype(self, words: Set[str], req_lower: str, has_ui: bool) -> str:
        if any(w in words for w in ("fix", "bug", "error", "traceback", "debug", "crash")):
            return "debugging"
        if any(w in words for w in ("architect", "schema", "design", "structure")):
            return "architecture"
        if any(w in words for w in ("script", "snippet", "utility", "calc", "parse")) and not has_ui:
            return "simple_script"
        if any(w in words for w in ("css", "style", "animation", "ui", "ux", "theme", "button", "layout")):
            return "ui_implementation"
        if any(w in words for w in ("full", "complete", "saas", "dashboard", "portal", "platform")):
            return "complex_app"
        return "full_stack_app"
