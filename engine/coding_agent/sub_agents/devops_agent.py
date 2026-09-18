"""
DevOps Agent for SAGE Coding Agent Architecture (v6).
Responsibilities:
- Containerization (Dockerfile, docker-compose.yml)
- CI/CD Pipelines (GitHub Actions workflows)
- Environment configuration & templates (.env.example)
- Cloud deployment configurations & reverse proxy setup (Nginx)
- Health check endpoints and service monitoring
"""
import logging
from typing import Dict, Any, List, Optional, Callable

from .base_sub_agent import BaseSubAgent

logger = logging.getLogger(__name__)


class DevOpsAgent(BaseSubAgent):
    """Specialized in Docker, CI/CD, cloud infrastructure, and deployment setups."""

    def __init__(self, context_mgr, tools, model_router=None):
        super().__init__(role="devops", name="DevOps Agent", context_mgr=context_mgr, tools=tools, model_router=model_router)

    def execute(
        self,
        task: Dict[str, Any],
        dep_context: Dict[str, Any],
        llm_caller_fn: Optional[Callable[..., Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        instruction = task.get("instruction", "")

        system_prompt = (
            "You are Sage AI's Principal DevOps & Site Reliability Engineer. "
            "Generate production-ready container definitions, docker-compose setups, CI/CD automation, and environment configs. "
            "Specify files clearly in markdown code fences, e.g.:\n"
            "```dockerfile file:Dockerfile\n# Dockerfile\n```\n"
            "```yaml file:docker-compose.yml\n# Compose\n```\n"
            "```env file:.env.example\n# Environment variables\n```"
        )

        prompt = (
            f"DevOps Task: {instruction}\n\n"
            "Generate complete deployment configurations including Dockerfile, docker-compose.yml, .env.example, and CI workflow."
        )

        llm_res = self.call_llm(prompt=prompt, system_prompt=system_prompt, llm_caller_fn=llm_caller_fn)
        content_text = llm_res.get("text", "")
        extracted_files = self.extract_code_blocks(content_text)

        if not extracted_files:
            dockerfile = (
                "FROM python:3.11-slim\n"
                "WORKDIR /app\n"
                "COPY requirements.txt* ./\n"
                "RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi\n"
                "COPY . .\n"
                "EXPOSE 8000\n"
                "CMD [\"python\", \"backend/server.py\"]\n"
            )
            extracted_files.append({"language": "dockerfile", "path": "Dockerfile", "content": dockerfile})

            compose = (
                "version: '3.8'\n"
                "services:\n"
                "  app:\n"
                "    build: .\n"
                "    ports:\n"
                "      - \"8000:8000\"\n"
                "    environment:\n"
                "      - PORT=8000\n"
                "      - APP_ENV=production\n"
                "    restart: unless-stopped\n"
            )
            extracted_files.append({"language": "yaml", "path": "docker-compose.yml", "content": compose})

            env_example = (
                "# Application Environment Configuration\n"
                "PORT=8000\n"
                "APP_ENV=development\n"
                "SECRET_KEY=change_this_to_a_secure_random_key_in_production\n"
                "DATABASE_URL=sqlite:///./app.db\n"
            )
            extracted_files.append({"language": "env", "path": ".env.example", "content": env_example})

        return {
            "success": True,
            "role": self.role,
            "agent_name": self.name,
            "summary": content_text or "DevOps deployment scripts and container configurations generated.",
            "generated_files": extracted_files
        }
