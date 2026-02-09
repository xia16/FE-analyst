"""AnalyzerRegistry: discovers and manages analyzer plugins."""

from __future__ import annotations
import importlib
from typing import TYPE_CHECKING

from src.config import SETTINGS
from src.utils.logger import setup_logger

if TYPE_CHECKING:
    from src.analysis.base import BaseAnalyzer

logger = setup_logger("registry")

_registry_instance = None


def get_registry() -> AnalyzerRegistry:
    """Get or create the singleton registry."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AnalyzerRegistry()
        _registry_instance.auto_discover()
    return _registry_instance


class AnalyzerRegistry:
    """Central registry of all available analyzers."""

    def __init__(self):
        self._analyzers: dict[str, BaseAnalyzer] = {}
        self._weight_overrides: dict[str, float] = {}

    def register(self, analyzer: BaseAnalyzer) -> None:
        self._analyzers[analyzer.name] = analyzer
        logger.info("Registered analyzer: %s", analyzer.name)

    def get(self, name: str) -> BaseAnalyzer | None:
        return self._analyzers.get(name)

    def items(self):
        return self._analyzers.items()

    def names(self) -> list[str]:
        return list(self._analyzers.keys())

    def get_weights(self) -> dict[str, float]:
        weights = {}
        for name, analyzer in self._analyzers.items():
            weights[name] = self._weight_overrides.get(name, analyzer.default_weight)
        return weights

    def auto_discover(self) -> None:
        """Load analyzers from settings.yaml registry config."""
        registry_config = SETTINGS.get("analysis", {}).get("registry", {})

        for name, conf in registry_config.items():
            if not conf.get("enabled", True):
                logger.info("Skipping disabled analyzer: %s", name)
                continue

            module_path = conf["module"]
            class_name = conf["class"]

            try:
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                instance = cls()
                self.register(instance)

                if "weight" in conf:
                    self._weight_overrides[name] = conf["weight"]

            except Exception as e:
                logger.error("Failed to load analyzer %s: %s", name, e)
