"""
Agent Planner for Autonomous Project Coding Agent.
Interacts with the coding LLM to generate structured, validated JSON operations plans.
"""
import json
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

from engine.router import FallbackRouter
from .workspace_inspector import WorkspaceInspector, WorkspaceSecurityError


PLAN_SCHEMA_PROMPT = """
You are the Autonomous Coding Agent of Sage AI.
Analyze the user's task and workspace manifest, then produce a SINGLE JSON response specifying the exact file operations to fulfill the request.

Your response MUST be valid JSON conforming EXACTLY to this schema:
{
  "summary": "High level explanation of the changes made",
  "operations": [
    {
      "op": "write",
      "path": "relative/path/to/file.ext",
      "content": "Full complete file content to be written"
    },
    {
      "op": "delete",
      "path": "relative/path/to/obsolete.ext",
      "content": ""
    }
  ],
  "notes": [
    "Important architectural note 1",
    "Instructions to run tests"
  ]
}

CRITICAL RULES:
1. Do NOT wrap the JSON in Markdown code fences if possible, or output only valid JSON.
2. Every "op" must be either "write" or "delete".
3. "path" must be relative to the workspace root without leading slashes or ".." parent traversals.
4. "content" for "write" must be the complete, updated file content (never use placeholders like '...rest of code...').
5. Ensure valid syntax and write tests where appropriate.
"""


class AgentPlanner:
    """Generates and validates structured JSON implementation plans."""

    def __init__(self, router: Optional[FallbackRouter] = None):
        self.router = router or FallbackRouter()

    def generate_plan(
        self,
        inspector: WorkspaceInspector,
        task_instruction: str,
        repair_context: Optional[str] = None,
        selected_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Builds prompt with workspace context, queries coding LLM, and parses JSON plan.
        """
        tree_view = inspector.get_tree_view()
        manifest = inspector.scan_manifest(max_files=50)
        
        # Read small relevant files if available
        sample_files = {}

        # Prioritize explicit target file mentioned in instruction (e.g. Target File: styles.css)
        target_match = re.search(r"Target File:\s*([^\r\n]+)", task_instruction, re.IGNORECASE)
        if target_match:
            target_name = target_match.group(1).strip()
            try:
                target_path = inspector.resolve_safe_path(target_name)
                if target_path.is_file():
                    content = inspector.read_file(target_name, max_bytes=10000)
                    if content is not None:
                        sample_files[target_name] = content
            except Exception:
                pass

        for item in manifest[:5]:
            if not item["is_binary"] and item["size"] < 15000:
                if item["path"] not in sample_files:
                    content = inspector.read_file(item["path"], max_bytes=4000)
                    if content:
                        sample_files[item["path"]] = content

        prompt_parts = [
            f"### Task Description:\n{task_instruction}\n",
            f"### Current Workspace Tree:\n```\n{tree_view}\n```\n",
        ]

        if sample_files:
            prompt_parts.append("### Relevant Existing Files Sample:\n")
            for path, text in sample_files.items():
                prompt_parts.append(f"--- File: {path} ---\n{text}\n")

        if repair_context:
            prompt_parts.append(
                f"### Self-Repair Information (Previous Attempt Failed):\n"
                f"The previous operations resulted in test or execution errors:\n"
                f"```\n{repair_context}\n```\n"
                f"Analyze this error and output a corrected JSON plan that fixes the bug.\n"
            )

        full_prompt = "\n".join(prompt_parts)

        # Execute with selected model preference or Auto Router waterfall
        model_to_use = selected_model if (selected_model and "auto" not in selected_model.lower()) else "Auto Router"
        resp = self.router.route_and_execute(
            prompt=full_prompt,
            system_prompt=PLAN_SCHEMA_PROMPT,
            selected_model=model_to_use
        )

        if not resp.success:
            err_msg = resp.error_msg or "AI Model failed to respond."
            return self._fallback_plan(
                f"AI Provider Error ({resp.provider_id or 'Router'}): {err_msg}",
                resp.text or err_msg
            )

        # Handle case where router fell back to local offline assistant
        if resp.provider_id == "local_facts" or "Offline Assistant Mode" in resp.text:
            return self._fallback_plan(
                "No AI coding provider connected. Cloud APIs (Groq, OpenRouter, NVIDIA, Gemini) are unconfigured and Ollama is offline. Open '✨ Add AI Models' to connect an active AI provider.",
                resp.text
            )

        plan = self._parse_and_validate_json(resp.text, inspector)
        return plan

    def _parse_and_validate_json(self, response_text: str, inspector: WorkspaceInspector) -> Dict[str, Any]:
        """Extracts JSON object from LLM response and validates operations schema."""
        raw_text = response_text.strip()
        
        # Strip thinking tags if present (e.g. from reasoning models like DeepSeek-R1)
        from ui.components.message_bubble import extract_thinking
        _, clean_text = extract_thinking(raw_text)
        if clean_text:
            raw_text = clean_text.strip()
        
        # Strip code fences if present
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
        if fence_match:
            candidate = fence_match.group(1).strip()
        else:
            curly_match = re.search(r"\{[\s\S]*\}", raw_text)
            candidate = curly_match.group(0).strip() if curly_match else raw_text

        data = None
        parse_err = None

        # Tier 1: Direct parse
        try:
            data = json.loads(candidate, strict=False)
        except Exception as e:
            parse_err = e

        # Tier 2: Fix invalid backslash escape sequences in code/CSS
        if data is None:
            try:
                fixed_escapes = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', candidate)
                data = json.loads(fixed_escapes, strict=False)
            except Exception as e:
                parse_err = e

        # Tier 3: Strip trailing commas before closing braces/brackets
        if data is None:
            try:
                fixed_commas = re.sub(r',\s*([\}\]])', r'\1', fixed_escapes)
                data = json.loads(fixed_commas, strict=False)
            except Exception as e:
                parse_err = e

        if not isinstance(data, dict):
            return self._fallback_plan(f"Failed to parse LLM JSON: {str(parse_err or 'Not a JSON object')}", response_text)

        # Validate Schema
        summary = str(data.get("summary", "Automated plan execution"))
        raw_ops = data.get("operations", [])
        validated_ops = []

        for op in raw_ops:
            op_type = str(op.get("op", "")).lower()
            if op_type not in ["write", "delete"]:
                continue

            rel_path = str(op.get("path", "")).strip()
            if not rel_path:
                continue

            # Verify path safety against traversal
            try:
                inspector.resolve_safe_path(rel_path)
            except WorkspaceSecurityError:
                continue

            content = str(op.get("content", ""))
            validated_ops.append({
                "op": op_type,
                "path": rel_path,
                "content": content
            })

        notes = [str(n) for n in data.get("notes", [])]

        return {
            "summary": summary,
            "operations": validated_ops,
            "notes": notes,
            "raw_response": response_text
        }

    def _fallback_plan(self, reason: str, raw_text: str) -> Dict[str, Any]:
        return {
            "summary": f"Fallback Plan ({reason})",
            "operations": [],
            "notes": [f"Could not parse valid JSON plan from LLM output. Raw snippet: {raw_text[:200]}..."],
            "raw_response": raw_text
        }
