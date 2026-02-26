"""PipelineContext: shared state bag passed through every pipeline step."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass
class PipelineContext:
    """Accumulates data and results as a pipeline executes."""

    # Input
    tickers: list[str]
    profile_name: str = "full"
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    # Universe metadata (from YAML)
    company_meta: dict[str, dict] = field(default_factory=dict)

    # Fetched data
    price_data: dict[str, pd.DataFrame] = field(default_factory=dict)
    fundamentals_data: dict[str, dict] = field(default_factory=dict)
    financials_data: dict[str, dict] = field(default_factory=dict)
    news_data: dict[str, Any] = field(default_factory=dict)

    # Analysis results: ticker -> {analyzer_name -> result_dict}
    analysis_results: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Portfolio holdings (optional, for portfolio-level analyzers)
    holdings: list[dict] = field(default_factory=list)  # [{"ticker": str, "weight": float}]

    # Scores: ticker -> {composite_score, component_scores, recommendation}
    scores: dict[str, dict] = field(default_factory=dict)

    # Pipeline metadata
    steps_completed: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    @property
    def primary_ticker(self) -> str:
        return self.tickers[0] if self.tickers else ""

    def set_analysis(self, ticker: str, analyzer_name: str, result: dict):
        if ticker not in self.analysis_results:
            self.analysis_results[ticker] = {}
        self.analysis_results[ticker][analyzer_name] = result

    def get_analysis(self, ticker: str, analyzer_name: str) -> dict | None:
        return self.analysis_results.get(ticker, {}).get(analyzer_name)
