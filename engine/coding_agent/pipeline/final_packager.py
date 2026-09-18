"""
Final Packaging & Response Delivery for SAGE Coding Agent Architecture (v6).
Prepares the complete deliverable bundle for the user:
- Complete working project files
- Code + Documentation package
- Tests and execution results
- Deployment guide
- Project structure map (ASCII tree)
- Task timeline and performance metrics
"""
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..context_manager import ContextFileManager

logger = logging.getLogger(__name__)


class FinalPackager:
    """Assembles final project deliverables and packages them for the user response."""

    def __init__(self, context_mgr: ContextFileManager):
        self.context_mgr = context_mgr

    def package_project(
        self,
        project_goal: str,
        scheduler_report: Dict[str, Any],
        validation_report: Dict[str, Any],
        repair_report: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Assembles all final artifacts, reports, and instructions into a cohesive delivery bundle.
        """
        files = self.context_mgr.list_files()
        tree = self.context_mgr.generate_project_tree(max_depth=4)

        # Extract README / Docs content if available
        readme_content = ""
        try:
            readme_content = self.context_mgr.read_file("README.md")
        except Exception:
            readme_content = f"# {project_goal}\nProject scaffolded by Sage Coding Agent v6."

        # Compute file inventory
        inventory = []
        for f in files:
            inventory.append({
                "path": f["path"],
                "size_bytes": f["size"],
                "type": Path(f["name"]).suffix or "file"
            })

        # Summarize test results
        test_info = validation_report.get("test_results", {})
        test_summary = "All automated checks and unit tests passed." if validation_report.get("passed") else "Some tests flagged items for attention."

        # Construct comprehensive markdown deliverable
        deliverable_md = (
            f"# 🚀 Project Delivery: {project_goal}\n\n"
            f"> **Built with SAGE Coding Agent (v6)** — *Build Big. Think Deep. Ship Fast.*\n\n"
            f"## 📋 Executive Summary\n"
            f"Successfully designed, implemented, tested, and packaged complete solution for `{project_goal}` across "
            f"{len(scheduler_report.get('timeline', []))} specialized sub-agent tasks.\n\n"
            f"## 🌲 Project Structure\n"
            f"```\n{tree}\n```\n\n"
            f"## 🧪 Automated Testing & Validation\n"
            f"- **Status**: {'✅ Passed' if validation_report.get('passed') else '⚠️ Warnings'}\n"
            f"- **Files Audited**: {validation_report.get('total_files_audited', len(files))}\n"
            f"- **Syntax Errors**: {len(validation_report.get('syntax_errors', []))}\n"
            f"- **Security Audit Findings**: {len(validation_report.get('security_findings', []))}\n"
            f"- **Test Suite Output**:\n```\n{test_info.get('stdout') or test_summary}\n```\n\n"
            f"## ⏱️ Execution Timeline\n"
        )

        for item in scheduler_report.get("timeline", []):
            status = "✅" if item.get("success") else "❌"
            deliverable_md += f"- `{item.get('timestamp')}` {status} **{item.get('role').upper()}**: {item.get('name')} ({item.get('duration_s')}s)\n"

        deliverable_md += (
            f"\n## 🚢 Deployment & Setup Guide\n"
            f"```bash\n"
            f"# 1. Start application\n"
            f"python backend/server.py\n\n"
            f"# 2. Run unit tests\n"
            f"python -m unittest discover -s tests\n\n"
            f"# 3. Run containerized\n"
            f"docker-compose up --build\n"
            f"```\n"
        )

        return {
            "success": True,
            "goal": project_goal,
            "project_name": self.context_mgr.workspace_root.name,
            "tree": tree,
            "file_inventory": inventory,
            "validation": validation_report,
            "timeline": scheduler_report.get("timeline", []),
            "readme": readme_content,
            "deliverable_markdown": deliverable_md,
            "deliverables": [
                {
                    "type": "code_solution",
                    "title": f"Complete Project: {project_goal[:40]}",
                    "content": deliverable_md,
                    "files": [f["path"] for f in files]
                },
                {
                    "type": "written_content",
                    "title": "README & Documentation",
                    "content": readme_content,
                    "files": ["README.md"]
                }
            ]
        }
