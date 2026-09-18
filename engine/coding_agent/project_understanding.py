"""
Project Understanding Engine for SAGE Coding Agent Architecture (v6).
Capabilities:
- Analyze requirements from complex prompts
- Read existing codebase and manifests
- Understand architecture & patterns (monolith, microservices, SPA + API, CLI)
- Detect frameworks and languages (Python, TypeScript, React, Next.js, FastAPI, etc.)
- Map internal and external dependencies
- Break into modules for specialized sub-agents
"""
import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from .context_manager import ContextFileManager

logger = logging.getLogger(__name__)


class ProjectUnderstandingEngine:
    """Performs deep static analysis and architectural discovery of target projects."""

    FRAMEWORK_SIGNATURES = {
        "FastAPI": ["fastapi", "uvicorn"],
        "Flask": ["flask"],
        "Django": ["django"],
        "React": ["react", "react-dom"],
        "Next.js": ["next"],
        "Vue": ["vue"],
        "Svelte": ["svelte"],
        "Express": ["express"],
        "TailwindCSS": ["tailwindcss"],
        "PyTorch": ["torch"],
        "TensorFlow": ["tensorflow"],
    }

    LANGUAGE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript-react",
        ".jsx": "javascript-react",
        ".html": "html",
        ".css": "css",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".sql": "sql",
        ".sh": "shell",
        ".bat": "batch",
        ".ps1": "powershell"
    }

    def __init__(self, context_mgr: ContextFileManager):
        self.context_mgr = context_mgr
        self.workspace_root = context_mgr.workspace_root

    def update_workspace_root(self, root: Path):
        self.workspace_root = root

    def analyze_requirements(self, user_prompt: str, existing_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Parses complex user prompts to extract functional requirements,
        non-functional requirements, target stack, and constraints.
        """
        clean_prompt = user_prompt.strip()
        p_lower = clean_prompt.lower()

        # Detect domain
        domain = "general"
        if any(w in p_lower for w in ("lms", "learning management", "course", "student", "quiz")):
            domain = "lms_education"
        elif any(w in p_lower for w in ("ecommerce", "shop", "cart", "store", "product", "checkout", "stripe")):
            domain = "ecommerce"
        elif any(w in p_lower for w in ("chat", "messaging", "social", "forum")):
            domain = "social_communication"
        elif any(w in p_lower for w in ("dashboard", "crm", "analytics", "admin")):
            domain = "saas_dashboard"

        # Detect desired features
        features = []
        if any(w in p_lower for w in ("auth", "login", "signup", "jwt", "password", "oauth")):
            features.append("authentication")
        if any(w in p_lower for w in ("payment", "stripe", "paypal", "billing", "checkout")):
            features.append("payments")
        if any(w in p_lower for w in ("dashboard", "metrics", "chart", "analytics")):
            features.append("dashboard")
        if any(w in p_lower for w in ("database", "db", "sqlite", "postgres", "sql", "orm", "models")):
            features.append("database")
        if any(w in p_lower for w in ("api", "rest", "endpoint", "crud")):
            features.append("rest_api")
        if any(w in p_lower for w in ("docker", "deploy", "ci/cd", "compose", "container")):
            features.append("devops_deployment")
        if any(w in p_lower for w in ("test", "pytest", "unit test", "qa")):
            features.append("testing")
        if any(w in p_lower for w in ("docs", "documentation", "readme", "swagger", "openapi")):
            features.append("documentation")

        # Preferred tech stack detection from prompt
        suggested_stack = {}
        if "react" in p_lower or "next" in p_lower:
            suggested_stack["frontend"] = "React"
        elif "vue" in p_lower:
            suggested_stack["frontend"] = "Vue"
        elif "html" in p_lower or "vanilla" in p_lower:
            suggested_stack["frontend"] = "Vanilla HTML/CSS/JS"
        else:
            suggested_stack["frontend"] = "HTML/CSS/JS or React"

        if "fastapi" in p_lower or "python" in p_lower:
            suggested_stack["backend"] = "Python (FastAPI / Standard Library)"
        elif "node" in p_lower or "express" in p_lower:
            suggested_stack["backend"] = "Node.js (Express)"
        else:
            suggested_stack["backend"] = "Python"

        return {
            "prompt": clean_prompt,
            "domain": domain,
            "detected_features": features,
            "suggested_stack": suggested_stack,
            "is_greenfield": len(self.context_mgr.list_files()) == 0
        }

    def inspect_codebase(self) -> Dict[str, Any]:
        """
        Reads existing codebase, detects languages, frameworks, manifests, and architecture.
        """
        files = self.context_mgr.list_files(max_files=400)
        language_counts: Dict[str, int] = {}
        manifests: Dict[str, Any] = {}

        for f in files:
            ext = Path(f["name"]).suffix.lower()
            if ext in self.LANGUAGE_EXTENSIONS:
                lang = self.LANGUAGE_EXTENSIONS[ext]
                language_counts[lang] = language_counts.get(lang, 0) + 1

        # Check for key manifests
        for manifest_file in ["package.json", "requirements.txt", "pyproject.toml", "Cargo.toml", "Dockerfile", "docker-compose.yml", "README.md"]:
            try:
                content = self.context_mgr.read_file(manifest_file, max_lines=200)
                manifests[manifest_file] = content
            except Exception:
                pass

        # Detect frameworks from manifests
        detected_frameworks = []
        all_manifest_text = "\n".join(manifests.values()).lower()
        for fw, sigs in self.FRAMEWORK_SIGNATURES.items():
            if any(s.lower() in all_manifest_text for s in sigs):
                detected_frameworks.append(fw)

        # Architectural pattern deduction
        primary_lang = max(language_counts, key=language_counts.get) if language_counts else "python"
        has_frontend = any(lang in language_counts for lang in ("javascript", "typescript", "html", "typescript-react", "javascript-react"))
        has_backend = any(lang in language_counts for lang in ("python", "rust", "go", "java"))

        arch_pattern = "Monolithic / Script"
        if has_frontend and has_backend:
            arch_pattern = "Client-Server Full-Stack"
        elif "FastAPI" in detected_frameworks or "Flask" in detected_frameworks or "Express" in detected_frameworks:
            arch_pattern = "RESTful API Microservice"
        elif has_frontend:
            arch_pattern = "Single Page Application (SPA)"

        return {
            "file_count": len(files),
            "primary_language": primary_lang,
            "languages": language_counts,
            "manifests_present": list(manifests.keys()),
            "frameworks": detected_frameworks,
            "architecture_pattern": arch_pattern,
            "tree_preview": self.context_mgr.generate_project_tree(max_depth=3)
        }

    def break_into_modules(self, requirements: Dict[str, Any], codebase_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Deconstructs the project into decoupled modules mapped to specialized sub-agents.
        """
        modules = [
            {
                "module_id": "mod_architecture",
                "name": "System Architecture & Contracts",
                "owner_subagent": "architect",
                "deliverables": ["Architecture Blueprint", "Data Models / Schema Spec", "API Route Contracts"]
            },
            {
                "module_id": "mod_backend",
                "name": "Backend APIs & Business Logic",
                "owner_subagent": "backend",
                "deliverables": ["API Routes", "Controllers", "Authentication Middleware", "DB Migrations"]
            },
            {
                "module_id": "mod_frontend",
                "name": "Frontend UI & User Interaction",
                "owner_subagent": "frontend",
                "deliverables": ["UI Components", "Pages / Views", "State Management", "API Client Integration"]
            },
            {
                "module_id": "mod_devops",
                "name": "DevOps, Containerization & CI/CD",
                "owner_subagent": "devops",
                "deliverables": ["Dockerfile", "docker-compose.yml", "Environment Config (.env.example)", "CI Workflow"]
            },
            {
                "module_id": "mod_qa",
                "name": "Automated Testing & Security Validation",
                "owner_subagent": "qa",
                "deliverables": ["Unit Tests", "Integration Tests", "Security Vulnerability Audit"]
            },
            {
                "module_id": "mod_docs",
                "name": "Documentation & Setup Guides",
                "owner_subagent": "documentation",
                "deliverables": ["README.md", "API Documentation", "Setup & Deployment Guide"]
            }
        ]
        return modules
