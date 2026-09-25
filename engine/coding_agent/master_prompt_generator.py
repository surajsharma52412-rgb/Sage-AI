"""
Automatic Master Coding Prompt Generator for SAGE Coding Agent.
Implements Sections 1, 2, 8, 37, and 38 of the Ultimate Master Architecture:
- Never sends raw user requests to coding models
- Synthesizes exhaustive 20-point Master Engineering Specification (Section 8)
- Generates structured Coding Model Implementation Prompts (Section 38)
- Categorizes Continuous Project Improvements into Required, Recommended, Optional, Future (Section 37)
- Maintains full backwards compatibility with Phase 1 pipeline.
"""
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from .request_intelligence import (
    RequestIntelligenceEngine,
    RequestIntelligenceReport,
    AmbiguityLevel,
    ComplexityLevel,
    ProjectMode
)
from .project_memory import ProjectMemoryManager


@dataclass
class MasterPromptResult:
    """Structured result from the Master Prompt Generator."""
    master_prompt: str
    user_objective: str
    app_type: str
    tech_stack: Dict[str, str]
    file_structure: List[str]
    has_ui: bool
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    task_classification: str = "full_stack_app"
    complexity: str = "MEDIUM"
    project_mode: str = "NEW_PROJECT"
    engineering_spec: str = ""
    coding_model_prompt: str = ""
    improvements: Dict[str, List[str]] = field(default_factory=dict)


