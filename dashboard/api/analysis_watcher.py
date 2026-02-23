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
"""


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
                thesis_data = {
                    "markdown": text,
                    "recommendation": rec_match.group(1).upper() if rec_match else "HOLD",
                    "conviction": rec_match.group(2).upper() if rec_match else "MEDIUM",
                }
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
