# FE-Analyst Standard Operating Procedures

**Version:** 1.0
**Last Updated:** 2026-02-09
**Owner:** FE-Analyst Platform Team

---

## Overview

This directory contains the complete set of Standard Operating Procedures (SOPs) governing the FE-Analyst stock and company analysis platform. These SOPs define how data is collected, validated, analyzed, scored, and communicated -- covering the full lifecycle from raw data ingestion through final report delivery and quality assurance.

All SOPs are designed for use by both human analysts and AI agents operating within the platform.

---

## Table of Contents

| SOP | Title | Description |
|-----|-------|-------------|
| [SOP-001](01_data_collection_and_source_validation.md) | Data Collection & Source Validation | Procedures for ingesting data from all sources (yfinance, Finnhub, SEC filings), validating provenance, detecting staleness, and handling cross-source discrepancies. |
| [SOP-002](02_financial_statement_analysis.md) | Financial Statement Analysis | Systematic dissection of income statements, balance sheets, and cash flow statements to produce Financial Health, Growth Profile, and Valuation sub-scores. |
| [SOP-003](03_valuation_methodologies.md) | Valuation Methodologies | Intrinsic value determination using DCF, comparable analysis, and other methods. Governs the ValuationAnalyzer module (25% of composite score). |
| [SOP-004](04_risk_assessment_and_scenario_analysis.md) | Risk Assessment & Scenario Analysis | Identification, quantification, and communication of investment risks. Covers the risk module contributing 15% weight to the composite score. |
| [SOP-005](05_competitive_and_moat_analysis.md) | Competitive & Moat Analysis | Evaluation of economic moats across six dimensions: market dominance, switching costs, technology lock-in, supply chain criticality, and more. |
| [SOP-006](06_technical_analysis.md) | Technical Analysis | Technical indicators, chart pattern recognition, trend analysis, and momentum signals for timing and confirmation of fundamental views. |
| [SOP-007](07_report_writing_and_communication.md) | Report Writing & Communication | Standards for structuring, writing, and presenting investment research. Ensures reports are actionable, rigorous, and accessible. |
| [SOP-008](08_quality_assurance_and_peer_review.md) | Quality Assurance & Peer Review | Defense-in-depth QA framework covering data validation, calculation verification, analytical review, and output quality layers. |

---

## How to Use

**Starting a new analysis?** Begin with **SOP-001** to ensure clean data, then proceed through SOPs 002-005 for the analytical work.

**Writing up findings?** Follow **SOP-007** for report structure and **SOP-008** for the review checklist before publishing.

**Debugging a score anomaly?** Trace the issue through the relevant analytical SOP (002-006), then verify data integrity via **SOP-001**.

**General guidance:**
- SOPs 001-006 follow the analysis pipeline in order -- each builds on the outputs of its predecessors.
- SOP-007 and SOP-008 apply to all outputs regardless of which analytical SOPs were used.
- When in doubt, check SOP-008 for the QA checklist that covers cross-SOP validation requirements.

---

## Quick Reference Matrix

| Analysis Task | Primary SOP | Supporting SOPs |
|---------------|-------------|-----------------|
| Fetching market data / SEC filings | 001 | 008 |
| Income statement / balance sheet review | 002 | 001, 008 |
| DCF or comparable valuation | 003 | 001, 002 |
| Risk scoring and scenario modeling | 004 | 001, 002, 003 |
| Moat and competitive positioning | 005 | 001, 002 |
| Technical indicators and chart analysis | 006 | 001 |
| Drafting an investment report | 007 | 002, 003, 004, 005 |
| Peer review and QA sign-off | 008 | All |
| Full company analysis (end-to-end) | 001-008 | -- |
| Composite score calculation | 002, 003, 004, 005 | 001, 006, 008 |

---

## Conventions

- **SOP numbering** follows the analytical pipeline order (001-006), then communication (007), then QA (008).
- **All SOPs reference the composite scoring system** (0-100 scale) defined in `src/analysis/scoring.py`.
- **Configuration files** are in `configs/` -- primarily `settings.yaml` and `ai_moat_universe.yaml`.
- **Module mappings** are noted in each SOP's metadata header.

---

## Version History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-02-09 | 1.0 | FE-Analyst Team | Initial release of all 8 SOPs and this index. |
| | | | |
| | | | |

---

*This document is the entry point for all FE-Analyst SOPs. Keep it updated whenever SOPs are added, revised, or retired.*
