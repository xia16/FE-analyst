"""PipelineEngine: orchestrates step execution for an analysis run."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from src.pipeline.context import PipelineContext
from src.reports.renderer import ReportRenderer
from src.config import Paths
from src.utils.logger import setup_logger

logger = setup_logger("pipeline")

PipelineStep = Callable[[PipelineContext], None]
ProgressCallback = Callable[[str, str, float], None]


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


class AsyncPipelineEngine:
    """Parallel pipeline engine using ThreadPoolExecutor.

    Automatically groups pipeline steps into phases and executes
    parallelizable phases (FETCH, ANALYZE) concurrently while running
    sequential phases (SCORE, RENDER) in order.

    When the context contains multiple tickers, fetch and analysis steps
    are expanded into per-ticker tasks for maximum concurrency.

    Attributes:
        max_workers: Maximum number of threads in the executor pool.
        progress_callback: Optional callable invoked after each step with
            (step_name, status, elapsed_seconds).
        last_timing: Timing breakdown from the most recent ``run()`` call.
    """

    PHASE_FETCH: str = "FETCH"
    PHASE_ANALYZE: str = "ANALYZE"
    PHASE_SCORE: str = "SCORE"
    PHASE_RENDER: str = "RENDER"

    _PARALLEL_PHASES: frozenset[str] = frozenset({"FETCH", "ANALYZE"})
    _PHASE_ORDER: list[str] = ["FETCH", "ANALYZE", "SCORE", "RENDER"]

    def __init__(
        self,
        max_workers: int = 4,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.renderer = ReportRenderer()
        self.max_workers = max_workers
        self.progress_callback = progress_callback
        self._lock = threading.Lock()
        self.last_timing: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Step classification
    # ------------------------------------------------------------------

    @staticmethod
    def _step_name(step: PipelineStep) -> str:
        """Return a human-readable name for a pipeline step."""
        return getattr(step, "__name__", step.__class__.__name__)

    @classmethod
    def _classify_step(cls, step: PipelineStep) -> str:
        """Determine which execution phase a step belongs to.

        Classification order:
        1. Explicit ``phase`` attribute on the step function/object.
        2. Name-based heuristic (fetch, analy*, score, render/report).
        3. Falls back to SCORE (sequential) for unrecognised steps.
        """
        phase_attr = getattr(step, "phase", None)
        if phase_attr is not None:
            return str(phase_attr).upper()

        name = cls._step_name(step).lower()
        if "fetch" in name:
            return cls.PHASE_FETCH
        if "analy" in name:
            return cls.PHASE_ANALYZE
        if "score" in name:
            return cls.PHASE_SCORE
        if "render" in name or "report" in name:
            return cls.PHASE_RENDER
        return cls.PHASE_SCORE

    def _group_steps_by_phase(
        self, steps: list[PipelineStep],
    ) -> list[tuple[str, list[PipelineStep]]]:
        """Partition *steps* into ordered phase groups.

        Returns a list of ``(phase_name, step_list)`` tuples, preserving
        the canonical phase order and omitting empty phases.
        """
        groups: dict[str, list[PipelineStep]] = {
            p: [] for p in self._PHASE_ORDER
        }
        for step in steps:
            phase = self._classify_step(step)
            target = groups.get(phase, groups[self.PHASE_SCORE])
            target.append(step)
        return [(p, groups[p]) for p in self._PHASE_ORDER if groups[p]]

    # ------------------------------------------------------------------
    # Multi-ticker expansion
    # ------------------------------------------------------------------

    def _make_single_ticker_task(
        self, step: PipelineStep, ticker: str,
    ) -> PipelineStep:
        """Wrap *step* so it operates on a single ticker only.

        A lightweight ``PipelineContext`` is created with ``tickers=[ticker]``
        but sharing all mutable data dictionaries with the original context.
        Because each ticker writes to its own dictionary key, concurrent
        access from different threads is safe under the GIL.
        """
        original_name = self._step_name(step)

        def _task(ctx: PipelineContext) -> None:
            single_ctx = PipelineContext(
                tickers=[ticker],
                profile_name=ctx.profile_name,
                run_id=ctx.run_id,
                company_meta=ctx.company_meta,
                price_data=ctx.price_data,
                fundamentals_data=ctx.fundamentals_data,
                financials_data=ctx.financials_data,
                news_data=ctx.news_data,
                analysis_results=ctx.analysis_results,
                scores=ctx.scores,
                # steps_completed and errors are managed by the engine
                # with a lock, so share them directly.
                steps_completed=ctx.steps_completed,
                errors=ctx.errors,
                started_at=ctx.started_at,
            )
            step(single_ctx)

        _task.__name__ = f"{original_name}[{ticker}]"
        return _task

    def _expand_steps_by_ticker(
        self, ctx: PipelineContext, steps: list[PipelineStep],
    ) -> list[PipelineStep]:
        """Expand each step into per-ticker tasks when multiple tickers exist.

        For a single ticker the original steps are returned unchanged.
        For *N* tickers and *S* steps this produces *N x S* independent
        tasks that can all execute in parallel.
        """
        if len(ctx.tickers) <= 1:
            return list(steps)

        expanded: list[PipelineStep] = []
        for step in steps:
            for ticker in ctx.tickers:
                expanded.append(self._make_single_ticker_task(step, ticker))
        return expanded

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def _execute_step(
        self,
        step: PipelineStep,
        ctx: PipelineContext,
        step_name: str,
    ) -> tuple[float, str]:
        """Run a single step with timing, error handling, and progress tracking.

        Returns:
            A ``(elapsed_seconds, status)`` tuple where *status* is either
            ``"completed"`` or ``"failed"``.
        """
        start = time.monotonic()
        try:
            step(ctx)
            elapsed = time.monotonic() - start
            with self._lock:
                ctx.steps_completed.append(step_name)
            logger.info("Step %s completed in %.1fs", step_name, elapsed)
            if self.progress_callback is not None:
                self.progress_callback(step_name, "completed", elapsed)
            return elapsed, "completed"
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error("Step %s failed in %.1fs: %s", step_name, elapsed, exc)
            with self._lock:
                ctx.errors.append({"step": step_name, "error": str(exc)})
            if self.progress_callback is not None:
                self.progress_callback(step_name, "failed", elapsed)
            return elapsed, "failed"

    def run_parallel(
        self,
        ctx: PipelineContext,
        steps: list[PipelineStep],
        max_workers: int | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Execute *steps* concurrently using a thread pool.

        Each step is wrapped in a try/except so that a single failure does
        not cancel the remaining tasks.  Errors are accumulated in
        ``ctx.errors`` and completed step names are appended to
        ``ctx.steps_completed``.

        Args:
            ctx: Shared pipeline context.
            steps: Steps to run in parallel.
            max_workers: Override for ``self.max_workers``.

        Returns:
            Mapping of ``step_name -> {"status": ..., "elapsed": ...}``.
        """
        workers = max_workers if max_workers is not None else self.max_workers
        results: dict[str, dict[str, Any]] = {}
        executor = ThreadPoolExecutor(max_workers=workers)

        try:
            future_to_name: dict[Any, str] = {}
            for step in steps:
                name = self._step_name(step)
                future = executor.submit(self._execute_step, step, ctx, name)
                future_to_name[future] = name

            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    elapsed, status = future.result()
                    results[name] = {
                        "status": status,
                        "elapsed": round(elapsed, 2),
                    }
                except Exception as exc:
                    # Should not happen since _execute_step catches
                    # exceptions internally, but guard against the
                    # unexpected.
                    logger.error(
                        "Unexpected error in step %s: %s", name, exc,
                    )
                    results[name] = {
                        "status": "error",
                        "error": str(exc),
                        "elapsed": 0.0,
                    }
        except KeyboardInterrupt:
            logger.warning(
                "Parallel execution interrupted, shutting down executor",
            )
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True)

        return results

    # ------------------------------------------------------------------
    # Pre-initialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pre_initialize_analysis_results(ctx: PipelineContext) -> None:
        """Ensure ``analysis_results`` has a sub-dict for every ticker.

        This avoids a check-then-act race in ``PipelineContext.set_analysis``
        when multiple threads write results for the same ticker concurrently.
        """
        for ticker in ctx.tickers:
            if ticker not in ctx.analysis_results:
                ctx.analysis_results[ticker] = {}

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    def run(
        self,
        ctx: PipelineContext,
        steps: list[PipelineStep],
        template: str = "deep_dive.md.j2",
        output_dir: Path | None = None,
    ) -> Path:
        """Execute the pipeline with automatic phase grouping and parallelism.

        Steps are classified into four phases:

        * **FETCH** -- data retrieval (parallel, multi-ticker expanded)
        * **ANALYZE** -- analysis plugins (parallel, multi-ticker expanded)
        * **SCORE** -- composite scoring (sequential)
        * **RENDER** -- report generation (sequential)

        Timing data for every phase and step is stored in
        ``self.last_timing`` after the run completes.

        Args:
            ctx: Shared pipeline context.
            steps: Ordered list of pipeline step callables.
            template: Jinja2 template name for report rendering.
            output_dir: Directory for the rendered report file.

        Returns:
            ``Path`` to the generated markdown report.
        """
        output_dir = output_dir or Paths.REPORTS_OUTPUT
        output_dir.mkdir(parents=True, exist_ok=True)

        pipeline_start = time.monotonic()
        timing: dict[str, Any] = {}

        logger.info(
            "AsyncPipeline started: profile=%s tickers=%s steps=%d",
            ctx.profile_name, ctx.tickers, len(steps),
        )

        phases = self._group_steps_by_phase(steps)

        # Pre-initialise analysis_results to prevent race conditions
        # when per-ticker analysis tasks run concurrently.
        self._pre_initialize_analysis_results(ctx)

        try:
            for phase_name, phase_steps in phases:
                phase_start = time.monotonic()
                logger.info(
                    "Phase %s started (%d steps)",
                    phase_name, len(phase_steps),
                )

                if phase_name in self._PARALLEL_PHASES:
                    # Expand fetch/analyze steps across tickers for
                    # maximum concurrency, then run in parallel.
                    expanded = self._expand_steps_by_ticker(ctx, phase_steps)
                    logger.info(
                        "Phase %s expanded to %d tasks (multi-ticker)",
                        phase_name, len(expanded),
                    )
                    phase_results = self.run_parallel(ctx, expanded)
                else:
                    # SCORE and RENDER phases run sequentially.
                    phase_results: dict[str, dict[str, Any]] = {}
                    for step in phase_steps:
                        name = self._step_name(step)
                        elapsed, status = self._execute_step(step, ctx, name)
                        phase_results[name] = {
                            "status": status,
                            "elapsed": round(elapsed, 2),
                        }

                phase_elapsed = time.monotonic() - phase_start
                timing[phase_name] = {
                    "elapsed": round(phase_elapsed, 2),
                    "steps": phase_results,
                }
                logger.info(
                    "Phase %s completed in %.1fs", phase_name, phase_elapsed,
                )

        except KeyboardInterrupt:
            total_elapsed = time.monotonic() - pipeline_start
            logger.warning(
                "Pipeline interrupted after %.1fs", total_elapsed,
            )
            timing["total"] = round(total_elapsed, 2)
            timing["status"] = "interrupted"
            self.last_timing = timing
            raise

        # ---- Render report ----
        report_md = self.renderer.render(template, ctx)

        # ---- Write output ----
        slug = "_".join(ctx.tickers[:3])
        if len(ctx.tickers) > 3:
            slug += f"_+{len(ctx.tickers) - 3}"
        filename = f"{ctx.profile_name}_{slug}_{ctx.run_id}.md"
        report_path = output_dir / filename
        report_path.write_text(report_md)

        total_elapsed = time.monotonic() - pipeline_start
        timing["total"] = round(total_elapsed, 2)
        timing["status"] = "completed"
        self.last_timing = timing

        logger.info(
            "AsyncPipeline completed in %.1fs. Report: %s",
            total_elapsed, report_path,
        )

        return report_path
