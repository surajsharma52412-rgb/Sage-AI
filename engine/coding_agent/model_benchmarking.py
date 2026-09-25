"""
Model Benchmarking & Historical Performance Tracker for SAGE Coding Agent.
Implements Sections 10 and 11 of the Ultimate Master Architecture:
- Tracks historical performance metrics per model: success rate, latency, tokens, cost, test pass rate, bug rate
- Learns which model performs best for specific task archetypes (architecture, UI, backend, debugging, documentation)
- Enforces cost-aware model routing combined with Zero-Cost Guard (<= 0 Rs)
"""
import time
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ModelExecutionRecord:
    """Telemetry record for a single model task execution."""
    model_name: str
    provider_id: str
    archetype: str  # architecture, ui_implementation, backend, debugging, documentation, simple_script
    latency_s: float
    cost_rs: float
    tokens_used: int
    tests_passed: bool
    bugs_detected: int
    success: bool
    timestamp: float = field(default_factory=time.time)


@dataclass
class ModelBenchmarkStats:
    """Aggregated historical performance stats for a model."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_s: float = 0.0
    total_cost_rs: float = 0.0
    total_tokens: int = 0
    tests_passed_count: int = 0
    bugs_detected_count: int = 0

    @property
    def success_rate(self) -> float:
        return round((self.successful_calls / self.total_calls * 100), 1) if self.total_calls > 0 else 0.0

    @property
    def avg_latency_s(self) -> float:
        return round(self.total_latency_s / self.total_calls, 2) if self.total_calls > 0 else 0.0

    @property
    def avg_cost_rs(self) -> float:
        return round(self.total_cost_rs / self.total_calls, 2) if self.total_calls > 0 else 0.0

    @property
    def test_pass_rate(self) -> float:
        return round((self.tests_passed_count / self.total_calls * 100), 1) if self.total_calls > 0 else 0.0


class ModelBenchmarkTracker:
    """
    Learns and tracks historical performance across models.
    Enables empirical model routing based on actual track records rather than theoretical claims.
    """

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root.resolve() if workspace_root else Path.cwd().resolve()
        self.storage_dir = self.workspace_root / ".sage"
        self.benchmark_file = self.storage_dir / "model_benchmarks.json"
        self.stats: Dict[str, ModelBenchmarkStats] = {}
        self.archetype_stats: Dict[str, Dict[str, ModelBenchmarkStats]] = {}
        self.load_benchmarks()

    def load_benchmarks(self):
        """Loads historical model benchmark data from disk."""
        if self.benchmark_file.exists():
            try:
                with open(self.benchmark_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for m, s in data.get("models", {}).items():
                        self.stats[m] = ModelBenchmarkStats(**s)
                    for arch, models in data.get("archetypes", {}).items():
                        self.archetype_stats[arch] = {
                            m: ModelBenchmarkStats(**s) for m, s in models.items()
                        }
            except Exception as e:
                logger.warning("Could not load benchmarks: %s", e)

    def save_benchmarks(self):
        """Persists model benchmark data to disk."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            serializable = {
                "models": {m: asdict(s) for m, s in self.stats.items()},
                "archetypes": {
                    arch: {m: asdict(s) for m, s in models.items()}
                    for arch, models in self.archetype_stats.items()
                }
            }
            with open(self.benchmark_file, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)
        except Exception as e:
            logger.warning("Could not save benchmarks: %s", e)

    def record_execution(
        self,
        model_name: str,
        provider_id: str,
        archetype: str,
        latency_s: float,
        cost_rs: float,
        tokens_used: int,
        tests_passed: bool,
        bugs_detected: int,
        success: bool
    ):
        """Records an execution result to update model statistics."""
        # Update global stats for model
        if model_name not in self.stats:
            self.stats[model_name] = ModelBenchmarkStats()
        st = self.stats[model_name]
        st.total_calls += 1
        if success:
            st.successful_calls += 1
        else:
            st.failed_calls += 1
        st.total_latency_s += latency_s
        st.total_cost_rs += cost_rs
        st.total_tokens += tokens_used
        if tests_passed:
            st.tests_passed_count += 1
        st.bugs_detected_count += bugs_detected

        # Update archetype stats
        if archetype not in self.archetype_stats:
            self.archetype_stats[archetype] = {}
        if model_name not in self.archetype_stats[archetype]:
            self.archetype_stats[archetype][model_name] = ModelBenchmarkStats()
        ast_ = self.archetype_stats[archetype][model_name]
        ast_.total_calls += 1
        if success:
            ast_.successful_calls += 1
        else:
            ast_.failed_calls += 1
        ast_.total_latency_s += latency_s
        ast_.total_cost_rs += cost_rs
        ast_.total_tokens += tokens_used
        if tests_passed:
            ast_.tests_passed_count += 1
        ast_.bugs_detected_count += bugs_detected

        self.save_benchmarks()

    def get_best_model_for_archetype(
        self,
        archetype: str,
        available_candidates: List[str]
    ) -> Optional[str]:
        """
        Recommends the best candidate model for an archetype based on empirical pass rate
        and success history.
        """
        if archetype not in self.archetype_stats or not available_candidates:
            return available_candidates[0] if available_candidates else None

        arch_models = self.archetype_stats[archetype]
        best_model = None
        best_score = -1.0

        for cand in available_candidates:
            if cand in arch_models and arch_models[cand].total_calls >= 2:
                stats = arch_models[cand]
                # Score formula: 60% test pass rate + 30% success rate - latency penalty
                score = (stats.test_pass_rate * 0.6) + (stats.success_rate * 0.3) - (min(stats.avg_latency_s, 20.0) * 0.5)
                if score > best_score:
                    best_score = score
                    best_model = cand

        return best_model or available_candidates[0]
