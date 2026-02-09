"""Base class for all analysis plugins."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.pipeline.context import PipelineContext


class BaseAnalyzer(ABC):
    """Interface every analyzer must implement.

    To create a new analyzer:
    1. Create a new file in src/analysis/ (e.g., supply_chain.py)
    2. Define a class that extends BaseAnalyzer
    3. Implement name, analyze()
    4. Register it in configs/settings.yaml under analysis.registry
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name used as key in registry and context."""
        ...

    @abstractmethod
    def analyze(self, ticker: str, ctx: PipelineContext) -> dict:
        """Run analysis for a single ticker.

        Args:
            ticker: Stock symbol
            ctx: Pipeline context with fetched data available

        Returns:
            Dict with analysis results. MUST include a "score" key (0-100).
        """
        ...

    @property
    def default_weight(self) -> float:
        """Default weight in composite scoring (0.0 - 1.0)."""
        return 0.10
