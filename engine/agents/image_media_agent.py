"""
Image / Media Agent for Sage Multi-Agentic AI Architecture.
Capabilities:
- Generate images
- Edit images
- Create diagrams (Mermaid / SVG)
- Design UI/UX
- Generate videos (if supported)
- Create charts & visuals
"""
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from config import AGENT_IMAGE_MEDIA
from .base_agent import BaseAgent
from engine.providers.image_provider import ImageProvider
from engine.photo_agent.autonomous_photo_agent import AutonomousPhotoAgent


class ImageMediaAgent(BaseAgent):
    """Specialized in visual media generation, diagrams, UI/UX designs, and charts."""

    def __init__(self):
        super().__init__(name=AGENT_IMAGE_MEDIA, role_id="image_media")
        self.image_provider = ImageProvider()
        ws_root = getattr(self.workspace, "root_path", None) if hasattr(self, "workspace") else None
        self.photo_agent = AutonomousPhotoAgent(workspace_root=ws_root)

    def execute(
        self,
        task_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        instruction = task_input.get("instruction") or task_input.get("query") or ""
        media_type = task_input.get("media_type", "image")  # "image", "diagram", "ui_ux", "photo_library"
        task_id = (context or {}).get("task_id")
        inst_lower = instruction.lower()

        # Check for photo library tasks
        if any(k in inst_lower for k in ("photo library", "organize photos", "dedupe photos", "photo album")) or media_type in ("photo_library", "photos"):
            return self._execute_photo_task(task_input, instruction, task_id, on_stage)
        elif "diagram" in inst_lower or "flowchart" in inst_lower or "architecture" in inst_lower or media_type == "diagram":
            return self._generate_diagram(instruction, task_id, on_stage, on_chunk)
        elif "ui" in inst_lower or "mockup" in inst_lower or "ux" in inst_lower or media_type == "ui_ux":
            return self._generate_ui_ux(instruction, task_id, on_stage, on_chunk)
        else:
            return self._generate_image(instruction, task_id, on_stage)

    def _execute_photo_task(
        self,
        task_input: Dict[str, Any],
        instruction: str,
        task_id: Optional[str] = None,
        on_stage: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        if on_stage:
            on_stage("📷 Image / Media Agent: Executing autonomous photo library task...")
        self.log("Executing photo library task", task_id=task_id, details={"instruction": instruction})

        library_folder = task_input.get("library_folder") or task_input.get("folder") or str(Path.cwd())
        res = self.photo_agent.execute_task(
            library_folder=library_folder,
            task_instruction=instruction
        )
        return {
            "success": res.get("success", False),
            "agent": self.name,
            "summary": res.get("final_review", {}).get("summary", "Photo task completed."),
            "result": res,
            "deliverables": [
                {
                    "type": "photo_review_report",
                    "title": f"Photo Task: {instruction[:30]}",
                    "content": res.get("final_review", {}).get("summary", ""),
                    "data": res
                }
            ]
        }

    def _generate_image(
        self,
        prompt: str,
        task_id: Optional[str] = None,
        on_stage: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        if on_stage:
            on_stage("🖼️ Image / Media Agent: Rendering visual image...")
        self.log("Rendering visual image", task_id=task_id, details={"prompt": prompt})

        resp = self.image_provider.generate(prompt)

        self.send_bus_message(
            to_agent="all",
            message_type="image_rendered",
            content=f"Rendered image for: '{prompt[:40]}...'",
            task_id=task_id
        )

        return {
            "success": resp.success,
            "agent": self.name,
            "summary": resp.text,
            "is_image": resp.is_image,
            "image_data": resp.image_data,
            "deliverables": [
                {
                    "type": "image" if resp.is_image else "text",
                    "title": f"Visual Render: {prompt[:30]}" if resp.is_image else "Image Status",
                    "content": resp.text,
                    "image_data": resp.image_data
                }
            ]
        }

    def _generate_diagram(
        self,
        instruction: str,
        task_id: Optional[str] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        if on_stage:
            on_stage("🖼️ Image / Media Agent: Formulating technical diagram (Mermaid/SVG)...")
        self.log("Formulating technical diagram", task_id=task_id, details={"instruction": instruction})

        system_prompt = (
            "You are Sage AI's Image / Media Agent specialized in technical diagrams. "
            "Output clear, structured diagrams using Mermaid code blocks (```mermaid ... ```) "
            "or clean SVG diagrams along with an architectural explanation."
        )

        prompt = f"Create a clear technical diagram for: {instruction}"
        llm_res = self.call_llm(prompt=prompt, system_prompt=system_prompt, on_chunk=on_chunk)
        text = llm_res.get("text", "")

        return {
            "success": True,
            "agent": self.name,
            "summary": text,
            "is_diagram": True,
            "deliverables": [
                {
                    "type": "diagram",
                    "title": f"Diagram: {instruction[:40]}",
                    "content": text
                }
            ]
        }

    def _generate_ui_ux(
        self,
        instruction: str,
        task_id: Optional[str] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        if on_stage:
            on_stage("🖼️ Image / Media Agent: Designing UI/UX mockup & styling...")
        self.log("Designing UI/UX component", task_id=task_id, details={"instruction": instruction})

        system_prompt = (
            "You are Sage AI's Image / Media Agent specialized in modern UI/UX design. "
            "Provide modern design tokens (color palette, typography, glassmorphic layout) "
            "and clean HTML/CSS wireframes or QSS component designs."
        )

        prompt = f"Design a state-of-the-art UI/UX layout for: {instruction}"
        llm_res = self.call_llm(prompt=prompt, system_prompt=system_prompt, on_chunk=on_chunk)
        text = llm_res.get("text", "")

        return {
            "success": True,
            "agent": self.name,
            "summary": text,
            "is_ui_ux": True,
            "deliverables": [
                {
                    "type": "ui_ux_design",
                    "title": f"UI/UX Design: {instruction[:40]}",
                    "content": text
                }
            ]
        }
