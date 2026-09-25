"""
Search Provider for Sage AI.
Extracts real-time web evidence using Tavily API with DuckDuckGo fallback.
"""
import time
import os
import re
import urllib.parse
import requests
from typing import List, Dict, Any, Optional, Callable
from .base_provider import BaseProvider, ProviderResponse
from database.db_manager import get_db
from config import DEFAULT_MODELS


class SearchProvider(BaseProvider):
    """Web Search Provider with Tavily primary and DuckDuckGo fallback."""

    TAVILY_ENDPOINT = DEFAULT_MODELS["tavily_api_url"]

    def __init__(self):
        super().__init__("search", "Web Search Engine")

    def _get_tavily_key(self) -> Optional[str]:
        key = get_db().get_setting("tavily_api_key")
        if not key:
            key = os.getenv("TAVILY_API_KEY")
        return key.strip() if key else None

    def is_available(self) -> bool:
        # Search is always available because of DuckDuckGo fallback
        return True

    def search_tavily(self, query: str) -> Optional[Dict[str, Any]]:
        api_key = self._get_tavily_key()
        if not api_key:
            return None

        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "max_results": 5,
        }

        try:
            resp = requests.post(self.TAVILY_ENDPOINT, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                citations = []
                for item in data.get("results", []):
                    citations.append({
                        "title": item.get("title", "Web Source"),
                        "url": item.get("url", ""),
                        "snippet": item.get("content", ""),
                    })
                return {
                    "answer": data.get("answer"),
                    "citations": citations,
                    "engine": "Tavily Search",
                }
        except Exception:
            pass
        return None

    def search_duckduckgo(self, query: str) -> Dict[str, Any]:
        """Free fallback search via DuckDuckGo API and HTML parser."""
        citations = []
        answer = None

        # 1. Try DuckDuckGo Instant Answer API
        try:
            url = f"https://api.duckduckgo.com/?q={urllib.parse.quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
            resp = requests.get(url, headers={"User-Agent": "SageAI/1.0"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("AbstractText"):
                    answer = data["AbstractText"]
                    if data.get("AbstractURL"):
                        citations.append({
                            "title": data.get("Heading", "DuckDuckGo Summary"),
                            "url": data.get("AbstractURL"),
                            "snippet": data["AbstractText"][:300]
                        })

                for topic in data.get("RelatedTopics", [])[:4]:
                    if "Text" in topic and "FirstURL" in topic:
                        citations.append({
                            "title": topic.get("Text", "")[:60] + "...",
                            "url": topic.get("FirstURL"),
                            "snippet": topic.get("Text")
                        })
        except Exception:
            pass

        # 2. Try DuckDuckGo HTML if citations still empty
        if not citations:
            try:
                html_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
                resp = requests.get(
                    html_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                    timeout=10
                )
                if resp.status_code == 200:
                    text = resp.text
                    # Extract result links and snippets with regex
                    links = re.findall(
                        r'<a class="result__url" href="([^"]+)".*?>(.*?)</a>[\s\S]*?<a class="result__snippet[^>]*>(.*?)</a>',
                        text
                    )
                    for link, title_raw, snippet_raw in links[:4]:
                        clean_title = re.sub(r"<[^>]+>", "", title_raw).strip()
                        clean_snippet = re.sub(r"<[^>]+>", "", snippet_raw).strip()
                        clean_link = link.strip()
                        if clean_link.startswith("//"):
                            clean_link = "https:" + clean_link
                        citations.append({
                            "title": clean_title or "Web Search Result",
                            "url": clean_link,
                            "snippet": clean_snippet
                        })
            except Exception:
                pass

        return {
            "answer": answer,
            "citations": citations,
            "engine": "DuckDuckGo Fallback",
        }

    def generate(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> ProviderResponse:
        start_time = time.time()

        # Step 1: Tavily Search
        search_res = self.search_tavily(prompt)
        # Step 2: DuckDuckGo Fallback if Tavily is unavailable or failed
        if not search_res or not search_res.get("citations"):
            search_res = self.search_duckduckgo(prompt)

        latency = (time.time() - start_time) * 1000
        citations = search_res.get("citations", [])

        # Formatted evidence text
        evidence_lines = [f"### Web Search Evidence ({search_res.get('engine', 'Web')})\n"]
        if search_res.get("answer"):
            evidence_lines.append(f"**Quick Answer**: {search_res['answer']}\n")

        if citations:
            for idx, c in enumerate(citations, 1):
                evidence_lines.append(f"**[{idx}] [{c['title']}]({c['url']})**")
                if c.get("snippet"):
                    evidence_lines.append(f"> {c['snippet']}\n")
        else:
            evidence_lines.append("No direct web snippets retrieved for this query.")

        full_text = "\n".join(evidence_lines)

        return ProviderResponse(
            text=full_text,
            model_name=search_res.get("engine", "Web Search"),
            provider_id=self.provider_id,
            success=True,
            citations=citations,
            latency_ms=latency,
            metadata={"raw_evidence": full_text}
        )
