"""
Data Analysis Agent for Sage Multi-Agentic AI Architecture.
Capabilities:
- Analyze data
- Create charts
- Find insights
- Work with CSV/Excel
- Statistical analysis
- Generate reports
"""
import io
import csv
import json
import math
import logging
from typing import Dict, Any, Optional, Callable, List

from config import AGENT_DATA_ANALYSIS
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class DataAnalysisAgent(BaseAgent):
    """Specialized in quantitative analysis, CSV/data parsing, statistical summaries, and analytical reports."""

    def __init__(self):
        super().__init__(name=AGENT_DATA_ANALYSIS, role_id="data_analysis")

    def execute(
        self,
        task_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        instruction = task_input.get("instruction") or task_input.get("query") or ""
        raw_data = task_input.get("data")
        task_id = (context or {}).get("task_id")

        if on_stage:
            on_stage("📊 Data Analysis Agent: Computing statistical metrics & trends...")
        self.log("Analyzing data and generating insights", task_id=task_id, details={"instruction": instruction})

        stats_summary = {}
        # If tabular CSV string or list provided, compute statistics
        if isinstance(raw_data, str) and ("," in raw_data or "\t" in raw_data):
            stats_summary = self._compute_tabular_stats(raw_data)
        elif isinstance(raw_data, list):
            stats_summary = self._compute_list_stats(raw_data)

        stats_block = f"\nComputed Metrics:\n{json.dumps(stats_summary, indent=2)}\n" if stats_summary else ""

        system_prompt = (
            "You are Sage AI's expert Data Analysis Agent. You specialize in mathematical rigor, "
            "statistical analysis, discovering trends, anomalies, and formulating executive data reports. "
            "Use clear tables, key metrics, and markdown-formatted charts or ASCII visuals."
        )

        prompt = (
            f"Analytical Objective: {instruction}\n"
            f"{stats_block}\n"
            f"{('Raw Dataset:\n' + str(raw_data)[:1500]) if raw_data else ''}\n\n"
            "Provide a comprehensive Data Analysis Report including Executive Summary, Key Findings, "
            "Statistical Metrics, Visual Representation, and Strategic Recommendations."
        )

        llm_res = self.call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            on_chunk=on_chunk,
            preferred_providers=["groq", "nvidia", "gemini", "openrouter", "ollama", "local_facts"]
        )

        report_text = llm_res.get("text", "")

        self.send_bus_message(
            to_agent="all",
            message_type="analysis_completed",
            content=f"Data analysis report produced for: '{instruction[:40]}...'",
            task_id=task_id
        )

        return {
            "success": True,
            "agent": self.name,
            "summary": report_text,
            "metrics": stats_summary,
            "deliverables": [
                {
                    "type": "data_analysis_report",
                    "title": f"Data Analysis Report: {instruction[:40]}",
                    "content": report_text,
                    "metrics": stats_summary
                }
            ]
        }

    def _compute_tabular_stats(self, csv_content: str) -> Dict[str, Any]:
        """Calculates basic column statistics for numerical columns in CSV."""
        try:
            reader = csv.DictReader(io.StringIO(csv_content.strip()))
            rows = list(reader)
            if not rows:
                return {}

            columns = reader.fieldnames or []
            stats = {"total_rows": len(rows), "columns": columns, "numeric_stats": {}}

            for col in columns:
                vals = []
                for r in rows:
                    v = r.get(col, "").strip()
                    try:
                        vals.append(float(v))
                    except ValueError:
                        pass
                if len(vals) >= max(2, int(len(rows) * 0.5)):
                    mean_val = sum(vals) / len(vals)
                    min_val = min(vals)
                    max_val = max(vals)
                    variance = sum((x - mean_val) ** 2 for x in vals) / len(vals)
                    std_dev = math.sqrt(variance)
                    stats["numeric_stats"][col] = {
                        "count": len(vals),
                        "mean": round(mean_val, 2),
                        "std_dev": round(std_dev, 2),
                        "min": min_val,
                        "max": max_val
                    }

            return stats
        except Exception as e:
            logger.debug("Tabular stats calculation failed: %s", e)
            return {}

    def _compute_list_stats(self, numbers: List[Any]) -> Dict[str, Any]:
        numeric_vals = [float(x) for x in numbers if isinstance(x, (int, float))]
        if not numeric_vals:
            return {"count": len(numbers)}
        mean_val = sum(numeric_vals) / len(numeric_vals)
        return {
            "count": len(numeric_vals),
            "mean": round(mean_val, 2),
            "min": min(numeric_vals),
            "max": max(numeric_vals),
            "sum": round(sum(numeric_vals), 2)
        }