class MasterPromptGenerator:
    """
    Automatic Master Coding Prompt Generator & Engineering Specification Synthesizer.
    Converts simple user requests into production-grade engineering specifications.
    """

    ANIMATION_SYSTEM_SPEC = """
ANIMATION SYSTEM SPECIFICATION (REQUIRED):
- Architecture: Reusable system-wide motion tokens rather than ad-hoc CSS transitions.
- Motion Tokens:
  * Fast (micro-interactions, button clicks, hover feedback): 120ms - 180ms
  * Medium (cards, dropdowns, tooltips, list item entrances): 200ms - 280ms
  * Slow (page transitions, modal backdrops, full view switches): 300ms - 400ms
  * Default Easing Curve: cubic-bezier(0.16, 1, 0.3, 1) [out-expo/out-cubic]
- Compulsory Animated Interactions:
  1. Page/View Transitions: Smooth cross-fade with subtle parallax slide-in (240ms).
  2. Component Entrances: Opacity 0 -> 1 with translateY(+8px -> 0px) staggered cascade.
  3. Interactive Elements: Hover elevation, active click compression scale(0.97).
  4. Loading States: Continuous skeleton shimmer waves, spinning indicators.
  5. Feedback/Toasts: Slide-down entrance, pulsing border glow, auto-dismiss exit.
- Accessibility Guarantee:
  Must include `@media (prefers-reduced-motion: reduce)` block that sets animation-duration: 0.01ms
  and transition-duration: 0.01ms for users requesting reduced motion.
"""

    UI_UX_SPEC = """
UI/UX DESIGN SPECIFICATION:
- Aesthetics: Sleek, high-contrast, modern interface with curated color palettes.
- Typography: Clean sans-serif font stack (Inter, Roboto, system-ui) with clear visual hierarchy.
- Layout: Responsive flex/grid design with fluid breakpoints for mobile, tablet, and desktop.
- State Feedback: Explicit visual states for default, hover, active, focus-visible, loading, empty, and disabled.
- Spacing: Systematic 4px/8px rhythm with generous whitespace.
- Consistency: Unified border-radius, elevation drop-shadows, and glassmorphic card containers.
"""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root.resolve() if workspace_root else Path.cwd().resolve()
        self.request_intelligence = RequestIntelligenceEngine(self.workspace_root)
        self.project_memory = ProjectMemoryManager(self.workspace_root)

    def set_workspace_root(self, root: Path):
        self.workspace_root = root.resolve()
        self.request_intelligence.workspace_root = self.workspace_root
        self.project_memory.set_workspace_root(self.workspace_root)

    def analyze_intent(self, user_request: str) -> Dict[str, Any]:
        """Backwards-compatible helper for analyzing intent."""
        intel = self.request_intelligence.analyze_request(user_request)
        return {
            "classification": intel.archetype,
            "has_ui": intel.has_ui,
            "detected_lang": intel.tech_stack.get("language", "Python"),
            "detected_framework": intel.tech_stack.get("framework", "Standard"),
            "complexity": intel.complexity.value,
            "project_mode": intel.project_mode.value
        }

    def check_for_critical_ambiguity(self, user_request: str) -> Tuple[bool, Optional[str]]:
        """Backwards-compatible helper for minimal ambiguity checking."""
        intel = self.request_intelligence.analyze_request(user_request)
        is_ambiguous = (intel.ambiguity_level == AmbiguityLevel.CRITICAL)
        return is_ambiguous, intel.clarification_question

    def inspect_workspace_context(self) -> Dict[str, Any]:
        """Gathers context about existing project structure, dependencies, and files."""
        context = {
            "exists": False,
            "files": [],
            "dependencies": [],
            "primary_lang": "Unknown",
            "has_tests": False
        }
        if not self.workspace_root.exists():
            return context

        try:
            files = []
            for p in self.workspace_root.glob("*"):
                if p.name.startswith((".", "node_modules", "venv", "__pycache__")):
                    continue
                files.append(p.name + ("/" if p.is_dir() else ""))
            context["files"] = files[:20]
            context["exists"] = len(files) > 0

            # Check config files
            if (self.workspace_root / "package.json").exists():
                context["primary_lang"] = "JavaScript/TypeScript"
            elif (self.workspace_root / "requirements.txt").exists() or (self.workspace_root / "pyproject.toml").exists():
                context["primary_lang"] = "Python"

            # Check tests
            context["has_tests"] = (self.workspace_root / "tests").exists() or any("test" in f.lower() for f in files)
        except Exception:
            pass

        return context

    def generate_master_prompt(
        self,
        user_request: str,
        project_map: Optional[Dict[str, Any]] = None
    ) -> MasterPromptResult:
        """
        Transforms the natural language user request into the complete
        Master Engineering Specification and Section 38 Coding Model Prompt.
        """
        # Step 1: Deep Request Intelligence Analysis
        ws_context = self.inspect_workspace_context()
        intel = self.request_intelligence.analyze_request(user_request, ws_context)

        # Step 2: Critical Ambiguity Gate
        if intel.ambiguity_level == AmbiguityLevel.CRITICAL:
            return MasterPromptResult(
                master_prompt="",
                user_objective=user_request,
                app_type="Ambiguous",
                tech_stack={},
                file_structure=[],
                has_ui=False,
                needs_clarification=True,
                clarification_question=intel.clarification_question
            )

        # Select stack
        primary_lang = intel.tech_stack.get("language", "Python")
        if ws_context["primary_lang"] != "Unknown" and intel.archetype != "simple_script":
            primary_lang = ws_context["primary_lang"]

        framework = intel.tech_stack.get("framework", "Standard")
        has_ui = intel.has_ui

        # Default file structure
        if "python" in primary_lang.lower():
            file_tree = [
                "src/",
                "  ├── __init__.py",
                "  ├── main.py",
                "  ├── models.py",
                "  ├── services/",
                "  └── utils/",
                "tests/",
                "  └── test_main.py",
                "requirements.txt",
                "README.md"
            ]
        else:
            file_tree = [
                "src/",
                "  ├── components/",
                "  ├── services/",
                "  ├── styles/",
                "  ├── index.html",
                "  ├── app.js",
                "  └── index.css",
                "tests/",
                "package.json",
                "README.md"
            ]

        # Update Project Memory
        self.project_memory.update_tech_stack({"language": primary_lang, "framework": framework})

        # Step 3: Synthesize 20-Point Master Engineering Specification (Section 8)
        engineering_spec = self._synthesize_engineering_spec(
            user_request=user_request,
            intel=intel,
            primary_lang=primary_lang,
            framework=framework,
            file_tree=file_tree,
            ws_context=ws_context
        )

        # Step 4: Synthesize Section 38 Coding Model Prompt
        coding_model_prompt = self._synthesize_coding_model_prompt(
            user_request=user_request,
            intel=intel,
            primary_lang=primary_lang,
            framework=framework,
            file_tree=file_tree,
            ws_context=ws_context
        )

        # Step 5: Continuous Project Improvements (Section 37)
        improvements = self._categorize_improvements(intel, has_ui)

        return MasterPromptResult(
            master_prompt=engineering_spec,
            user_objective=user_request,
            app_type=intel.archetype,
            tech_stack={"language": primary_lang, "framework": framework},
            file_structure=file_tree,
            has_ui=has_ui,
            needs_clarification=False,
            task_classification=intel.archetype,
            complexity=intel.complexity.value,
            project_mode=intel.project_mode.value,
            engineering_spec=engineering_spec,
            coding_model_prompt=coding_model_prompt,
            improvements=improvements
        )

    def _synthesize_engineering_spec(
        self,
        user_request: str,
        intel: RequestIntelligenceReport,
        primary_lang: str,
        framework: str,
        file_tree: List[str],
        ws_context: Dict[str, Any]
    ) -> str:
        """Synthesizes the complete 20-section Master Engineering Specification (Section 8)."""
        functional_lines = "\n".join(f"- {f}" for f in intel.requirements.functional)
        non_functional_lines = "\n".join(f"- {nf}" for nf in intel.requirements.non_functional)

        spec = f"""================================================================================
MASTER ENGINEERING SPECIFICATION — AUTONOMOUS SOFTWARE SYSTEM
================================================================================

SYSTEM ROLE:
You are an expert software engineer and autonomous coding agent orchestrator.
Your mandate is to convert this engineering specification into a complete, clean,
verified, and runnable production implementation.

1. PROJECT OBJECTIVE:
PROJECT:
Autonomous Software Implementation: {user_request[:90]}
Scope: {intel.scope} | Complexity: {intel.complexity.value} | Mode: {intel.project_mode.value}

2. USER GOAL:
USER OBJECTIVE:
{user_request.strip()}

REQUIREMENTS:
3. FUNCTIONAL REQUIREMENTS:
{functional_lines}

4. NON-FUNCTIONAL REQUIREMENTS:
{non_functional_lines}
- Strict performance: Non-blocking async IO and responsive sub-second feedback.
- Reliability: Self-healing error boundaries and zero-degradation fallback paths.

5. TECH STACK:
- Primary Language: {primary_lang}
- Primary Framework: {framework}
- Runtime: {intel.tech_stack.get('runtime', 'Standard')}
- Database: {intel.tech_stack.get('database', 'SQLite (Zero-Config Embedded)')}
- Styling: Modern CSS Tokens / Glassmorphic dark palette

6. ARCHITECTURE:
SYSTEM ARCHITECTURE:
- Modular Layered Pipeline: Presentation -> Domain Business Logic -> Storage & IO.
- Separation of Concerns: Clear boundary between user interface, routing, and data models.
- Immutable state flows with explicit event emitters.

7. APPLICATION FLOW:
User Input -> Validation Gate -> Controller / Service Layer -> State Store -> UI Response.

8. DATA FLOW:
Client Action -> Typed Request Payload -> Sanitizer -> Core Domain Service -> Storage -> Synchronized State.

9. COMPONENT ARCHITECTURE:
- Independent, decoupled components with single responsibility.
- Unified theme context with reusable design tokens.

PROJECT STRUCTURE:
{chr(10).join(file_tree)}

10. DATABASE REQUIREMENTS:
DATABASE DESIGN:
- Zero-leak relational tables or JSON store with indexed primary keys.
- Idempotent schema migrations and initialization on boot.

11. API REQUIREMENTS:
API DESIGN:
- Uniform REST / Service Envelope: {{ "success": bool, "data": Any, "error": Optional[str] }}.
- Semantic status codes and complete parameter validation.

BACKEND REQUIREMENTS:
- Clean API endpoints / controllers with typed schemas.
- Input validation on all incoming request parameters.
- Robust exception handling returning standard structured error payloads.

12. SECURITY REQUIREMENTS:
SECURITY MODEL:
- Zero Hardcoded Secrets: All keys strictly resolved via environment variables.
- Full sanitization preventing SQL Injection, XSS, and shell execution traversal.

13. ERROR HANDLING:
- User-friendly messages concealing internal tracebacks.
- Structured logging with DEBUG, INFO, WARNING, ERROR levels.

14. UI/UX SYSTEM:
UI/UX REQUIREMENTS:
{self.UI_UX_SPEC}

15. ANIMATION SYSTEM:
ANIMATION REQUIREMENTS:
{self.ANIMATION_SYSTEM_SPEC}

16. ACCESSIBILITY:
- WCAG 2.1 AA compliant contrast.
- Full keyboard focus-visible rings and screen-reader accessible attributes.

17. PERFORMANCE:
- Minimal payload footprint with lazy-loaded modules.
- Zero memory leaks, unbounded cache growths, or redundant re-renders.

18. TESTING REQUIREMENTS:
TESTING STRATEGY:
- Unit tests covering 100% of core domain logic.
- Integration tests validating component wiring and error handling.
- Smart Test Selection with zero regressions.

19. DEPLOYMENT STRATEGY:
- Single-command local startup script or standard entry point.
- Comprehensive documentation and environment instructions.

EXISTING PROJECT CONTEXT:
- Workspace: {self.workspace_root}
- Existing Files Detected: {', '.join(ws_context['files']) if ws_context['files'] else 'Clean project environment'}
- Existing Framework Detected: {ws_context['primary_lang']}
- Existing Functionality: Preserved without unintended breaking modifications.

IMPLEMENTATION PLAN:
1. Initialize project scaffold and dependency manifests.
2. Build core data structures and business logic services.
3. Construct UI components and integrate reusable animation system.
4. Implement error boundaries and logging infrastructure.
5. Write and execute automated unit tests.
6. Verify visual and functional completion criteria.

QUALITY REQUIREMENTS:
- Modular, readable, well-commented code following idiomatic standards.
- Static type annotations where supported by the language.
- Zero dead code or unreferenced dependencies.

20. ACCEPTANCE CRITERIA:
FINAL VERIFICATION CHECKLIST:
[ ] All user requirements implemented in full without mock placeholders.
[ ] UI is modern, polished, responsive, and animated.
[ ] Animation system respects prefers-reduced-motion.
[ ] Automated tests pass with 0 errors.
[ ] Zero hardcoded credentials or API keys.
[ ] Application launches cleanly without runtime exceptions.
[ ] Documentation updated with setup and usage instructions.

IMPORTANT RULES:
- Do not invent missing critical requirements.
- Ask the user only when essential information is genuinely missing.
- Preserve existing functionality.
- Do not expose secrets.
- Do not claim completion without verification.
- Implement the requested functionality completely.
- Make the UI polished and responsive.
- Add meaningful animations throughout the UI.
- Respect reduced-motion preferences.
================================================================================
"""
        return spec.strip()

    def _synthesize_coding_model_prompt(
        self,
        user_request: str,
        intel: RequestIntelligenceReport,
        primary_lang: str,
        framework: str,
        file_tree: List[str],
        ws_context: Dict[str, Any]
    ) -> str:
        """Synthesizes the Section 38 prompt sent to implementation coding models."""
        files_str = "\n".join(f"- {f}" for f in file_tree[:8])
        memory_summary = self.project_memory.build_compressed_context(user_request)

        prompt = f"""You are the implementation engineer for this project.

PROJECT OBJECTIVE:
{user_request[:100]}

USER REQUIREMENT:
{user_request.strip()}

CURRENT PROJECT:
{memory_summary}

ARCHITECTURE:
Modular layered architecture (Presentation -> Service Layer -> Data Models).

TECH STACK:
Language: {primary_lang} | Framework: {framework} | Runtime: {intel.tech_stack.get('runtime', 'Standard')}

FILES RELEVANT TO THIS TASK:
{files_str}

REQUIREMENTS:
1. Implement the user objective completely without omissions.
2. Build modular, production-ready code with comprehensive error handling.
3. If UI is involved, make it responsive, modern, and animated.

IMPLEMENTATION PLAN:
1. Scaffold components and services.
2. Implement core logic and data models.
3. Connect UI and motion tokens (respecting prefers-reduced-motion).
4. Write and run automated unit tests.
5. Verify zero errors.

UI/UX REQUIREMENTS:
{self.UI_UX_SPEC}

ANIMATION REQUIREMENTS:
{self.ANIMATION_SYSTEM_SPEC}

SECURITY REQUIREMENTS:
- Zero hardcoded secrets (use .env / environment variables).
- Parameterized queries to prevent SQL injection.
- Sanitize inputs to prevent XSS.

TESTING REQUIREMENTS:
- Generate automated unit tests.
- Verify 100% test pass rate before reporting completion.

ACCEPTANCE CRITERIA:
- Verified implementation running cleanly with zero runtime exceptions.
- All functional paths tested and passing.

CONSTRAINTS:
- Do not invent non-requested dependencies.
- Preserve existing working code.

IMPLEMENTATION RULES:
1. Preserve existing functionality.
2. Do not invent critical requirements.
3. Do not expose secrets.
4. Follow the existing project architecture.
5. Write production-quality code.
6. Handle errors properly.
7. Test your implementation.
8. Fix discovered errors.
9. Do not claim success without verification.
10. Keep the implementation modular.
11. Make UI responsive.
12. Implement meaningful animations.
13. Respect reduced-motion preferences.
14. Update documentation where necessary.

YOUR TASK:
Implement the requested functionality completely.

After implementation:
- run appropriate tests
- inspect for errors
- fix failures
- verify requirements
- report the actual implementation status.
"""
        return prompt.strip()

    def _categorize_improvements(
        self,
        intel: RequestIntelligenceReport,
        has_ui: bool
    ) -> Dict[str, List[str]]:
        """Implements Section 37: Continuous Project Improvement."""
        required = [
            f"Implement core functionality: {intel.user_request[:50]}",
            "Pass all automated unit tests",
            "Verify zero syntax or runtime errors"
        ]

        recommended = [
            "Add automated integration tests for edge cases",
            "Configure environment variable template (.env.example)"
        ]

        optional = [
            "Add localized multi-language string tables",
            "Implement client-side caching for offline resilience"
        ]

        future = [
            "Setup CI/CD pipeline automation with GitHub Actions",
            "Implement telemetry logging and error reporting"
        ]

        if has_ui:
            recommended.append("Implement smooth skeleton shimmers for asynchronous loading states")
            optional.append("Add light/dark theme toggle with persistent user preference")

        return {
            "Required": required,
            "Recommended": recommended,
            "Optional": optional,
            "Future": future
        }
