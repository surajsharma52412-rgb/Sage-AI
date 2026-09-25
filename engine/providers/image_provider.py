"""
Image Generation Provider for Sage AI.
Workflow:
User asks for image
       ↓
Check remaining free credits
       ↓
 ┌─────┴─────┐
 ↓           ↓
Available   Not available
 ↓           ↓
Black Forest Stop
FLUX.1       + tell user
Generate
image
"""
import time
import base64
import re
import urllib.parse
import requests
import logging
from typing import List, Dict, Any, Optional, Callable
from .base_provider import BaseProvider, ProviderResponse
from database.db_manager import get_db
from config import DEFAULT_MODELS

logger = logging.getLogger(__name__)


class ImageProvider(BaseProvider):
    """
    Credit-gated Image Generation Provider using Black Forest Labs FLUX.1.
    """

    def __init__(self):
        super().__init__("image", "Black Forest Labs FLUX.1")

    def get_remaining_credits(self) -> int:
        """Checks remaining free credits from database quota."""
        db = get_db()
        quota = db.get_provider_quota("image")
        if quota and "remaining_amount" in quota:
            return int(quota["remaining_amount"])

        # Initialize default quota if not set yet
        init_credits = int(db.get_setting("image_free_credits", DEFAULT_MODELS.get("image_free_credits", 25)))
        db.save_provider_quota("image", {
            "total_limit": float(init_credits),
            "used_amount": 0.0,
            "remaining_amount": float(init_credits),
            "currency_or_unit": "Credits",
            "is_free_tier": True,
            "details": {"model": "black-forest-labs/FLUX.1-schnell"}
        })
        return init_credits

    def consume_credit(self) -> int:
        """Deducts 1 credit from user balance and returns new remaining count."""
        db = get_db()
        current = self.get_remaining_credits()
        new_remaining = max(0, current - 1)
        used = max(0, 25 - new_remaining)

        quota = db.get_provider_quota("image")
        if quota:
            used = float(quota.get("used_amount", 0.0)) + 1.0

        db.save_provider_quota("image", {
            "total_limit": 25.0,
            "used_amount": float(used),
            "remaining_amount": float(new_remaining),
            "currency_or_unit": "Credits",
            "is_free_tier": True,
            "details": {"model": "black-forest-labs/FLUX.1-schnell"}
        })
        db.set_setting("image_remaining_credits", str(new_remaining))
        return new_remaining

    def refill_credits(self, amount: int = 25) -> int:
        """Refills free credits allowance."""
        db = get_db()
        db.save_provider_quota("image", {
            "total_limit": float(amount),
            "used_amount": 0.0,
            "remaining_amount": float(amount),
            "currency_or_unit": "Credits",
            "is_free_tier": True,
            "details": {"model": "black-forest-labs/FLUX.1-schnell"}
        })
        db.set_setting("image_remaining_credits", str(amount))
        return amount

    def is_available(self) -> bool:
        """Available if user has at least 1 credit remaining."""
        return self.get_remaining_credits() > 0

    def _clean_prompt(self, raw_prompt: str) -> str:
        """
        Cleans conversational prefixes like 'make piture of universe'
        into a clean diffusion prompt: 'universe'.
        """
        cleaned = raw_prompt.strip()
        # Regex to strip command prefixes
        pattern = (
            r"^(?:please\s+)?(?:generate|create|make|draw|paint|render|illustrate|show\s+me|give\s+me)"
            r"\s+(?:an?\s+|the\s+)?(?:picture|piture|image|photo|artwork|wallpaper|drawing|painting|pic|pics)?"
            r"\s*(?:of|about|showing|depicting)?\s*"
        )
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
        # Clean trailing punctuation like dots or exclamation
        cleaned = re.sub(r"[.!?]+$", "", cleaned).strip()
        return cleaned if cleaned else raw_prompt.strip()

    def generate(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> ProviderResponse:
        """
        Step 1: Check remaining free credits
        Step 2: If available -> Generate via Black Forest FLUX.1 & deduct credit
        Step 3: If not available -> Stop & inform user
        """
        start_time = time.time()
        clean_subject = self._clean_prompt(prompt)

        # -------------------------------------------------------------
        # STEP 1: Check remaining free credits
        # -------------------------------------------------------------
        remaining_credits = self.get_remaining_credits()

        # -------------------------------------------------------------
        # STEP 2 (BRANCH B): Credits NOT available -> Stop + tell user
        # -------------------------------------------------------------
        if remaining_credits <= 0:
            latency = (time.time() - start_time) * 1000
            error_message = (
                f"### ⚠️ Free Image Credits Exhausted\n\n"
                f"> **You have 0 free image generation credits remaining.**\n\n"
                f"#### How to continue:\n"
                f"1. Open **Settings (⚙️) ➔ Local & Image AI** and click **🔄 Refill Free Credits (+25)** to instantly reload your allowance.\n"
                f"2. Or add your personal Hugging Face API key in **Add AI Models** for unlimited high-speed generations.\n\n"
                f"*Request stopped: \"{prompt}\"*"
            )
            return ProviderResponse(
                text=error_message,
                model_name="Black Forest FLUX.1 (Credits Exhausted)",
                provider_id=self.provider_id,
                success=False,
                error_msg="Free image credits exhausted",
                latency_ms=latency,
                is_image=False
            )

        # -------------------------------------------------------------
        # STEP 2 (BRANCH A): Credits Available -> Black Forest FLUX.1
        # -------------------------------------------------------------
        # Try Black Forest Labs FLUX.1 generation
        img_bytes = self._generate_flux_image(clean_subject)

        if img_bytes:
            # Deduct 1 free credit upon successful generation
            new_remaining = self.consume_credit()
            latency = (time.time() - start_time) * 1000
            b64_img = base64.b64encode(img_bytes).decode("utf-8")

            success_text = (
                f"### 🎨 Generated Picture: *\"{clean_subject}\"*\n\n"
                f"Rendered with **Black Forest Labs FLUX.1** (12B Flow Transformer Neural Engine).\n\n"
                f"- **Model:** `black-forest-labs/FLUX.1-schnell`\n"
                f"- **Resolution:** 1024 × 1024 High-Definition\n"
                f"- 💳 **Remaining Free Credits:** **{new_remaining}** credits left"
            )

            return ProviderResponse(
                text=success_text,
                model_name="Black Forest FLUX.1 (Hugging Face)",
                provider_id=self.provider_id,
                success=True,
                latency_ms=latency,
                is_image=True,
                image_data=b64_img,
                metadata={
                    "model": "black-forest-labs/FLUX.1-schnell",
                    "remaining_credits": new_remaining,
                    "prompt": clean_subject
                }
            )

        # Fallback to local procedural canvas if network unavailable
        latency = (time.time() - start_time) * 1000
        return self._build_offline_canvas(clean_subject, latency, remaining_credits)

    def _generate_flux_image(self, clean_prompt: str) -> Optional[bytes]:
        """
        Generates image bytes using Black Forest Labs FLUX.1 (via Pollinations / HF Inference).
        """
        db = get_db()
        hf_key = db.get_setting("huggingface_api_key", "")

        # 1. First attempt: Hugging Face Router endpoint if key is present
        if hf_key:
            try:
                hf_url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
                headers = {"Authorization": f"Bearer {hf_key}"}
                resp = requests.post(
                    hf_url,
                    headers=headers,
                    json={"inputs": clean_prompt},
                    timeout=20
                )
                if resp.status_code == 200 and len(resp.content) > 1000 and "image" in resp.headers.get("content-type", ""):
                    return resp.content
            except Exception as e:
                logger.warning("HF Router FLUX.1 call failed: %s", e)

        # 2. Primary / Fast Black Forest Labs FLUX.1 endpoint (100% Free, High Definition)
        try:
            encoded_prompt = urllib.parse.quote(clean_prompt)
            flux_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=flux&width=1024&height=1024&nologo=true"
            resp = requests.get(flux_url, timeout=35)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return resp.content
        except Exception as e:
            logger.warning("Black Forest FLUX.1 Pollinations endpoint error: %s", e)

        # 3. High-speed SDXL Turbo backup
        try:
            encoded_prompt = urllib.parse.quote(clean_prompt)
            turbo_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=turbo&width=768&height=768&nologo=true"
            resp = requests.get(turbo_url, timeout=20)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return resp.content
        except Exception as e:
            logger.warning("Turbo fallback error: %s", e)

        return None

    def _build_offline_canvas(self, prompt: str, latency: float, remaining: int) -> ProviderResponse:
        """
        Procedurally creates an offline artistic preview card if network is disconnected.
        """
        try:
            from PySide6.QtGui import QImage, QPainter, QColor, QLinearGradient, QFont
            from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt, QRect

            img = QImage(768, 512, QImage.Format_RGB32)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.Antialiasing)

            # Cosmic gradient background
            grad = QLinearGradient(0, 0, 768, 512)
            grad.setColorAt(0.0, QColor(8, 11, 22))
            grad.setColorAt(0.5, QColor(16, 24, 48))
            grad.setColorAt(1.0, QColor(12, 18, 36))
            painter.fillRect(0, 0, 768, 512, grad)

            # Emerald glowing accent border
            painter.setPen(QColor(15, 230, 181, 140))
            painter.drawRoundedRect(12, 12, 744, 488, 16, 16)

            # Title
            painter.setPen(QColor(15, 230, 181))
            font = QFont("Segoe UI", 20, QFont.Bold)
            painter.setFont(font)
            painter.drawText(QRect(30, 40, 708, 40), Qt.AlignLeft, "🎨 Black Forest Labs FLUX.1")

            # Subtitle
            painter.setPen(QColor(168, 175, 194))
            font_sub = QFont("Segoe UI", 12)
            painter.setFont(font_sub)
            painter.drawText(QRect(30, 85, 708, 30), Qt.AlignLeft, "Offline Canvas Mode • Check your internet connection")

            # User prompt in central highlight box
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(25, 35, 65, 180))
            painter.drawRoundedRect(30, 140, 708, 160, 12, 12)

            painter.setPen(QColor(244, 245, 251))
            font_prompt = QFont("Segoe UI", 14, QFont.DemiBold)
            painter.setFont(font_prompt)
            painter.drawText(QRect(50, 160, 668, 120), Qt.AlignLeft | Qt.TextWordWrap, f"\"{prompt}\"")

            # Footer status
            painter.setPen(QColor(15, 230, 181))
            font_footer = QFont("Segoe UI", 11)
            painter.setFont(font_footer)
            painter.drawText(QRect(30, 440, 708, 30), Qt.AlignLeft, f"💳 Free Credits: {remaining} remaining • Reconnect internet for full neural render")

            painter.end()

            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            img.save(buf, "PNG")
            b64_img = base64.b64encode(ba.data()).decode("utf-8")

            return ProviderResponse(
                text=(
                    f"### 🎨 Picture Canvas: *\"{prompt}\"*\n\n"
                    f"Network is currently offline. A local visual canvas was generated.\n\n"
                    f"💳 **Remaining Free Credits:** **{remaining}** credits"
                ),
                model_name="Black Forest FLUX.1 (Offline Canvas)",
                provider_id=self.provider_id,
                success=True,
                latency_ms=latency,
                is_image=True,
                image_data=b64_img
            )
        except Exception as e:
            return ProviderResponse(
                text=f"### Image Generation Failed: {e}",
                model_name="Black Forest FLUX.1",
                provider_id=self.provider_id,
                success=False,
                error_msg=str(e),
                latency_ms=latency,
                is_image=False
            )
