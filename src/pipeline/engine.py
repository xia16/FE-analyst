"""PipelineEngine: orchestrates step execution for an analysis run."""

from __future__ import annotations
from pathlib import Path
from typing import Callable

from src.pipeline.context import PipelineContext
from src.reports.renderer import ReportRenderer
from src.config import Paths
from src.utils.logger import setup_logger

logger = setup_logger("pipeline")

PipelineStep = Callable[[PipelineContext], None]


class PipelineEngine:
    """Executes an ordered list of pipeline steps against a context."""

    def __init__(self):
        self.renderer = ReportRenderer()

    def run(
        self,
        ctx: PipelineContext,
        steps: list[PipelineStep],
        template: str = "deep_dive.md.j2",
        output_dir: Path | None = None,
    ) -> Path:
        """Execute all steps, then render the report."""
        output_dir = output_dir or Paths.REPORTS_OUTPUT
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Pipeline started: profile=%s tickers=%s steps=%d",
            ctx.profile_name, ctx.tickers, len(steps),
        )

        for i, step in enumerate(steps, 1):
            step_name = getattr(step, "__name__", step.__class__.__name__)
            logger.info("[%d/%d] Running: %s", i, len(steps), step_name)
            try:
                step(ctx)
                ctx.steps_completed.append(step_name)
            except Exception as e:
                logger.error("Step %s failed: %s", step_name, e)
                ctx.errors.append({"step": step_name, "error": str(e)})

        # Render report
        report_md = self.renderer.render(template, ctx)

        # Write output
        slug = "_".join(ctx.tickers[:3])
        if len(ctx.tickers) > 3:
            slug += f"_+{len(ctx.tickers) - 3}"
        filename = f"{ctx.profile_name}_{slug}_{ctx.run_id}.md"
        report_path = output_dir / filename
        report_path.write_text(report_md)

        logger.info("Report saved: %s", report_path)
        return report_path
