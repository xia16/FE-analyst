"""Jinja2-based markdown report renderer."""

from __future__ import annotations
from pathlib import Path

import numpy as np
from jinja2 import Environment, FileSystemLoader

from src.config import Paths
from src.pipeline.context import PipelineContext
from src.utils.logger import setup_logger

logger = setup_logger("renderer")


def fmt_num(val, currency="$") -> str:
    if val is None:
        return "N/A"
    try:
        val = float(val)
    except (TypeError, ValueError):
        return str(val)
    if np.isnan(val):
        return "N/A"
    if abs(val) >= 1e12:
        return f"{currency}{val/1e12:.1f}T"
    elif abs(val) >= 1e9:
        return f"{currency}{val/1e9:.1f}B"
    elif abs(val) >= 1e6:
        return f"{currency}{val/1e6:.1f}M"
    elif abs(val) >= 1e3:
        return f"{currency}{val/1e3:.1f}K"
    else:
        return f"{currency}{val:.2f}"


def fmt_pct(val) -> str:
    if val is None:
        return "N/A"
    try:
        return f"{float(val)*100:.1f}%"
    except (TypeError, ValueError):
        return str(val)


def fmt_ratio(val) -> str:
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.2f}"
    except (TypeError, ValueError):
        return str(val)


class ReportRenderer:
    """Render PipelineContext into markdown using Jinja2 templates."""

    def __init__(self, template_dir: Path | None = None):
        tpl_dir = template_dir or Paths.REPORTS_TEMPLATES
        self.env = Environment(
            loader=FileSystemLoader(str(tpl_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["fmt_num"] = fmt_num
        self.env.filters["fmt_pct"] = fmt_pct
        self.env.filters["fmt_ratio"] = fmt_ratio

    def render(self, template_name: str, ctx: PipelineContext) -> str:
        template = self.env.get_template(template_name)
        return template.render(ctx=ctx, now=ctx.started_at)
