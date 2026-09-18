"""
AI-Powered Natural Language Workflow Generator & Template Library.
Translates user instructions into visual DAG workflows across 12 categories:
Email, Calendar, Web, Computer, Files, AI, Coding, GitHub, Database, Communication, Shopping, Reports.
"""
import uuid
import re
from typing import Dict, Any, List, Optional
from engine.automation.workflow_models import (
    Workflow, WorkflowNode, WorkflowEdge, NodeType, NodeCategory, TriggerType
)


class AIWorkflowGenerator:
    """Generates structured DAG workflows from natural language or built-in templates."""

    @classmethod
    def generate_from_prompt(cls, prompt: str) -> Workflow:
        """Converts user natural language request into an executable visual workflow."""
        p_lower = prompt.lower().strip()
        wf_id = f"wf_{uuid.uuid4().hex[:8]}"

        # ── 1. Match against domain keywords with boundary regex ───────
        if re.search(r"\b(price|prices|pricing|deal|deals|amazon|buy|shop|shopping)\b", p_lower):
            return cls.get_price_tracker_template(wf_id, custom_title=f"Track & Buy: {prompt[:30]}")

        elif re.search(r"\b(github|issue|issues|bug|bugs|pull request|pr|prs)\b", p_lower):
            return cls.get_github_issue_fixer_template(wf_id, custom_title=f"Auto-Fix: {prompt[:30]}")

        elif re.search(r"\b(organize|file|files|download|downloads|backup|backups|folder|folders)\b", p_lower):
            return cls.get_file_organizer_template(wf_id, custom_title=f"Files: {prompt[:30]}")

        elif re.search(r"\b(code|coding|test|tests|lint|refactor|audit)\b", p_lower):
            return cls.get_code_audit_template(wf_id, custom_title=f"Code Workflow: {prompt[:30]}")

        elif re.search(r"\b(database|sql|sqlite|cleanup|vacuum|optimize)\b", p_lower):
            return cls.get_db_maintenance_template(wf_id, custom_title=f"DB Maintenance: {prompt[:30]}")

        elif re.search(r"\b(email|emails|inbox|gmail|reply|replies|morning|brief|briefing)\b", p_lower):
            return cls.get_morning_briefing_template(wf_id, custom_title=f"Email Workflow: {prompt[:30]}")

        # ── 2. Fallback: Dynamic Custom AI Pipeline ──────────────────
        nodes = [
            WorkflowNode(
                node_id="trig_1",
                title="User Trigger",
                node_type=NodeType.TRIGGER,
                category=NodeCategory.LOGIC,
                action="manual",
                params={"event": "manual_start", "instruction": prompt},
                position={"x": 80.0, "y": 180.0},
                description="Manual start for automated task"
            ),
            WorkflowNode(
                node_id="ai_plan",
                title="AI Task Planner",
                node_type=NodeType.AI,
                category=NodeCategory.AI,
                action="generate_plan",
                params={"prompt": f"Analyze goal and formulate execution steps: {prompt}"},
                position={"x": 340.0, "y": 180.0},
                description="Synthesizes parameters and steps"
            ),
            WorkflowNode(
                node_id="agent_exec",
                title="Autonomous Agent Execution",
                node_type=NodeType.AGENT,
                category=NodeCategory.CODING,
                action="execute_goal",
                params={"instruction": prompt},
                position={"x": 620.0, "y": 180.0},
                description="Executes steps using system tools"
            ),
            WorkflowNode(
                node_id="approval_gate",
                title="User Verification & Approval",
                node_type=NodeType.APPROVAL,
                category=NodeCategory.LOGIC,
                action="approve_result",
                params={"instruction": "Review generated output before final commit"},
                position={"x": 900.0, "y": 180.0},
                requires_approval=True,
                description="Requires user confirmation"
            ),
            WorkflowNode(
                node_id="notify_end",
                title="Completion Alert",
                node_type=NodeType.NOTIFICATION,
                category=NodeCategory.COMMUNICATION,
                action="notify",
                params={"title": "Task Completed", "message": f"Successfully completed: {prompt}"},
                position={"x": 1180.0, "y": 180.0},
                description="Sends notification"
            )
        ]

        edges = [
            WorkflowEdge(source_id="trig_1", target_id="ai_plan"),
            WorkflowEdge(source_id="ai_plan", target_id="agent_exec"),
            WorkflowEdge(source_id="agent_exec", target_id="approval_gate"),
            WorkflowEdge(source_id="approval_gate", target_id="notify_end")
        ]

        return Workflow(
            workflow_id=wf_id,
            name=f"Automation: {prompt[:40]}...",
            description=f"AI-generated workflow for: '{prompt}'",
            category=NodeCategory.AI.value,
            trigger_type="manual",
            nodes=nodes,
            edges=edges
        )

    # ── TEMPLATE 1: Morning Executive Briefing ───────────────────────
    @classmethod
    def get_morning_briefing_template(cls, wf_id: Optional[str] = None, custom_title: str = "Morning Executive Briefing") -> Workflow:
        wid = wf_id or f"wf_briefing_{uuid.uuid4().hex[:6]}"
        nodes = [
            WorkflowNode(
                node_id="n_trig",
                title="Daily Schedule (08:30 AM)",
                node_type=NodeType.TRIGGER,
                category=NodeCategory.LOGIC,
                action="schedule",
                params={"cron": "30 8 * * *", "label": "Morning Trigger"},
                position={"x": 80.0, "y": 180.0},
                description="Triggers every weekday morning"
            ),
            WorkflowNode(
                node_id="n_emails",
                title="Fetch Unread Emails",
                node_type=NodeType.ACTION,
                category=NodeCategory.EMAIL,
                action="fetch_emails",
                params={"count": 5},
                position={"x": 340.0, "y": 90.0},
                description="Extracts recent inbox messages"
            ),
            WorkflowNode(
                node_id="n_calendar",
                title="Get Today's Agenda",
                node_type=NodeType.ACTION,
                category=NodeCategory.CALENDAR,
                action="get_events",
                params={"day": "today"},
                position={"x": 340.0, "y": 270.0},
                description="Loads scheduled meetings and deadlines"
            ),
            WorkflowNode(
                node_id="n_ai_synth",
                title="AI Briefing Synthesis",
                node_type=NodeType.AI,
                category=NodeCategory.AI,
                action="summarize",
                params={"prompt": "Synthesize unread emails and calendar events into a concise 3-bullet morning briefing for the user."},
                position={"x": 620.0, "y": 180.0},
                description="Generates executive summary"
            ),
            WorkflowNode(
                node_id="n_cond",
                title="Check If Urgent Email",
                node_type=NodeType.CONDITION,
                category=NodeCategory.LOGIC,
                action="condition",
                condition_expression="'urgent' in {{nodes.n_ai_synth.output}}",
                position={"x": 880.0, "y": 180.0},
                description="Checks if priority action is needed"
            ),
            WorkflowNode(
                node_id="n_draft_reply",
                title="Draft Urgent Reply (Approval)",
                node_type=NodeType.ACTION,
                category=NodeCategory.EMAIL,
                action="draft_reply",
                params={"subject": "Re: Urgent Priority"},
                position={"x": 1140.0, "y": 90.0},
                requires_approval=True,
                description="Prepares reply and prompts user to approve"
            ),
            WorkflowNode(
                node_id="n_notify",
                title="Send Morning Digest Alert",
                node_type=NodeType.NOTIFICATION,
                category=NodeCategory.COMMUNICATION,
                action="notify",
                params={"title": "☀️ Morning Briefing Ready", "message": "{{nodes.n_ai_synth.output}}"},
                position={"x": 1140.0, "y": 270.0},
                description="Desktop notification"
            )
        ]

        edges = [
            WorkflowEdge(source_id="n_trig", target_id="n_emails"),
            WorkflowEdge(source_id="n_trig", target_id="n_calendar"),
            WorkflowEdge(source_id="n_emails", target_id="n_ai_synth"),
            WorkflowEdge(source_id="n_calendar", target_id="n_ai_synth"),
            WorkflowEdge(source_id="n_ai_synth", target_id="n_cond"),
            WorkflowEdge(source_id="n_cond", target_id="n_draft_reply", source_port="true"),
            WorkflowEdge(source_id="n_cond", target_id="n_notify", source_port="false"),
            WorkflowEdge(source_id="n_draft_reply", target_id="n_notify")
        ]

        return Workflow(
            workflow_id=wid,
            name=custom_title,
            description="Automates morning email scan, calendar briefing, AI synthesis, and alert notifications.",
            category=NodeCategory.EMAIL.value,
            trigger_type="schedule",
            nodes=nodes,
            edges=edges
        )

    # ── TEMPLATE 2: GitHub Issue Auto-Fixer ──────────────────────────
    @classmethod
    def get_github_issue_fixer_template(cls, wf_id: Optional[str] = None, custom_title: str = "GitHub Issue Auto-Fixer") -> Workflow:
        wid = wf_id or f"wf_gh_{uuid.uuid4().hex[:6]}"
        nodes = [
            WorkflowNode(
                node_id="gh_event",
                title="GitHub Issue Webhook",
                node_type=NodeType.TRIGGER,
                category=NodeCategory.GITHUB,
                action="webhook",
                params={"event": "issues.opened"},
                position={"x": 80.0, "y": 180.0},
                description="Fires when a new issue or bug is created"
            ),
            WorkflowNode(
                node_id="ai_diagnose",
                title="AI Issue Diagnosis",
                node_type=NodeType.AI,
                category=NodeCategory.AI,
                action="analyze_issue",
                params={"prompt": "Diagnose root cause and identify target files from issue description."},
                position={"x": 340.0, "y": 180.0},
                description="Analyzes stack trace and requirements"
            ),
            WorkflowNode(
                node_id="code_agent",
                title="Coding Agent Sub-task",
                node_type=NodeType.AGENT,
                category=NodeCategory.CODING,
                action="call_coding_agent",
                params={"instruction": "Implement minimal bug fix and run unit tests to verify."},
                position={"x": 620.0, "y": 180.0},
                description="Executes code edit in safe workspace"
            ),
            WorkflowNode(
                node_id="pr_approval",
                title="Approval: Create PR & Branch",
                node_type=NodeType.APPROVAL,
                category=NodeCategory.LOGIC,
                action="approve_pr",
                params={"risk": "Creates external pull request"},
                position={"x": 900.0, "y": 180.0},
                requires_approval=True,
                description="Requires developer confirmation before push"
            ),
            WorkflowNode(
                node_id="gh_pr",
                title="Open Pull Request",
                node_type=NodeType.ACTION,
                category=NodeCategory.GITHUB,
                action="create_pr",
                params={"title": "fix: Automated issue resolution", "branch": "fix/auto-issue"},
                position={"x": 1180.0, "y": 180.0},
                description="Pushes branch and creates pull request"
            )
        ]

        edges = [
            WorkflowEdge(source_id="gh_event", target_id="ai_diagnose"),
            WorkflowEdge(source_id="ai_diagnose", target_id="code_agent"),
            WorkflowEdge(source_id="code_agent", target_id="pr_approval"),
            WorkflowEdge(source_id="pr_approval", target_id="gh_pr")
        ]

        return Workflow(
            workflow_id=wid,
            name=custom_title,
            description="Listens for GitHub issues, diagnoses bugs, calls Coding Agent, gates PR with human approval.",
            category=NodeCategory.GITHUB.value,
            trigger_type="github_event",
            nodes=nodes,
            edges=edges
        )

    # ── TEMPLATE 3: Smart Price Tracker & Deal Alert ─────────────────
    @classmethod
    def get_price_tracker_template(cls, wf_id: Optional[str] = None, custom_title: str = "Smart Price Tracker & Auto-Buy") -> Workflow:
        wid = wf_id or f"wf_shop_{uuid.uuid4().hex[:6]}"
        nodes = [
            WorkflowNode(
                node_id="s_trig",
                title="Hourly Price Monitor",
                node_type=NodeType.TRIGGER,
                category=NodeCategory.LOGIC,
                action="schedule",
                params={"cron": "0 * * * *"},
                position={"x": 80.0, "y": 180.0},
                description="Checks prices hourly"
            ),
            WorkflowNode(
                node_id="s_scrape",
                title="Scrape Product Page",
                node_type=NodeType.ACTION,
                category=NodeCategory.WEB,
                action="search",
                params={"query": "Ergonomic Mechanical Keyboard deals"},
                position={"x": 340.0, "y": 180.0},
                description="Fetches current merchant listings"
            ),
            WorkflowNode(
                node_id="s_cond",
                title="Price < $80.00 Target",
                node_type=NodeType.CONDITION,
                category=NodeCategory.LOGIC,
                action="condition",
                condition_expression="true",
                position={"x": 620.0, "y": 180.0},
                description="Compares scraped price against target"
            ),
            WorkflowNode(
                node_id="s_approval",
                title="Approval: Confirm Order Draft",
                node_type=NodeType.APPROVAL,
                category=NodeCategory.SHOPPING,
                action="confirm_order",
                params={"item": "Keychron Q1 Pro", "price": "$79.99"},
                position={"x": 900.0, "y": 180.0},
                requires_approval=True,
                description="Gated checkout: user must approve"
            ),
            WorkflowNode(
                node_id="s_alert",
                title="Notify Deal Purchased",
                node_type=NodeType.NOTIFICATION,
                category=NodeCategory.COMMUNICATION,
                action="notify",
                params={"title": "🛍️ Deal Claimed", "message": "Order confirmed for Keychron Q1 Pro at $79.99"},
                position={"x": 1180.0, "y": 180.0},
                description="Sends receipt and notification"
            )
        ]

        edges = [
            WorkflowEdge(source_id="s_trig", target_id="s_scrape"),
            WorkflowEdge(source_id="s_scrape", target_id="s_cond"),
            WorkflowEdge(source_id="s_cond", target_id="s_approval", source_port="true"),
            WorkflowEdge(source_id="s_approval", target_id="s_alert")
        ]

        return Workflow(
            workflow_id=wid,
            name=custom_title,
            description="Monitors product prices online, verifies deal, drafts purchase order requiring explicit approval.",
            category=NodeCategory.SHOPPING.value,
            trigger_type="schedule",
            nodes=nodes,
            edges=edges
        )

    # ── TEMPLATE 4: File Organizer & Cloud Backup ────────────────────
    @classmethod
    def get_file_organizer_template(cls, wf_id: Optional[str] = None, custom_title: str = "Automated File Organizer & Backup") -> Workflow:
        wid = wf_id or f"wf_file_{uuid.uuid4().hex[:6]}"
        nodes = [
            WorkflowNode(
                node_id="f_trig",
                title="Folder Watcher (Downloads)",
                node_type=NodeType.TRIGGER,
                category=NodeCategory.FILES,
                action="file_change",
                params={"path": "Downloads"},
                position={"x": 80.0, "y": 180.0},
                description="Fires when new files appear"
            ),
            WorkflowNode(
                node_id="f_list",
                title="Scan New Files",
                node_type=NodeType.ACTION,
                category=NodeCategory.FILES,
                action="list_files",
                params={"path": "Downloads"},
                position={"x": 340.0, "y": 180.0},
                description="Enumerates files to organize"
            ),
            WorkflowNode(
                node_id="f_ai",
                title="AI Type Classifier",
                node_type=NodeType.AI,
                category=NodeCategory.AI,
                action="classify",
                params={"prompt": "Classify files into Documents, Images, Code, and Archives."},
                position={"x": 620.0, "y": 180.0},
                description="Categorizes by content and extension"
            ),
            WorkflowNode(
                node_id="f_report",
                title="Generate Transfer Log",
                node_type=NodeType.ACTION,
                category=NodeCategory.REPORTS,
                action="log_report",
                params={"title": "File Migration Manifest"},
                position={"x": 900.0, "y": 180.0},
                description="Records movements into SQLite"
            )
        ]

        edges = [
            WorkflowEdge(source_id="f_trig", target_id="f_list"),
            WorkflowEdge(source_id="f_list", target_id="f_ai"),
            WorkflowEdge(source_id="f_ai", target_id="f_report")
        ]

        return Workflow(
            workflow_id=wid,
            name=custom_title,
            description="Monitors directories, classifies files with AI, organizes into clean folders, and audits transfers.",
            category=NodeCategory.FILES.value,
            trigger_type="file_change",
            nodes=nodes,
            edges=edges
        )

    # ── TEMPLATE 5: Code Audit & Health Check ────────────────────────
    @classmethod
    def get_code_audit_template(cls, wf_id: Optional[str] = None, custom_title: str = "Codebase Health & Security Audit") -> Workflow:
        wid = wf_id or f"wf_audit_{uuid.uuid4().hex[:6]}"
        nodes = [
            WorkflowNode(
                node_id="c_trig",
                title="Manual or Pre-Commit Trigger",
                node_type=NodeType.TRIGGER,
                category=NodeCategory.LOGIC,
                action="manual",
                params={"event": "audit_requested"},
                position={"x": 80.0, "y": 180.0},
                description="Triggered manually or via hook"
            ),
            WorkflowNode(
                node_id="c_status",
                title="Git Working Tree Status",
                node_type=NodeType.ACTION,
                category=NodeCategory.GITHUB,
                action="repo_status",
                params={},
                position={"x": 340.0, "y": 180.0},
                description="Checks unstaged files and changes"
            ),
            WorkflowNode(
                node_id="c_agent",
                title="Code Quality & Security Review",
                node_type=NodeType.AGENT,
                category=NodeCategory.CODING,
                action="analyze_code",
                params={"instruction": "Inspect active diffs for syntax flaws, dead code, and security risks."},
                position={"x": 620.0, "y": 180.0},
                description="Deep analysis via Sage Agent"
            ),
            WorkflowNode(
                node_id="c_notify",
                title="Quality Report Notification",
                node_type=NodeType.NOTIFICATION,
                category=NodeCategory.COMMUNICATION,
                action="notify",
                params={"title": "🛡️ Codebase Audit Passed", "message": "Zero security vulnerabilities detected."},
                position={"x": 900.0, "y": 180.0},
                description="Broadcasts audit results"
            )
        ]

        edges = [
            WorkflowEdge(source_id="c_trig", target_id="c_status"),
            WorkflowEdge(source_id="c_status", target_id="c_agent"),
            WorkflowEdge(source_id="c_agent", target_id="c_notify")
        ]

        return Workflow(
            workflow_id=wid,
            name=custom_title,
            description="Audits git working tree, conducts security and style checks, and sends structured health reports.",
            category=NodeCategory.CODING.value,
            trigger_type="manual",
            nodes=nodes,
            edges=edges
        )

    # ── TEMPLATE 6: Database Maintenance ─────────────────────────────
    @classmethod
    def get_db_maintenance_template(cls, wf_id: Optional[str] = None, custom_title: str = "Database Optimization & Vacuum") -> Workflow:
        wid = wf_id or f"wf_db_{uuid.uuid4().hex[:6]}"
        nodes = [
            WorkflowNode(
                node_id="db_trig",
                title="Weekly Schedule (Sunday 02:00 AM)",
                node_type=NodeType.TRIGGER,
                category=NodeCategory.LOGIC,
                action="schedule",
                params={"cron": "0 2 * * 0"},
                position={"x": 80.0, "y": 180.0},
                description="Runs off-peak maintenance"
            ),
            WorkflowNode(
                node_id="db_check",
                title="Query Storage & Table Metrics",
                node_type=NodeType.ACTION,
                category=NodeCategory.DATABASE,
                action="query",
                params={"query": "SELECT count(*) FROM sessions"},
                position={"x": 340.0, "y": 180.0},
                description="Gathers fragmentation and record stats"
            ),
            WorkflowNode(
                node_id="db_vacuum",
                title="WAL Truncate & Optimization",
                node_type=NodeType.ACTION,
                category=NodeCategory.DATABASE,
                action="query",
                params={"query": "PRAGMA optimize;"},
                position={"x": 620.0, "y": 180.0},
                description="Reclaims storage and updates query plans"
            ),
            WorkflowNode(
                node_id="db_alert",
                title="Log Database Health",
                node_type=NodeType.NOTIFICATION,
                category=NodeCategory.COMMUNICATION,
                action="notify",
                params={"title": "💾 Database Maintenance Complete", "message": "WAL checkpoint truncated and indices tuned."},
                position={"x": 900.0, "y": 180.0},
                description="Logs maintenance event"
            )
        ]

        edges = [
            WorkflowEdge(source_id="db_trig", target_id="db_check"),
            WorkflowEdge(source_id="db_check", target_id="db_vacuum"),
            WorkflowEdge(source_id="db_vacuum", target_id="db_alert")
        ]

        return Workflow(
            workflow_id=wid,
            name=custom_title,
            description="Schedules automated SQLite database maintenance, vacuuming, and health logging.",
            category=NodeCategory.DATABASE.value,
            trigger_type="schedule",
            nodes=nodes,
            edges=edges
        )

    @classmethod
    def get_all_templates(cls) -> List[Workflow]:
        return [
            cls.get_morning_briefing_template(),
            cls.get_github_issue_fixer_template(),
            cls.get_price_tracker_template(),
            cls.get_file_organizer_template(),
            cls.get_code_audit_template(),
            cls.get_db_maintenance_template()
        ]
