"""
Base Provider interface for Sage AI.
Defines standard response format and execution lifecycle.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Generator, Callable


@dataclass
class ProviderResponse:
    """Standardized response from any model or service provider."""
    text: str
    model_name: str
    provider_id: str
    success: bool = True
    error_msg: Optional[str] = None
    citations: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    is_image: bool = False
    image_data: Optional[str] = None  # Base64 string if image

    def __post_init__(self):
        if self.error_msg:
            from engine.security_vault import SecurityVault
            self.error_msg = SecurityVault.sanitize_text(self.error_msg)


class BaseProvider(ABC):
    """Abstract base class for all LLM and tool providers."""

    def __init__(self, provider_id: str, name: str):
        self.provider_id = provider_id
        self.name = name

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if required credentials or service endpoints are configured and reachable."""
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> ProviderResponse:
        """Executes completion or tool call, invoking on_chunk for partial tokens if supported."""
        pass
