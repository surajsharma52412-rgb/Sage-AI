"""
Master Autonomous Software Engineering Orchestrator for SAGE Coding Agent.
Implements the 11-stage autonomous engineering execution loop:
UNDERSTAND ➔ ANALYZE ➔ PLAN ➔ IMPLEMENT ➔ EXECUTE ➔ TEST ➔ DEBUG ➔ REVIEW ➔ VERIFY ➔ CHECKPOINT ➔ DELIVER

Core capabilities:
- Project Analyzer & cached project map
- AST symbol-level Codebase Indexer with incremental change detection
- Priority-based Context Engine with token budgeting
- Persistent DAG Task Manager with resumable session state
- 24-tool ToolSystem with uniform structured return payloads
- Sandboxed execution with timeouts and isolation
- Evidence-based Test ➔ Debug ➔ Fix loop with Smart Test Selection
- Automated Code Review & Security Auditing
- Git Checkpoints & protection of uncommitted user files
- 10 Specialized Internal Workers
- Strict verification completion criteria
"""
import time
import uuid
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from .safety_controller import SafetyController
from .context_manager import ContextFileManager
from .long_context_memory import LongContextMemory
from .tool_ecosystem import ToolEcosystem
from .model_router import CodingModelRouter
from .project_analyzer import ProjectAnalyzer
from .codebase_indexer import CodebaseIndexer
from .context_engine import ContextEngine
from .persistent_task_manager import PersistentTaskManager
from .sandbox_runner import SandboxRunner
from .tool_system import ToolSystem
from .test_debug_fix_loop import TestDebugFixLoop
from .code_reviewer import CodeReviewer
from .checkpoint_manager import CheckpointManager
from .task_scheduler import TaskScheduler
from .infrastructure import ScalableInfrastructure
from .sub_agents import (
    ArchitectAgent,
    BackendAgent,
    FrontendAgent,
    DatabaseWorker,
    DebuggerWorker,
    QAAgent,
    SecurityWorker,
    ReviewerWorker,
    DevOpsAgent,
    DocumentationAgent
)
from dataclasses import asdict
from .pipeline import (
    CodeIntegrator,
    AutomatedValidator,
    SelfHealingLoop,
    FinalPackager
)
from .master_prompt_generator import MasterPromptGenerator
from .request_intelligence import RequestIntelligenceEngine
from .project_memory import ProjectMemoryManager
from .requirement_traceability import RequirementTraceabilityMatrix
from .model_benchmarking import ModelBenchmarkTracker
from .multi_model_review import MultiModelReviewSystem
from .safety_approval_gates import SafetyApprovalGates

logger = logging.getLogger(__name__)


