"""
Local Facts & Knowledge Base Provider for Sage AI (Lunar Engine).
Delivers instantaneous, zero-latency local answers for system time, math, currency,
and built-in offline technical knowledge.
"""
import time
import json
import re
import ast
import operator
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

from .base_provider import BaseProvider, ProviderResponse
from config import KNOWLEDGE_BASE_PATH


# Safe math evaluator
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}

def safe_eval_math(expr: str) -> Optional[float]:
    """Safely evaluates a mathematical expression without eval()."""
    clean = re.sub(r"[^0-9\+\-\*\/\(\)\.\^\%]", "", expr.replace("^", "**"))
    if not clean:
        return None

    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                return SAFE_OPERATORS[op_type](left, right)
            raise ValueError(f"Unsupported operator: {op_type}")
        elif isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                return SAFE_OPERATORS[op_type](operand)
            raise ValueError(f"Unsupported operator: {op_type}")
        raise ValueError("Unsupported AST node")

    try:
        tree = ast.parse(clean, mode='eval')
        return _eval(tree.body)
    except Exception:
        return None


class LocalFactsProvider(BaseProvider):
    """Answers local system questions, math, currency, and offline knowledge."""

    def __init__(self):
        super().__init__("local_facts", "Sage Local Knowledge")
        self.knowledge_base = self._load_knowledge_base()

    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        if KNOWLEDGE_BASE_PATH.exists():
            try:
                with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        if "facts" in data and isinstance(data["facts"], list):
                            return data["facts"]
                        return list(data.values())
                    elif isinstance(data, list):
                        return data
            except Exception:
                pass
        return []

    def is_available(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> ProviderResponse:
        start_time = time.time()
        lower_prompt = prompt.strip().lower()

        # 0. Friendly Greetings
        if re.match(r"^(hi|hello|hey|yoo+|yo|greetings|howdy|sup)\b", lower_prompt):
            greeting_text = (
                "👋 **Hello! Welcome to Sage AI.**\n\n"
                "I am your multi-agentic AI desktop assistant powered by the Lunar Engine.\n\n"
                "Here are a few things we can do together:\n"
                "- 💻 **Code & Debug**: Ask coding questions in Python, JavaScript, C++, Rust, and more.\n"
                "- 🚀 **Autonomous Projects**: Switch to the **Projects** tab to plan, generate, and test complete codebases.\n"
                "- 🌐 **Live Web Search**: Toggle **Web Search** to extract real-time information with citations.\n"
                "- ⚡ **Multi-Model Intelligence**: Powered by Groq, NVIDIA NIM, Google Gemini, OpenRouter, or private local Ollama.\n"
                "- 📚 **Offline Reference**: Type `cheatsheet` or ask about system time, math, currency, and tech guides anytime!\n\n"
                "How can I help you today?"
            )
            latency = (time.time() - start_time) * 1000
            if on_chunk:
                on_chunk(greeting_text)
            return ProviderResponse(
                text=greeting_text,
                model_name="Sage Instant Assistant",
                provider_id=self.provider_id,
                latency_ms=latency
            )

        # 0b. Permanent Creator & Founder Queries (Suraj Sharma)
        if any(phrase in lower_prompt for phrase in [
            "who created you", "who is your creator", "who made you", "who built you",
            "who is the creator", "who developed you", "who is your developer",
            "who built sage", "who created sage", "who made sage", "who designed you",
            "who is suraj", "who is suraj sharma", "suraj sharma"
        ]):
            creator_text = (
                "### 🌟 Creator & Lead Developer Information\n\n"
                "**Sage AI (Lunar Engine)** was created, founded, and developed by **Suraj Sharma**.\n\n"
                "- **Creator & Founder:** Suraj Sharma\n"
                "- **Project:** Sage AI\n"
                "- **Engine:** Lunar Multi-Agent Engine\n"
                "- **Status:** Permanent and immutable creator\n\n"
                "Suraj Sharma designed Sage AI to be an exceptionally fast, user-friendly, and powerful autonomous AI desktop workspace."
            )
            latency = (time.time() - start_time) * 1000
            if on_chunk:
                on_chunk(creator_text)
            return ProviderResponse(
                text=creator_text,
                model_name="Sage Creator Identity",
                provider_id=self.provider_id,
                latency_ms=latency
            )

        # 1. System time / date
        if any(term in lower_prompt for term in ["time", "date", "clock", "today"]):
            now = datetime.now()
            time_str = now.strftime("%I:%M:%S %p")
            date_str = now.strftime("%A, %B %d, %Y")
            tz_str = now.astimezone().tzname() or "Local"

            resp_text = (
                f"### System Chronometer (Local)\n\n"
                f"- **Current Time:** `{time_str}` ({tz_str})\n"
                f"- **Current Date:** `{date_str}`\n"
                f"- **ISO-8601:** `{now.isoformat()}`"
            )
            latency = (time.time() - start_time) * 1000
            if on_chunk:
                on_chunk(resp_text)
            return ProviderResponse(
                text=resp_text,
                model_name="Local System Time",
                provider_id=self.provider_id,
                latency_ms=latency
            )

        # 2. Math calculation
        math_match = re.search(r"(?:calculate|compute|what is|eval)?\s*([0-9\.\s\+\-\*\/\(\)\^\%]{3,})", lower_prompt)
        if math_match:
            candidate = math_match.group(1).strip()
            result = safe_eval_math(candidate)
            if result is not None:
                formatted_res = f"{result:g}"
                resp_text = (
                    f"### Mathematical Computation\n\n"
                    f"$$\n{candidate} = {formatted_res}\n$$\n\n"
                    f"**Result:** `{formatted_res}`"
                )
                latency = (time.time() - start_time) * 1000
                if on_chunk:
                    on_chunk(resp_text)
                return ProviderResponse(
                    text=resp_text,
                    model_name="Local Math Engine",
                    provider_id=self.provider_id,
                    latency_ms=latency
                )

        # 3. Currency conversion estimate
        curr_match = re.search(r"convert\s+(\d+(?:\.\d+)?)\s*([a-z]{3})\s+to\s+([a-z]{3})", lower_prompt)
        if curr_match:
            amount = float(curr_match.group(1))
            from_c = curr_match.group(2).upper()
            to_c = curr_match.group(3).upper()

            # Baseline rates against USD
            rates_to_usd = {
                "USD": 1.0,
                "EUR": 1.08,
                "GBP": 1.28,
                "INR": 0.012,
                "JPY": 0.0067,
                "CAD": 0.74,
                "AUD": 0.66,
            }

            if from_c in rates_to_usd and to_c in rates_to_usd:
                in_usd = amount * rates_to_usd[from_c]
                target_amount = in_usd / rates_to_usd[to_c]
                resp_text = (
                    f"### Currency Conversion (Approximate Rate)\n\n"
                    f"- **Input:** `{amount:,.2f} {from_c}`\n"
                    f"- **Estimated Output:** `{target_amount:,.2f} {to_c}`\n\n"
                    f"> *Note: Currency conversion uses local reference rates. Enable Web Search (`🌐 Web`) for real-time live forex rates.*"
                )
                latency = (time.time() - start_time) * 1000
                if on_chunk:
                    on_chunk(resp_text)
                return ProviderResponse(
                    text=resp_text,
                    model_name="Local Currency Converter",
                    provider_id=self.provider_id,
                    latency_ms=latency
                )

        # 4. Catalog request (e.g. "Show me cheatsheets", "knowledge base", "help")
        if any(kw in lower_prompt for kw in ["cheatsheet", "cheat sheet", "knowledge base", "offline facts", "what can you do offline", "offline guide", "list guides"]):
            lines = [
                "### 📚 Sage AI Local Knowledge Base & Cheatsheets\n",
                "Here are all available built-in offline technical guides and cheatsheets:\n"
            ]
            for fact in self.knowledge_base:
                title = fact.get("title", "Guide")
                tags = ", ".join(fact.get("tags", [])[:3])
                lines.append(f"- **{title}** (`{tags}`)")
            lines.append("\n*Tip: Simply ask for any topic above (e.g. `Python cheatsheet` or `Git commands`) for the full offline guide.*")
            resp_text = "\n".join(lines)
            latency = (time.time() - start_time) * 1000
            if on_chunk:
                on_chunk(resp_text)
            return ProviderResponse(
                text=resp_text,
                model_name="Local Knowledge Base Catalog",
                provider_id=self.provider_id,
                citations=[{"title": "Local Knowledge Base", "url": "local://knowledge_base.json"}],
                latency_ms=latency
            )

        # 5. Knowledge Base Item Match
        for fact in self.knowledge_base:
            keywords = fact.get("keywords", []) or fact.get("tags", [])
            title_lower = fact.get("title", "").lower()
            if any(kw in lower_prompt for kw in keywords) or title_lower in lower_prompt or any(len(w) > 3 and w in lower_prompt for w in title_lower.split()):
                resp_text = f"## {fact.get('title')}\n\n{fact.get('content')}"
                latency = (time.time() - start_time) * 1000
                if on_chunk:
                    on_chunk(resp_text)
                return ProviderResponse(
                    text=resp_text,
                    model_name="Local Knowledge Base",
                    provider_id=self.provider_id,
                    citations=[{"title": fact.get("title", "KB"), "url": "local://knowledge_base.json"}],
                    latency_ms=latency
                )

        # 6. Default local offline assistant fallback
        fallback_text = (
            f"### Sage AI (Offline Assistant Mode)\n\n"
            f"You asked: *\"{prompt}\"*\n\n"
            "Currently, all external cloud provider API keys (Groq, OpenRouter, NVIDIA, Gemini) are unconfigured, "
            "and local Ollama was not detected on `http://127.0.0.1:11434`.\n\n"
            "#### Quick Setup Options:\n"
            "1. **Cloud APIs**: Click **Add AI Models (✨)** in the sidebar to enter your free API key for Groq, Gemini, NVIDIA NIM, or OpenRouter.\n"
            "2. **Local Ollama**: Start Ollama (`ollama serve`) and pull a model such as `ollama run llama3.2:3b`.\n"
            "3. **Local Tools**: You can ask for current time, math calculations (e.g. `25 * 40`), git cheatsheet, Python reference, or type `cheatsheet` to view all offline guides!"
        )
        latency = (time.time() - start_time) * 1000
        if on_chunk:
            on_chunk(fallback_text)
        return ProviderResponse(
            text=fallback_text,
            model_name="Sage Local Fallback",
            provider_id=self.provider_id,
            latency_ms=latency
        )
