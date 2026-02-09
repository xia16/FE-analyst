"""Report generation - produce structured analysis reports."""

import json
from datetime import datetime
from pathlib import Path

from src.analysis.scoring import StockScorer
from src.config import Paths
from src.utils.logger import setup_logger

logger = setup_logger("reports")


class ReportGenerator:
    """Generate investment analysis reports."""

    def __init__(self):
        self.scorer = StockScorer()
        self.output_dir = Paths.REPORTS_OUTPUT
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def full_report(self, ticker: str) -> str:
        """Generate a comprehensive stock analysis report as markdown."""
        logger.info("Generating full report for %s", ticker)
        result = self.scorer.score(ticker)
        report = self._format_markdown(result)

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.output_dir / f"{ticker}_{timestamp}.md"
        filepath.write_text(report)
        logger.info("Report saved: %s", filepath)

        # Also save raw JSON
        json_path = self.output_dir / f"{ticker}_{timestamp}.json"
        json_path.write_text(json.dumps(result, indent=2, default=str))

        return report

    def compare_report(self, tickers: list[str]) -> str:
        """Generate a comparison report for multiple stocks."""
        results = []
        for t in tickers:
            results.append(self.scorer.score(t))

        report = self._format_comparison(results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.output_dir / f"comparison_{timestamp}.md"
        filepath.write_text(report)
        return report

    def _format_markdown(self, result: dict) -> str:
        """Format a single stock analysis as markdown."""
        lines = [
            f"# Stock Analysis: {result['ticker']}",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
            "---",
            "",
            f"## Composite Score: {result['composite_score']}/100",
            f"## Recommendation: **{result['recommendation']}**",
            "",
            "### Component Scores",
            "",
            "| Component | Score | Weight |",
            "|-----------|-------|--------|",
        ]

        for comp, score in result["component_scores"].items():
            weight = result["weights"].get(comp, 0)
            lines.append(f"| {comp.title()} | {score}/100 | {weight:.0%} |")

        details = result.get("details", {})

        # Fundamental details
        if "fundamental" in details:
            fund = details["fundamental"]
            lines.extend([
                "",
                "### Fundamental Analysis",
                f"- **Sector:** {fund.get('sector', 'N/A')}",
                f"- **Financial Health:** {fund['health']['score']}/{fund['health']['max_score']}",
            ])
            for r in fund["health"]["reasons"]:
                lines.append(f"  - {r}")
            lines.append(f"- **Growth:** {fund['growth']['score']}/{fund['growth']['max_score']}")
            for r in fund["growth"]["reasons"]:
                lines.append(f"  - {r}")

        # Valuation details
        if "valuation" in details:
            val = details["valuation"]
            if "error" not in val:
                lines.extend([
                    "",
                    "### Valuation (DCF)",
                    f"- **Intrinsic Value:** ${val.get('intrinsic_per_share', 'N/A')}",
                    f"- **Current Price:** ${val.get('current_price', 'N/A')}",
                    f"- **Margin of Safety:** {val.get('margin_of_safety_pct', 'N/A')}%",
                    f"- **Verdict:** {val.get('verdict', 'N/A')}",
                ])

        # Technical details
        if "technical" in details:
            lines.extend(["", "### Technical Signals", ""])
            for name, sig in details["technical"].items():
                lines.append(
                    f"- **{name.upper()}:** {sig.get('signal', 'N/A')} - {sig.get('reason', '')}"
                )

        # Risk details
        if "risk" in details:
            risk = details["risk"]
            if "error" not in risk:
                lines.extend([
                    "",
                    "### Risk Profile",
                    f"- **Risk Level:** {risk.get('risk_level', 'N/A')}",
                    f"- **Annualized Volatility:** {risk.get('volatility', 'N/A')}",
                    f"- **Beta:** {risk.get('beta', 'N/A')}",
                    f"- **Sharpe Ratio:** {risk.get('sharpe_ratio', 'N/A')}",
                    f"- **Max Drawdown:** {risk.get('max_drawdown', 'N/A')}",
                    f"- **VaR (95%):** {risk.get('var_95', 'N/A')}",
                ])

        # Sentiment details
        if "sentiment" in details:
            sent = details["sentiment"]
            lines.extend([
                "",
                "### Sentiment",
                f"- **Overall:** {sent.get('overall_label', 'N/A')} ({sent.get('overall_score', 0):.3f})",
            ])

        lines.extend([
            "",
            "---",
            "*Disclaimer: This is an automated analysis for informational purposes only. "
            "Not financial advice. Always do your own research.*",
        ])

        return "\n".join(lines)

    def _format_comparison(self, results: list[dict]) -> str:
        """Format a multi-stock comparison table."""
        lines = [
            "# Stock Comparison Report",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
            "| Ticker | Score | Recommendation | Fundamental | Valuation | Technical | Sentiment | Risk |",
            "|--------|-------|---------------|-------------|-----------|-----------|-----------|------|",
        ]
        for r in sorted(results, key=lambda x: x["composite_score"], reverse=True):
            cs = r["component_scores"]
            lines.append(
                f"| {r['ticker']} | **{r['composite_score']}** | {r['recommendation']} "
                f"| {cs.get('fundamental', '-')} | {cs.get('valuation', '-')} "
                f"| {cs.get('technical', '-')} | {cs.get('sentiment', '-')} "
                f"| {cs.get('risk', '-')} |"
            )

        lines.extend([
            "",
            "---",
            "*Disclaimer: Automated analysis for informational purposes only. Not financial advice.*",
        ])
        return "\n".join(lines)
