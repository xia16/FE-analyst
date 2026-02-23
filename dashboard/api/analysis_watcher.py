"""
Analysis Watcher — Monitors analysis_queue/ for trigger files and runs Claude Code.

Runs in tmux alongside the telegram poller and API server.
Usage: python analysis_watcher.py

Flow:
1. Dashboard POST /api/analyze/{ticker}/thesis -> creates .trigger file
2. This watcher picks up the trigger
3. Runs raw metrics via run_analysis.py subprocess
4. Constructs a prompt with all raw data
5. Runs: claude -p "{prompt}" --output-format json
6. Parses output and stores thesis in stock_analyses table
7. Deletes trigger file
"""

import json
import logging
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "portfolio.db"
QUEUE_DIR = Path(__file__).parent / "analysis_queue"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE_PYTHON = PROJECT_ROOT / "venv" / "bin" / "python"
ANALYSIS_RUNNER = Path(__file__).parent / "run_analysis.py"


def get_raw_metrics(ticker: str) -> dict:
    """Run analysis engines and get raw metrics."""
    try:
        result = subprocess.run(
            [str(PIPELINE_PYTHON), str(ANALYSIS_RUNNER), ticker],
            capture_output=True, text=True, timeout=120,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        logger.error("Analysis subprocess failed: %s", result.stderr)
        return {"error": result.stderr}
    except subprocess.TimeoutExpired:
        return {"error": "Analysis timed out"}
    except Exception as e:
        return {"error": str(e)}


def build_prompt(ticker: str, metrics: dict) -> str:
    """Build the Phase 3B enhanced analysis prompt with all raw data for Claude Code."""
    return f"""You are a senior equity research analyst at a hedge fund with deep expertise in international equities, ADR arbitrage, and catalyst-driven investing. Analyze {ticker} and produce a comprehensive, actionable investment thesis.

## Raw Data (from our analysis engines)

### Composite Score: {metrics.get('composite_score', 'N/A')}/100 — {metrics.get('recommendation', 'N/A')}
### Component Scores: {json.dumps(metrics.get('component_scores', {}), indent=2)}

### Fundamental Analysis
{json.dumps(metrics.get('details', {}).get('fundamental', {}), indent=2, default=str)}

### Valuation Analysis (DCF + Comparables)
{json.dumps(metrics.get('details', {}).get('valuation', {}), indent=2, default=str)}

### Risk Analysis
{json.dumps(metrics.get('details', {}).get('risk', {}), indent=2, default=str)}

### Technical Analysis
{json.dumps(metrics.get('details', {}).get('technical', {}), indent=2, default=str)}

### Moat Analysis
{json.dumps(metrics.get('moat', {}), indent=2, default=str)}

### Insider & Congressional Trading
{json.dumps(metrics.get('insider_congress', {}), indent=2, default=str)}

### Company Profile
{json.dumps(metrics.get('profile', {}), indent=2, default=str)}

### Key Ratios
{json.dumps(metrics.get('ratios', {}), indent=2, default=str)}

### International Analysis (ADR Premium/Discount, FX Sensitivity)
{json.dumps(metrics.get('international', {}), indent=2, default=str)}

### Earnings Estimates & Calendar
{json.dumps(metrics.get('earnings_estimates', {}), indent=2, default=str)}

### Short Interest
{json.dumps(metrics.get('short_interest', {}), indent=2, default=str)}

### Whale/Institutional Tracking
{json.dumps(metrics.get('whale_tracking', {}), indent=2, default=str)}

### Upcoming Catalysts
{json.dumps(metrics.get('catalysts', {}), indent=2, default=str)}

### Conviction Meta-Score
{json.dumps(metrics.get('conviction', {}), indent=2, default=str)}

## Instructions

You are a senior equity research analyst at a hedge fund with deep expertise in international equities, ADR arbitrage, and catalyst-driven investing. Write a comprehensive investment analysis report for {ticker} in **Markdown format**.

Structure your report however you see fit based on what the data reveals — there is no fixed template. Write naturally and insightfully as you would for an investment committee presentation. Use your judgment on what matters most for this particular company.

Your report should cover the key aspects you find most relevant: company overview, investment thesis, valuation view (interpret the DCF and comps data), risk factors, upcoming catalysts, competitive positioning, and any contrarian insights. Use markdown headers (##), bullet points, bold text, and tables where they help communicate clearly.

Be specific — cite actual numbers from the data (e.g., "RSI at 39 suggests oversold conditions" not just "technical picture is bearish"). If data shows errors or is unavailable, note it briefly and work with what you have.

At the very end of your report, on its own line, include:
**Recommendation: BUY|HOLD|SELL | Conviction: HIGH|MEDIUM|LOW**

## Scenario Assumptions (REQUIRED)

After your markdown report, you MUST output the following block with your bear/base/bull DCF scenario assumptions. Think critically about what specific growth rates, discount rates, and terminal growth rates are appropriate for THIS specific company. Do NOT use generic multipliers (like 1.3x growth for bull) — reason about company-specific catalysts, risks, and competitive dynamics for each scenario.

For each scenario, provide:
- `growth_rate`: Your estimated 5-year revenue/FCF growth rate (decimal, e.g. 0.15 = 15%). This should reflect your analysis of the company's specific growth drivers.
- `terminal_growth`: Long-run sustainable growth (decimal, typically 0.02-0.04 for most companies)
- `wacc_adjustment`: Adjustment RELATIVE to the base WACC (decimal, e.g. -0.01 means 1% lower WACC for bull case due to better credit conditions, +0.015 means 1.5% higher for bear case)
- `probability`: Your estimated probability weight (must sum to 1.0 across all three)
- `narrative`: 1-2 sentence thesis explaining WHY this scenario would materialize. Be specific about catalysts and risks.
- `key_drivers`: List of 2-4 key factors that would drive this scenario

Output the block exactly in this format:

<!-- SCENARIO_ASSUMPTIONS -->
{{
  "bull": {{
    "growth_rate": 0.XX,
    "terminal_growth": 0.0X,
    "wacc_adjustment": -0.0X,
    "probability": 0.XX,
    "narrative": "Specific thesis for the bull case",
    "key_drivers": ["driver1", "driver2", "driver3"]
  }},
  "base": {{
    "growth_rate": 0.XX,
    "terminal_growth": 0.0X,
    "wacc_adjustment": 0.00,
    "probability": 0.XX,
    "narrative": "Specific thesis for the base case",
    "key_drivers": ["driver1", "driver2"]
  }},
  "bear": {{
    "growth_rate": 0.XX,
    "terminal_growth": 0.0X,
    "wacc_adjustment": 0.0X,
    "probability": 0.XX,
    "narrative": "Specific thesis for the bear case",
    "key_drivers": ["driver1", "driver2", "driver3"]
  }}
}}
<!-- /SCENARIO_ASSUMPTIONS -->
"""


def _extract_scenario_assumptions(text: str) -> dict | None:
    """Extract LLM-validated scenario assumptions from Claude's output.

    Looks for the <!-- SCENARIO_ASSUMPTIONS --> block, parses JSON, validates
    required fields, clamps values to sane ranges, and normalizes probabilities.
    Returns None if parsing fails (graceful fallback to mechanical scenarios).
    """
    match = re.search(
        r"<!--\s*SCENARIO_ASSUMPTIONS\s*-->\s*(.*?)\s*<!--\s*/SCENARIO_ASSUMPTIONS\s*-->",
        text, re.DOTALL,
    )
    if not match:
        logger.info("No SCENARIO_ASSUMPTIONS block found in Claude output")
        return None

    raw = match.group(1).strip()
    try:
        assumptions = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse scenario JSON: %s", e)
        return None

    required_scenarios = {"bull", "base", "bear"}
    if not required_scenarios.issubset(assumptions.keys()):
        logger.warning("Missing scenarios: %s", required_scenarios - assumptions.keys())
        return None

    required_fields = {"growth_rate", "terminal_growth", "wacc_adjustment", "probability", "narrative", "key_drivers"}

    for scenario_name in required_scenarios:
        sc = assumptions[scenario_name]
        if not isinstance(sc, dict):
            logger.warning("Scenario '%s' is not a dict", scenario_name)
            return None
        missing = required_fields - sc.keys()
        if missing:
            logger.warning("Scenario '%s' missing fields: %s", scenario_name, missing)
            return None

        # Clamp values to sane ranges
        sc["growth_rate"] = max(-0.20, min(0.50, float(sc["growth_rate"])))
        sc["terminal_growth"] = max(0.01, min(0.05, float(sc["terminal_growth"])))
        sc["wacc_adjustment"] = max(-0.03, min(0.03, float(sc["wacc_adjustment"])))
        sc["probability"] = max(0.10, min(0.60, float(sc["probability"])))

        # Ensure key_drivers is a list
        if not isinstance(sc.get("key_drivers"), list):
            sc["key_drivers"] = []

        # Ensure narrative is a string
        if not isinstance(sc.get("narrative"), str):
            sc["narrative"] = ""

    # Normalize probabilities to sum to 1.0
    total_prob = sum(assumptions[s]["probability"] for s in required_scenarios)
    if total_prob > 0:
        for s in required_scenarios:
            assumptions[s]["probability"] = round(assumptions[s]["probability"] / total_prob, 3)

    logger.info(
        "Extracted LLM scenario assumptions: bull=%.1f%% growth, base=%.1f%%, bear=%.1f%%",
        assumptions["bull"]["growth_rate"] * 100,
        assumptions["base"]["growth_rate"] * 100,
        assumptions["bear"]["growth_rate"] * 100,
    )
    return assumptions


def update_status(analysis_id: int, status: str, data: dict | None = None, model: str | None = None):
    """Update analysis status in the database."""
    conn = sqlite3.connect(DB_PATH)
    if data is not None:
        conn.execute(
            "UPDATE stock_analyses SET status=?, data=?, model=? WHERE id=?",
            (status, json.dumps(data, default=str), model, analysis_id),
        )
    else:
        conn.execute("UPDATE stock_analyses SET status=? WHERE id=?", (status, analysis_id))
    conn.commit()
    conn.close()


def store_metrics(ticker: str, metrics: dict):
    """Store raw metrics in the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO stock_analyses (ticker, analysis_type, data, created_at, status) VALUES (?, 'metrics', ?, ?, 'completed')",
        (ticker, json.dumps(metrics, default=str), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def run_analysis(trigger: dict):
    """Run Claude Code analysis for a ticker."""
    analysis_id = trigger["id"]
    ticker = trigger["ticker"]

    logger.info("Starting analysis for %s (id=%d)", ticker, analysis_id)

    # Update status to running
    update_status(analysis_id, "running")

    # Get raw metrics
    metrics = get_raw_metrics(ticker)
    if "error" in metrics and not metrics.get("composite_score"):
        logger.error("Raw metrics failed for %s: %s", ticker, metrics.get("error"))
        update_status(analysis_id, "failed", {"error": metrics.get("error")})
        return

    # Store raw metrics
    store_metrics(ticker, metrics)

    # Build prompt and run Claude Code
    prompt = build_prompt(ticker, metrics)

    try:
        logger.info("Running Claude Code for %s...", ticker)
        import os
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        proc = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json"],
            capture_output=True, text=True, timeout=300,
            cwd=str(PROJECT_ROOT),
            env=env,
        )

        if proc.returncode == 0 and proc.stdout.strip():
            # Claude --output-format json wraps in {"type":"result","result":"..."}
            try:
                outer = json.loads(proc.stdout)
                text = outer.get("result", proc.stdout)
            except (json.JSONDecodeError, TypeError):
                text = proc.stdout

            # Try to parse as old-style JSON first (backward compat)
            old_thesis = _extract_json(text)
            if old_thesis and "executive_summary" in old_thesis:
                old_thesis["updated_at"] = datetime.utcnow().isoformat()
                update_status(analysis_id, "completed", old_thesis, "claude-code")
                logger.info("Thesis completed for %s (JSON format)", ticker)
            else:
                # New freeform markdown path
                rec_match = re.search(
                    r'\*\*Recommendation:\s*(BUY|HOLD|SELL)\s*\|\s*Conviction:\s*(HIGH|MEDIUM|LOW)\*\*',
                    text, re.IGNORECASE,
                )

                # Strip scenario block from displayed markdown (keep it clean)
                display_markdown = re.sub(
                    r"\s*<!--\s*SCENARIO_ASSUMPTIONS\s*-->.*?<!--\s*/SCENARIO_ASSUMPTIONS\s*-->\s*",
                    "", text, flags=re.DOTALL,
                ).strip()

                thesis_data = {
                    "markdown": display_markdown,
                    "recommendation": rec_match.group(1).upper() if rec_match else "HOLD",
                    "conviction": rec_match.group(2).upper() if rec_match else "MEDIUM",
                }

                # Extract and recompute LLM-validated scenarios
                scenario_assumptions = _extract_scenario_assumptions(text)
                if scenario_assumptions:
                    try:
                        logger.info("Recomputing DCF with LLM assumptions for %s...", ticker)
                        import sys
                        sys.path.insert(0, str(PROJECT_ROOT))
                        from src.analysis.valuation import ValuationAnalyzer
                        va = ValuationAnalyzer()
                        llm_scenarios = va.scenario_analysis_from_assumptions(
                            ticker, scenario_assumptions
                        )
                        if "error" not in llm_scenarios:
                            thesis_data["llm_scenarios"] = llm_scenarios
                            logger.info(
                                "LLM scenarios computed for %s: bear=$%.2f, base=$%.2f, bull=$%.2f (PW=$%.2f)",
                                ticker,
                                llm_scenarios["scenarios"]["bear"]["intrinsic_per_share"],
                                llm_scenarios["scenarios"]["base"]["intrinsic_per_share"],
                                llm_scenarios["scenarios"]["bull"]["intrinsic_per_share"],
                                llm_scenarios["probability_weighted"],
                            )
                        else:
                            logger.warning("LLM scenario recomputation failed: %s", llm_scenarios.get("error"))
                    except Exception as e:
                        logger.error("Failed to recompute LLM scenarios for %s: %s", ticker, e)

                update_status(analysis_id, "completed", thesis_data, "claude-code")
                logger.info("Thesis completed for %s (markdown format)", ticker)
        else:
            error = proc.stderr or "Claude Code returned no output"
            logger.error("Claude Code failed for %s: %s", ticker, error)
            update_status(analysis_id, "failed", {"error": error})

    except subprocess.TimeoutExpired:
        logger.error("Claude Code timed out for %s", ticker)
        update_status(analysis_id, "failed", {"error": "Claude Code timed out after 300s"})
    except FileNotFoundError:
        logger.error("claude CLI not found. Install Claude Code: npm install -g @anthropic-ai/claude-code")
        update_status(analysis_id, "failed", {"error": "claude CLI not found"})
    except Exception as e:
        logger.error("Analysis error for %s: %s", ticker, e)
        update_status(analysis_id, "failed", {"error": str(e)})


def _extract_json(text: str) -> dict | None:
    """Try to extract a JSON object from text that may contain markdown fences."""
    # Try direct parse first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try to find JSON in markdown code fences
    import re
    patterns = [
        r"```json\s*\n(.*?)\n\s*```",
        r"```\s*\n(.*?)\n\s*```",
        r"\{[^{}]*\"executive_summary\"[^{}]*\}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1) if match.lastindex else match.group(0))
            except (json.JSONDecodeError, TypeError):
                continue

    # Try to find any JSON object in the text
    brace_depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if brace_depth == 0:
                start = i
            brace_depth += 1
        elif ch == '}':
            brace_depth -= 1
            if brace_depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = None

    return None


def main():
    """Watch analysis_queue/ for trigger files."""
    QUEUE_DIR.mkdir(exist_ok=True)
    logger.info("Analysis watcher started. Watching %s", QUEUE_DIR)

    while True:
        try:
            triggers = sorted(QUEUE_DIR.glob("*.trigger"))
            for trigger_path in triggers:
                try:
                    trigger = json.loads(trigger_path.read_text())
                    logger.info("Processing trigger: %s (id=%s)", trigger["ticker"], trigger["id"])
                    run_analysis(trigger)
                except Exception as e:
                    logger.error("Error processing trigger %s: %s", trigger_path.name, e)
                finally:
                    trigger_path.unlink(missing_ok=True)

            time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error("Error in watch loop: %s", e)
            time.sleep(10)


if __name__ == "__main__":
    main()
