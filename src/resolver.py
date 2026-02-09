"""Ticker and company name resolution."""

from __future__ import annotations

import yaml

from src.config import PROJECT_ROOT
from src.utils.logger import setup_logger

logger = setup_logger("resolver")


def _load_aliases() -> dict:
    path = PROJECT_ROOT / "configs" / "aliases.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


class TickerResolver:
    """Resolve user input like 'TSMC' or 'Tokyo Electron' to canonical tickers."""

    def __init__(self):
        self._aliases = _load_aliases()
        self._universe_map = self._build_universe_map()

    def _build_universe_map(self) -> dict[str, str]:
        path = PROJECT_ROOT / "configs" / "ai_moat_universe.yaml"
        if not path.exists():
            return {}
        with open(path) as f:
            data = yaml.safe_load(f)

        name_map = {}
        for cat_data in (data or {}).get("categories", {}).values():
            if not isinstance(cat_data, dict):
                continue
            for item in cat_data.get("companies", []):
                if isinstance(item, dict) and "ticker" in item:
                    name = item.get("name", "")
                    ticker = item["ticker"]
                    adr = item.get("adr", "")
                    if name:
                        name_map[name.lower()] = adr or ticker
                    name_map[ticker.lower()] = ticker
                    if adr:
                        name_map[adr.lower()] = adr
        return name_map

    def resolve(self, user_input: str) -> str:
        # Check aliases
        for alias, ticker in self._aliases.items():
            if user_input.lower() == str(alias).lower():
                logger.info("Resolved alias '%s' -> '%s'", user_input, ticker)
                return ticker
        # Check universe
        lower = user_input.lower()
        if lower in self._universe_map:
            resolved = self._universe_map[lower]
            logger.info("Resolved universe '%s' -> '%s'", user_input, resolved)
            return resolved
        return user_input.upper()

    def resolve_many(self, inputs: list[str]) -> list[str]:
        return [self.resolve(i) for i in inputs]