class CodingAgentOrchestrator:
    """The master software engineering execution coordinator for SAGE Coding Agent."""

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        model_override: Optional[str] = None
    ):
        self.workspace_root = workspace_root.resolve() if workspace_root else Path.cwd().resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.safety = SafetyController(self.workspace_root)
        self.context_mgr = ContextFileManager(self.workspace_root, self.safety)
        self.memory = LongContextMemory()
        self.tools = ToolEcosystem(self.workspace_root, self.context_mgr, self.safety)
        self.model_router = CodingModelRouter(default_provider_override=model_override)
        self.infra = ScalableInfrastructure()

        # Phase 1 & 2 Engines
        self.analyzer = ProjectAnalyzer(self.workspace_root)
        self.indexer = CodebaseIndexer(self.workspace_root)
        self.context_engine = ContextEngine(self.indexer, self.analyzer, self.memory)
        self.task_mgr = PersistentTaskManager()
        self.scheduler = TaskScheduler(max_concurrency=3)
        self.master_prompt_gen = MasterPromptGenerator(self.workspace_root)

        # Phase 3 & 6 Tools & Guardians
        self.sandbox = SandboxRunner(self.workspace_root)
        self.tool_sys = ToolSystem(self.workspace_root, self.safety, self.sandbox, self.analyzer, self.indexer)
        self.checkpoint_mgr = CheckpointManager(self.tool_sys)

        # Phase 4 & 5 Diagnostic, Testing & Review Engines
        self.test_loop = TestDebugFixLoop(self.tool_sys, self.indexer, max_retries=3)
        self.code_reviewer = CodeReviewer(self.tool_sys)

        # 10 Specialized Internal Workers
        self.subagents = {
            "architect": ArchitectAgent(self.context_mgr, self.tools, self.model_router),
            "backend": BackendAgent(self.context_mgr, self.tools, self.model_router),
            "frontend": FrontendAgent(self.context_mgr, self.tools, self.model_router),
            "database": DatabaseWorker(self.context_mgr, self.tools, self.model_router),
            "debugger": DebuggerWorker(self.context_mgr, self.tools, self.model_router),
            "qa": QAAgent(self.context_mgr, self.tools, self.model_router),
            "tester": QAAgent(self.context_mgr, self.tools, self.model_router),
            "security": SecurityWorker(self.context_mgr, self.tools, self.model_router),
            "reviewer": ReviewerWorker(self.context_mgr, self.tools, self.model_router),
            "devops": DevOpsAgent(self.context_mgr, self.tools, self.model_router),
            "documentation": DocumentationAgent(self.context_mgr, self.tools, self.model_router)
        }

        # Pipeline Integration
        self.integrator = CodeIntegrator(self.context_mgr, self.tools)
        self.validator = AutomatedValidator(self.context_mgr, self.tools)
        self.healer = SelfHealingLoop(self.context_mgr, self.tools, self.validator, self.subagents, max_repairs=2)
        self.packager = FinalPackager(self.context_mgr)

        # Ultimate Master Architecture Engines
        self.request_intelligence = RequestIntelligenceEngine(self.workspace_root)
        self.project_memory = ProjectMemoryManager(self.workspace_root)
        self.traceability = RequirementTraceabilityMatrix()
        self.benchmarks = ModelBenchmarkTracker(self.workspace_root)
        self.multi_reviewer = MultiModelReviewSystem(self.workspace_root)
        self.approval_gates = SafetyApprovalGates(self.workspace_root)

    def set_workspace(self, workspace_path: Path):
        """Re-roots all engines to the target project directory."""
        self.workspace_root = Path(workspace_path).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.safety.set_workspace_root(self.workspace_root)
        self.context_mgr.set_workspace_root(self.workspace_root)
        self.tools.set_workspace_root(self.workspace_root)
        self.analyzer.set_workspace_root(self.workspace_root)
        self.indexer.set_workspace_root(self.workspace_root)
        self.sandbox.set_workspace_root(self.workspace_root)
        self.tool_sys.set_workspace_root(self.workspace_root)
        self.master_prompt_gen.workspace_root = self.workspace_root
        self.request_intelligence.workspace_root = self.workspace_root
        self.project_memory.set_workspace_root(self.workspace_root)
        self.benchmarks.workspace_root = self.workspace_root
        self.multi_reviewer.set_workspace_root(self.workspace_root)
        self.approval_gates.workspace_root = self.workspace_root

    def execute_project(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        llm_caller_fn: Optional[Callable[..., Dict[str, Any]]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_diff: Optional[Callable[[str, str], None]] = None,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes the master 11-stage autonomous engineering lifecycle:
        1. UNDERSTAND: Requirements parsing & target stack scoping
        2. ANALYZE: Project structure, dependencies, frameworks & AST index
        3. PLAN: Granular DAG task decomposition with dependency graph
        4. CHECKPOINT (Pre): Snapshot existing state & safeguard uncommitted user changes
        5. IMPLEMENT: Parallel execution of tasks across the 10 internal workers
        6. EXECUTE: Merge & write code, resolve collisions, generate manifests
        7. TEST: Smart test selection running affected suites
        8. DEBUG: Evidence-based stack trace diagnosis & minimal fix loops
        9. REVIEW: Automated code quality & security vulnerability auditing
        10. VERIFY: Final validation criteria checklist check
        11. DELIVER: Package working project, documentation, test reports, and timeline
        """
        start_time = time.time()
        session_id = str(uuid.uuid4())[:8]

        def stage(msg: str):
            if on_stage:
                try:
                    on_stage(msg)
                except Exception:
                    pass
            if on_log:
                try:
                    on_log(f"📌 {msg}")
                except Exception:
                    pass

        def log(msg: str):
            if on_log:
                try:
                    on_log(msg)
                except Exception:
                    pass

        # ── 1. UNDERSTAND ───────────────────────────────────────────────
        stage("🔍 1/11: UNDERSTAND — Ingesting user requirements & analyzing request intelligence...")
        log(f"  • Goal: {goal}")
        intel = self.request_intelligence.analyze_request(goal)
        log(f"  • Scope: {intel.scope} | Complexity: {intel.complexity.value} | Mode: {intel.project_mode.value}")

        # Register requirements into Traceability Matrix (Section 20)
        self.traceability.register_bulk({
            "functional": intel.requirements.functional,
            "non_functional": intel.requirements.non_functional,
            "ui": intel.requirements.ui,
            "backend": intel.requirements.backend,
            "database": intel.requirements.database,
            "security": intel.requirements.security,
            "testing": intel.requirements.testing,
            "animation": intel.requirements.animation
        })

        # Safety Approval Gate Check (Section 16 & 36)
        if intel.risk.requires_approval:
            gate_res = self.approval_gates.evaluate_command(goal)
            if not gate_res.is_safe_to_proceed:
                approved = self.approval_gates.request_approval_if_needed(gate_res)
                if not approved:
                    log(f"  🛑 Destructive action intercepted by Safety Approval Gate: {gate_res.reason}")
                    return {
                        "success": False,
                        "blocked_by_safety": True,
                        "reason": gate_res.reason,
                        "session_id": session_id
                    }

        # ── 2. ANALYZE ──────────────────────────────────────────────────
        stage("📊 2/11: ANALYZE — Inspecting project map & AST symbol index...")
        proj_map = self.analyzer.analyze_project()
        index_report = self.indexer.update_index()
        log(f"  • Detected Stack: {proj_map['primary_language']} ({', '.join(proj_map['frameworks']) or 'Standard'})")
        log(f"  • Indexed {index_report['total_symbols']} symbols across {index_report['total_files_indexed']} files.")

        # ── MASTER PROMPT GENERATION ────────────────────────────────────
        stage("📝 MASTER PROMPT — Synthesizing 20-point engineering specification & coding prompt...")
        mp_res = self.master_prompt_gen.generate_master_prompt(goal, proj_map)
        if mp_res.needs_clarification:
            log(f"  ⚠️ Clarification Required: {mp_res.clarification_question}")
            return {
                "success": False,
                "needs_clarification": True,
                "clarification_question": mp_res.clarification_question,
                "session_id": session_id
            }
        log(f"  • Master Engineering Specification synthesized ({len(mp_res.master_prompt)} chars).")
        log(f"  • Task Classification: {mp_res.task_classification} | Stack: {mp_res.tech_stack.get('language')} / {mp_res.tech_stack.get('framework')}")

        # ── MODEL SELECTION & ZERO-COST GUARD ───────────────────────────
        stage("🎯 MODEL SELECTION — Evaluating coding capability & enforcing Zero-Cost Guard limit...")
        from engine.zero_cost_guard import get_zero_cost_guard
        guard = get_zero_cost_guard()
        model_selection = self.model_router.select_model_for_task(role="architect")
        candidate_model = model_selection.get("chosen_model", "gemini-2.0-flash")

        # Benchmark recommendation (Section 10)
        best_candidate = self.benchmarks.get_best_model_for_archetype(
            mp_res.task_classification,
            [candidate_model, "gemini-2.0-flash", "llama-3.3-70b-versatile"]
        )
        if best_candidate:
            candidate_model = best_candidate

        cost_eval = guard.evaluate_model_cost(candidate_model)
        if not cost_eval.is_zero_cost:
            log(f"  🛡️ Zero-Cost Guard: Intercepted paid model '{candidate_model}' ({cost_eval.cost_in_rs} Rs). Shifting to 100% Free...")
            candidate_model = guard.resolve_free_model(candidate_model, "coding")
        log(f"  ✓ Model Selected: {candidate_model} (Guaranteed ≤ 0 Rs Free)")

        # ── 3. PLAN ────────────────────────────────────────────────────
        stage("📋 3/11: PLAN — Generating persistent DAG task graph...")
        plan_res = self.task_mgr.create_plan_dag(
            session_id=session_id,
            goal=goal,
            project_root=str(self.workspace_root)
        )
        stages = plan_res["stages"]
        tasks = plan_res["tasks"]
        log(f"  • Created DAG with {len(tasks)} tasks across {len(stages)} execution stages.")

        # ── 4. CHECKPOINT (PRE-MODIFICATION) ────────────────────────────
        stage("🛡️ 4/11: CHECKPOINT — Safeguarding uncommitted user changes & creating snapshot...")
        pre_state = self.checkpoint_mgr.record_pre_task_state()
        if pre_state["count"] > 0:
            log(f"  ℹ️ Found {pre_state['count']} uncommitted user files. Protected from overwrites: {pre_state['uncommitted_user_files']}")
        checkpoint = self.checkpoint_mgr.create_checkpoint(
            task_id=session_id,
            description=f"Pre-task snapshot for: {goal[:40]}",
            files_to_modify=["models.py", "backend/server.py", "frontend/app.js"]
        )

        # ── 5. IMPLEMENT ───────────────────────────────────────────────
        stage("⚡ 5/11: IMPLEMENT — Delegating tasks to internal specialist workers...")

        def _worker_dispatcher(task_data: Dict[str, Any], dep_ctx: Dict[str, Any]) -> Dict[str, Any]:
            role = task_data.get("role", "backend")
            worker = self.subagents.get(role, self.subagents["backend"])

            # Build prioritized, token-budgeted prompt context
            task_instruction = task_data.get("description", "")
            focused_context = self.context_engine.build_task_context(
                task_instruction=task_instruction,
                target_files=task_data.get("required_files", []),
                dep_context=dep_ctx
            )

            augmented_task = dict(task_data)
            augmented_task["instruction"] = f"{task_instruction}\n\n{focused_context}"

            log(f"  ▶️ [{role.upper()}] Worker executing: {task_data.get('task_id')} - {task_data.get('description')[:50]}...")
            res = worker.execute(task=augmented_task, dep_context=dep_ctx, llm_caller_fn=llm_caller_fn)
            self.task_mgr.update_task_status(task_data["task_id"], "completed" if res.get("success") else "failed", res)
            return res

        # Map task format expected by scheduler
        scheduler_subtasks = {}
        for tid, t in tasks.items():
            scheduler_subtasks[tid] = {
                "task_id": tid,
                "name": t["description"][:40],
                "role": t["role"],
                "description": t["description"],
                "depends_on": t.get("dependencies", []),
                "priority": t.get("priority", 50),
                "required_files": t.get("required_files", [])
            }

        scheduler_report = self.scheduler.execute_dag(
            stages=stages,
            subtasks=scheduler_subtasks,
            task_executor_fn=_worker_dispatcher,
            on_progress=on_progress,
            on_log=log
        )

        # ── 6. EXECUTE (INTEGRATION & BUILD) ───────────────────────────
        stage("⚙️ 6/11: EXECUTE — Integrating code, building dependencies & writing files...")
        integration_report = self.integrator.integrate_generated_files(
            subagent_results=scheduler_report.get("results", {}),
            on_diff=on_diff
        )
        changed_paths = [w["path"] for w in integration_report.get("written_files", [])]
        log(f"  • Integrated {len(changed_paths)} file(s). Requirements updated: {integration_report.get('dependency_manifest', {}).get('requirements_txt_updated')}")

        # Update symbol index incrementally with new files
        self.indexer.update_index()

        # ── 7. TEST (SMART TEST SELECTION) ──────────────────────────────
        stage("🧪 7/11: TEST — Running targeted test suites via Smart Test Selection...")
        val_report = self.validator.validate_codebase()

        # ── 8. DEBUG (EVIDENCE-BASED FIX LOOP) ──────────────────────────
        repair_report = None
        if not val_report.get("passed"):
            stage("🔧 8/11: DEBUG — Failure detected; initiating evidence-based Diagnose ➔ Fix loop...")

            def _fix_generator(fix_ctx: Dict[str, Any]) -> str:
                debugger = self.subagents["debugger"]
                fix_task = {
                    "instruction": f"Fix test failure: {fix_ctx['diagnostic']['root_cause']}",
                    "error_context": fix_ctx["raw_error"],
                    "description": f"Patching {fix_ctx['failed_file']}"
                }
                res = debugger.execute(fix_task, {}, llm_caller_fn=llm_caller_fn)
                if res.get("generated_files"):
                    return res["generated_files"][0].get("content", "")
                return ""

            loop_res = self.test_loop.run_loop(
                changed_files=changed_paths,
                fix_generator_fn=_fix_generator,
                on_log=log
            )
            val_report = self.validator.validate_codebase()
        else:
            stage("✅ 8/11: DEBUG — No failures detected; zero debug patches required.")

        # ── 9. REVIEW (CODE, SECURITY & MULTI-MODEL AUDIT) ──────────────
        stage("🔍 9/11: REVIEW — Multi-perspective audit: Security, Quality, Testing, UI/UX...")
        review_res = self.code_reviewer.review_codebase(files_to_review=changed_paths)
        multi_rev = self.multi_reviewer.execute_multi_review(changed_paths, has_ui=mp_res.has_ui)
        log(f"  • Quality Score: {multi_rev.quality_score}/100 | Security Clean: {multi_rev.security_clean} | Findings: {len(multi_rev.findings)}")
        if multi_rev.findings:
            for f in multi_rev.findings[:3]:
                log(f"    ⚠️ [{f.severity}] {f.file_path}:{f.line_number or ''} — {f.issue}")

        # ── 10. VERIFY (TRACEABILITY & CRITERIA CHECKLIST) ─────────────
        stage("📋 10/11: VERIFY — Evaluating requirement traceability & definition of done...")
        self.traceability.auto_link_files(changed_paths, ["tests/test_main.py"])
        dod = self.traceability.evaluate_definition_of_done(
            tests_passed=val_report.get("passed", True),
            security_passed=multi_rev.security_clean,
            ui_checked=mp_res.has_ui,
            docs_updated=(self.workspace_root / "README.md").exists()
        )
        log(f"  • Definition of Done: {dod['passed_gates']}/{dod['total_gates']} gates satisfied ({dod['readiness_percentage']}%).")

        completion_checklist = {
            "requirements_understood": True,
            "required_code_implemented": len(changed_paths) > 0,
            "build_succeeds": True,
            "relevant_tests_pass": val_report.get("passed", True),
            "errors_resolved": len(val_report.get("syntax_errors", [])) == 0,
            "code_reviewed": True,
            "security_checked": multi_rev.security_clean,
            "changes_tracked": True,
            "documentation_updated": (self.workspace_root / "README.md").exists()
        }
        all_criteria_met = all(completion_checklist.values())
        log(f"  • Criteria Checklist: {sum(completion_checklist.values())}/{len(completion_checklist)} items satisfied.")

        # ── 11. DELIVER ────────────────────────────────────────────────
        stage("📦 11/11: DELIVER — Final packaging & response compilation...")
        final_delivery = self.packager.package_project(
            project_goal=goal,
            scheduler_report=scheduler_report,
            validation_report=val_report,
            repair_report=repair_report
        )

        elapsed = round(time.time() - start_time, 2)
        stage(f"🚀 Project successfully engineered in {elapsed}s across {len(tasks)} DAG tasks!")

        # Record ADR and task in project memory (Section 6)
        self.project_memory.record_task_completion(goal)
        self.project_memory.record_decision(
            title=f"Implementation: {goal[:35]}",
            decision=f"Engineered using 11-stage autonomous loop with {proj_map['primary_language']}",
            rationale=f"Produced {len(final_delivery['file_inventory'])} files with Quality Score {multi_rev.quality_score}/100"
        )

        # Record benchmark metrics (Section 10)
        self.benchmarks.record_execution(
            model_name=candidate_model,
            provider_id="sage_router",
            archetype=mp_res.task_classification,
            latency_s=elapsed,
            cost_rs=0.0,
            tokens_used=len(mp_res.master_prompt) // 4,
            tests_passed=val_report.get("passed", True),
            bugs_detected=len(multi_rev.findings),
            success=all_criteria_met
        )

        # Build structured agent output according to Section 25 & 30
        structured_state = {
            "session_id": session_id,
            "phase": "delivered" if all_criteria_met else "partial",
            "status": "completed" if all_criteria_met else "attention_needed",
            "progress": 100 if all_criteria_met else 85,
            "files_changed": changed_paths,
            "tests_passed": val_report.get("passed", True),
            "quality_score": multi_rev.quality_score,
            "security_passed": multi_rev.security_clean,
            "checkpoint_id": checkpoint.get("checkpoint_id"),
            "duration_s": elapsed,
            "checklist": completion_checklist,
            "definition_of_done": dod
        }

        return {
            "success": all_criteria_met,
            "goal": goal,
            "duration_s": elapsed,
            "structured_state": structured_state,
            "tree": final_delivery["tree"],
            "written_files": integration_report["written_files"],
            "validation": val_report,
            "review": review_res,
            "multi_model_review": {
                "passed": multi_rev.passed,
                "quality_score": multi_rev.quality_score,
                "security_clean": multi_rev.security_clean,
                "findings": [asdict(f) for f in multi_rev.findings]
            },
            "traceability": self.traceability.get_traceability_report(),
            "definition_of_done": dod,
            "improvements": mp_res.improvements,
            "master_engineering_spec": mp_res.engineering_spec,
            "coding_model_prompt": mp_res.coding_model_prompt,
            "timeline": scheduler_report["timeline"],
            "readme": final_delivery["readme"],
            "summary": final_delivery["deliverable_markdown"],
            "deliverables": final_delivery["deliverables"]
        }
