"""
Project Analyzer for SAGE Autonomous Coding Agent.
Deeply analyzes target projects and generates a structured, cached project map:
- Programming languages & runtimes
- Frameworks (Frontend, Backend, Full-stack)
- Package managers & dependencies
- Application entry points & configuration files
- Environment templates & build/test systems
- Database & API structures
- Docker containerization & CI/CD configurations
- Git status & uncommitted change detection
"""
import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)


class ProjectAnalyzer:
    """Discovers, maps, and caches project architecture, stack, and dependencies."""

    FRAMEWORK_PATTERNS = {
        # Backend
        "FastAPI": ["fastapi", "uvicorn"],
        "Flask": ["flask"],
        "Django": ["django"],
        "Express": ["express"],
        "NestJS": ["@nestjs/core"],
        "Spring Boot": ["spring-boot"],
        "Actix": ["actix-web"],
        "Gin": ["github.com/gin-gonic/gin"],
        # Frontend
        "React": ["react", "react-dom"],
        "Next.js": ["next"],
        "Vue": ["vue"],
        "Nuxt": ["nuxt"],
        "Svelte": ["svelte"],
        "Angular": ["@angular/core"],
        "TailwindCSS": ["tailwindcss"],
        "Bootstrap": ["bootstrap"],
    }

    BUILD_SYSTEM_FILES = {
        "npm": ["package.json"],
        "pnpm": ["pnpm-lock.yaml"],
        "yarn": ["yarn.lock"],
        "pip": ["requirements.txt"],
        "poetry": ["pyproject.toml", "poetry.lock"],
        "pipenv": ["Pipfile"],
        "cargo": ["Cargo.toml"],
        "maven": ["pom.xml"],
        "gradle": ["build.gradle", "build.gradle.kts"],
        "go": ["go.mod"],
        "make": ["Makefile"],
        "cmake": ["CMakeLists.txt"]
    }

    TEST_FRAMEWORK_SIGNATURES = {
        "pytest": ["pytest", "pytest.ini", "conftest.py"],
        "unittest": ["unittest"],
        "jest": ["jest", "jest.config.js", "jest.config.ts"],
        "vitest": ["vitest", "vitest.config.ts"],
        "mocha": ["mocha"],
        "cargo_test": ["Cargo.toml"],
        "go_test": ["_test.go"]
    }

    ENTRY_POINT_CANDIDATES = [
        "main.py", "app.py", "server.py", "wsgi.py", "asgi.py", "index.py",
        "index.js", "index.ts", "server.js", "server.ts", "main.js", "main.ts",
        "src/main.py", "src/app.py", "src/index.js", "src/index.ts", "src/main.rs",
        "cmd/main.go", "main.go"
    ]

    IGNORE_DIRS = {
        ".git", ".venv", "venv", "node_modules", "__pycache__",
        ".pytest_cache", "dist", "build", ".next", ".nuxt",
        ".idea", ".vscode", "coverage", "vendor", ".mypy_cache"
    }

    def __init__(self, workspace_root: Path, cache_dir: Optional[Path] = None):
        self.workspace_root = workspace_root.resolve()
        self.cache_dir = cache_dir or (self.workspace_root / ".sage_cache")
        self.cached_map: Optional[Dict[str, Any]] = None

    def set_workspace_root(self, root: Path):
        self.workspace_root = root.resolve()
        self.cache_dir = self.workspace_root / ".sage_cache"
        self.cached_map = None

    def analyze_project(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Generates or retrieves cached project map.
        Analyzes the full workspace architecture without re-scanning unchanged trees.
        """
        if not force_refresh and self.cached_map is not None:
            return self.cached_map

        # Check disk cache
        cache_file = self.cache_dir / "project_map.json"
        if not force_refresh and cache_file.exists():
            try:
                self.cached_map = json.loads(cache_file.read_text(encoding="utf-8"))
                return self.cached_map
            except Exception:
                pass

        # Perform deep analysis
        project_map = self._perform_deep_analysis()
        self.cached_map = project_map

        # Persist cache
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(project_map, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug("Could not save project map cache: %s", e)

        return project_map

    def _perform_deep_analysis(self) -> Dict[str, Any]:
        """Scans workspace and extracts structural characteristics."""
        files = self._collect_workspace_files()
        file_paths = [f["rel_path"] for f in files]

        # 1. Languages
        language_counts: Dict[str, int] = {}
        for f in files:
            ext = f["ext"].lower()
            lang = self._ext_to_lang(ext)
            if lang:
                language_counts[lang] = language_counts.get(lang, 0) + 1

        primary_lang = max(language_counts, key=language_counts.get) if language_counts else "unknown"

        # 2. Manifests & Configs
        manifests = {}
        for m_name in [
            "package.json", "requirements.txt", "pyproject.toml", "Cargo.toml",
            "go.mod", "pom.xml", "Dockerfile", "docker-compose.yml", ".env.example",
            "tsconfig.json", "Makefile", "README.md"
        ]:
            if m_name in file_paths:
                try:
                    full = self.workspace_root / m_name
                    manifests[m_name] = full.read_text(encoding="utf-8", errors="replace")[:10000]
                except Exception:
                    pass

        # 3. Detect Frameworks
        detected_frameworks = self._detect_frameworks(manifests, files)

        # 4. Package Managers & Build System
        package_managers = []
        for pm, sig_files in self.BUILD_SYSTEM_FILES.items():
            if any(sf in file_paths for sf in sig_files):
                package_managers.append(pm)

        # 5. Test Frameworks
        test_frameworks = []
        for tf, sigs in self.TEST_FRAMEWORK_SIGNATURES.items():
            if any(s in file_paths for s in sigs):
                test_frameworks.append(tf)
            elif any(s in "\n".join(manifests.values()).lower() for s in sigs):
                test_frameworks.append(tf)

        # 6. Entry Points
        entry_points = [ep for ep in self.ENTRY_POINT_CANDIDATES if ep in file_paths]

        # 7. Architecture Classification
        has_frontend = any(lang in language_counts for lang in ("javascript", "typescript", "html", "css", "vue", "svelte"))
        has_backend = any(lang in language_counts for lang in ("python", "rust", "go", "java", "c#", "php"))
        has_docker = "Dockerfile" in file_paths or "docker-compose.yml" in file_paths
        has_ci = any(p.startswith(".github/workflows") or p.startswith(".gitlab-ci") for p in file_paths)

        if has_frontend and has_backend:
            arch_type = "Full-Stack (Client-Server)"
        elif has_backend and any(fw in detected_frameworks for fw in ("FastAPI", "Flask", "Express", "Gin")):
            arch_type = "Backend REST API / Microservice"
        elif has_frontend and any(fw in detected_frameworks for fw in ("React", "Vue", "Next.js", "Svelte")):
            arch_type = "Frontend SPA / Web Application"
        elif "python" in language_counts and any("cli" in p.lower() or "main.py" in p for p in file_paths):
            arch_type = "CLI / Script Automation"
        else:
            arch_type = "Modular Application"

        # 8. Directory Module Layout
        modules = self._discover_module_tree()

        return {
            "project_name": self.workspace_root.name,
            "root_path": str(self.workspace_root),
            "file_count": len(files),
            "primary_language": primary_lang,
            "languages": language_counts,
            "frameworks": detected_frameworks,
            "package_managers": package_managers,
            "test_frameworks": test_frameworks,
            "entry_points": entry_points,
            "architecture_type": arch_type,
            "manifests_present": list(manifests.keys()),
            "has_docker": has_docker,
            "has_ci": has_ci,
            "modules": modules
        }

    def _collect_workspace_files(self, max_files: int = 2000) -> List[Dict[str, Any]]:
        """Walks directory collecting paths, ignoring transient/build folders."""
        results = []
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS and not d.startswith(".")]
            for f in files:
                p = Path(root) / f
                try:
                    rel = str(p.relative_to(self.workspace_root)).replace("\\", "/")
                    results.append({
                        "name": f,
                        "rel_path": rel,
                        "ext": p.suffix,
                        "size": p.stat().st_size
                    })
                    if len(results) >= max_files:
                        return results
                except Exception:
                    continue
        return results

    def _discover_module_tree(self) -> Dict[str, List[str]]:
        """Maps top-level directories to their sub-components."""
        modules = {}
        for entry in self.workspace_root.iterdir():
            if entry.is_dir() and entry.name not in self.IGNORE_DIRS and not entry.name.startswith("."):
                sub_items = []
                for sub in entry.iterdir():
                    if sub.name not in self.IGNORE_DIRS and not sub.name.startswith("."):
                        sub_items.append(sub.name)
                modules[entry.name] = sub_items[:15]
        return modules

    def _detect_frameworks(self, manifests: Dict[str, str], files: List[Dict[str, Any]]) -> List[str]:
        detected = []
        combined_manifest = "\n".join(manifests.values()).lower()
        file_str = "\n".join(f["rel_path"].lower() for f in files)

        for fw, sigs in self.FRAMEWORK_PATTERNS.items():
            if any(s.lower() in combined_manifest or s.lower() in file_str for s in sigs):
                detected.append(fw)
        return detected

    @staticmethod
    def _ext_to_lang(ext: str) -> Optional[str]:
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".html": "html",
            ".css": "css",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".sql": "sql",
            ".sh": "shell",
            ".bat": "batch"
        }
        return mapping.get(ext)
