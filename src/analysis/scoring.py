"""Composite stock scoring system - combines all analyses into a single score.

Produces a composite score (0-100) from analysis engines, plus a
conviction meta-score that measures agreement across dimensions.

Weights are loaded from configs/settings.yaml (single source of truth).
"""

import hashlib
import numpy as np

from src.analysis.technical import TechnicalAnalyzer
from src.analysis.fundamental import FundamentalAnalyzer
from src.analysis.valuation import ValuationAnalyzer, _mos_to_score
from src.analysis.sentiment import SentimentAnalyzer
from src.analysis.risk import RiskAnalyzer, compute_risk_score
from src.analysis.international import InternationalAnalyzer
from src.analysis.portfolio_risk import PortfolioRiskAnalyzer
from src.analysis.moat import MoatAnalyzer
from src.data_sources.market_data import MarketDataClient
from src.utils.logger import setup_logger

logger = setup_logger("scoring")


def _load_weights_from_settings() -> dict[str, float]:
    """Load engine weights from configs/settings.yaml (single source of truth).

    Falls back to hardcoded defaults if settings unavailable.
    """
    try:
        from src.config import SETTINGS
        registry = SETTINGS.get("analysis", {}).get("registry", {})
        weights = {}
        for name, cfg in registry.items():
            if cfg.get("enabled", True) and "weight" in cfg:
                weights[name] = cfg["weight"]
        if weights and abs(sum(weights.values()) - 1.0) < 0.05:
            return weights
        logger.warning("Settings weights sum to %.3f, using fallback", sum(weights.values()))
    except Exception as e:
        logger.warning("Could not load weights from settings.yaml: %s", e)

    # Fallback — must match settings.yaml
    return {
        "fundamental": 0.25,
        "valuation": 0.20,
        "technical": 0.18,
        "risk": 0.13,
        "international": 0.08,
        "sentiment": 0.07,
        "portfolio_risk": 0.07,
        "moat": 0.02,
    }


# Minimum weight coverage required to issue a recommendation.
# Below this threshold the system outputs "INSUFFICIENT DATA".
MIN_WEIGHT_COVERAGE = 0.50


class StockScorer:
    """Generate a composite investment score (0-100) for a stock."""

    WEIGHTS = _load_weights_from_settings()

    def __init__(self):
        self.market = MarketDataClient()
        self.tech = TechnicalAnalyzer()
        self.fund = FundamentalAnalyzer()
        self.val = ValuationAnalyzer()
        self.sent = SentimentAnalyzer()
        self.risk = RiskAnalyzer()
        self.intl = InternationalAnalyzer()
        self.port_risk = PortfolioRiskAnalyzer()
        self.moat = MoatAnalyzer()

    def score(self, ticker: str) -> dict:
        """Compute composite score for a stock."""
        logger.info("Scoring %s", ticker)
        scores: dict[str, float | None] = {}
        details = {}
        data_quality: dict[str, dict] = {}

        # Fundamental score (0-100)
        try:
            fund_result = self.fund.analyze(ticker)
            health = fund_result["health"]["score"] / max(fund_result["health"]["max_score"], 1)
            growth = fund_result["growth"]["score"] / max(fund_result["growth"]["max_score"], 1)
            val_score = fund_result["valuation"]["score"] / max(fund_result["valuation"]["max_score"], 1)

            # Incorporate new metrics if available
            sub_scores = [health * 0.25, growth * 0.20, val_score * 0.15]
            sub_total_weight = 0.60

            # ROIC — skip if score is None (data unavailable)
            roic = fund_result.get("roic", {})
            roic_score = roic.get("score")
            if roic_score is not None and roic.get("max_score"):
                roic_pct = roic_score / roic["max_score"]
                sub_scores.append(roic_pct * 0.15)
                sub_total_weight += 0.15

            # Piotroski F-Score — use dynamic max_score, skip if None
            piotroski = fund_result.get("piotroski", {})
            pio_score = piotroski.get("score")
            pio_max = piotroski.get("max_score", 0)
            if pio_score is not None and pio_max > 0:
                pio_pct = pio_score / pio_max
                sub_scores.append(pio_pct * 0.10)
                sub_total_weight += 0.10

            # Earnings quality — skip if score is None (data unavailable)
            eq = fund_result.get("earnings_quality", {})
            eq_score = eq.get("score")
            if eq_score is not None and eq.get("max_score"):
                eq_pct = eq_score / eq["max_score"]
                sub_scores.append(eq_pct * 0.08)
                sub_total_weight += 0.08

            # Capital allocation — skip if score is None (data unavailable)
            ca = fund_result.get("capital_allocation", {})
            ca_score = ca.get("score")
            if ca_score is not None and ca.get("max_score"):
                ca_pct = ca_score / ca["max_score"]
                sub_scores.append(ca_pct * 0.07)
                sub_total_weight += 0.07

            # Normalize to 100
            scores["fundamental"] = (sum(sub_scores) / sub_total_weight) * 100 if sub_total_weight > 0 else None
            details["fundamental"] = fund_result
            data_quality["fundamental"] = {"status": "ok", "error": None}
        except Exception as e:
            logger.error("Fundamental analysis failed: %s", e)
            scores["fundamental"] = None
            data_quality["fundamental"] = {"status": "failed", "error": str(e)}

        # Valuation score (0-100): Composite DCF 60% + Comps 25% + Quality 15%
        try:
            dcf = self.val.dcf_valuation(ticker)
            comps = self.val.comparable_valuation(ticker)

            # Multi-method composite fair value
            composite_val = {}
            try:
                composite_val = self.val.composite_fair_value(ticker)
                dcf["composite"] = composite_val
            except Exception as e:
                logger.warning("Composite valuation failed for %s: %s", ticker, e)

            # Use composite MOS for scoring if available, else fall back to FCF DCF
            if composite_val.get("margin_of_safety_pct") is not None and "error" not in composite_val:
                mos = composite_val["margin_of_safety_pct"]
            elif dcf.get("margin_of_safety_pct") is not None and "error" not in dcf:
                mos = dcf["margin_of_safety_pct"]
            else:
                mos = 0  # No valid valuation — neutral

            dcf_score = _mos_to_score(mos)

            # Comps score (25% weight)
            comps_score = 50
            if comps.get("comparison"):
                premiums = [v["premium_pct"] for v in comps["comparison"].values()
                            if v.get("premium_pct") is not None]
                if premiums:
                    avg_premium = sum(premiums) / len(premiums)
                    comps_score = max(0, min(100, 50 - avg_premium))

            # Quality score (15% weight) — reuse fundamental health
            quality_score = scores.get("fundamental") or 50

            scores["valuation"] = dcf_score * 0.60 + comps_score * 0.25 + quality_score * 0.15
            details["valuation"] = {
                "dcf": dcf,
                "comparables": comps,
                "dcf_score": round(dcf_score, 1),
                "comps_score": round(comps_score, 1),
                "quality_score": round(quality_score, 1),
            }
            data_quality["valuation"] = {"status": "ok", "error": None}
        except Exception as e:
            logger.error("Valuation analysis failed: %s", e)
            scores["valuation"] = None
            data_quality["valuation"] = {"status": "failed", "error": str(e)}

        # Technical score (0-100) — confidence-weighted, excludes non-directional signals
        try:
            df = self.market.get_price_history(ticker)
            signals = self.tech.get_signals(df)

            BUY_SIGNALS = {"BUY"}
            NEUTRAL_SIGNALS = {"HOLD", "NORMAL", "ELEVATED", "HIGH VOLUME", "LOW VOLUME"}
            SELL_SIGNALS = {"SELL"}

            weighted_sum = 0.0
            total_weight = 0.0
            for s in signals.values():
                sig = s.get("signal")
                if sig is None:
                    continue
                conf = s.get("confidence", "MEDIUM")
                w = 1.5 if conf == "HIGH" else 1.0 if conf == "MEDIUM" else 0.5

                if sig in BUY_SIGNALS:
                    weighted_sum += 1.0 * w
                elif sig in NEUTRAL_SIGNALS:
                    weighted_sum += 0.5 * w
                elif sig in SELL_SIGNALS:
                    weighted_sum += 0.0 * w
                else:
                    continue

                total_weight += w

            scores["technical"] = (weighted_sum / total_weight) * 100 if total_weight > 0 else None
            details["technical"] = signals
            data_quality["technical"] = {"status": "ok", "error": None}
        except Exception as e:
            logger.error("Technical analysis failed: %s", e)
            scores["technical"] = None
            data_quality["technical"] = {"status": "failed", "error": str(e)}

        # Sentiment score (0-100)
        try:
            sent = self.sent.analyze(ticker)
            scores["sentiment"] = max(0, min(100, 50 + sent["overall_score"] * 50))
            details["sentiment"] = sent
            data_quality["sentiment"] = {"status": "ok", "error": None}
        except Exception as e:
            logger.error("Sentiment analysis failed: %s", e)
            scores["sentiment"] = None
            data_quality["sentiment"] = {"status": "failed", "error": str(e)}

        # Risk score (0-100, higher = less risky = better)
        try:
            risk = self.risk.analyze(ticker)
            if "error" in risk:
                logger.warning("Risk analysis returned error for %s: %s", ticker, risk["error"])
                scores["risk"] = None
                data_quality["risk"] = {"status": "failed", "error": risk["error"]}
            else:
                score, sub_scores = compute_risk_score(risk)
                scores["risk"] = score
                risk["risk_sub_scores"] = sub_scores
                data_quality["risk"] = {"status": "ok", "error": None}
            details["risk"] = risk
        except Exception as e:
            logger.error("Risk analysis failed: %s", e)
            scores["risk"] = None
            data_quality["risk"] = {"status": "failed", "error": str(e)}

        # International score (0-100)
        try:
            intl_result = self.intl.analyze(ticker)
            # Scoring logic mirrors InternationalAnalyzerPlugin
            intl_score = 70.0
            adr = intl_result.get("adr_analysis", {})
            pz = adr.get("premium_z_score", 0)
            if abs(pz) > 2:
                intl_score -= 15
            elif abs(pz) > 1:
                intl_score -= 5
            fx = intl_result.get("fx_sensitivity", {})
            corr = abs(fx.get("correlation", 0))
            if corr > 0.4:
                intl_score -= 10
            elif corr > 0.2:
                intl_score -= 5
            country = intl_result.get("country", "United States")
            if country == "United States":
                intl_score = 80.0
            scores["international"] = round(max(0, min(100, intl_score)), 1)
            details["international"] = intl_result
            data_quality["international"] = {"status": "ok", "error": None}
        except Exception as e:
            logger.error("International analysis failed: %s", e)
            scores["international"] = None
            data_quality["international"] = {"status": "failed", "error": str(e)}

        # Portfolio risk — requires multi-holding context.
        # In single-stock mode, set to None so weight redistributes to
        # engines that actually provide signal for this ticker.
        try:
            port_result = self.port_risk.analyze([{"ticker": ticker, "weight": 1.0}])
            scores["portfolio_risk"] = None  # No signal in single-stock mode
            details["portfolio_risk"] = port_result
            data_quality["portfolio_risk"] = {
                "status": "skipped",
                "error": "Portfolio risk requires multi-holding context; weight redistributed",
            }
        except Exception as e:
            logger.error("Portfolio risk analysis failed: %s", e)
            scores["portfolio_risk"] = None
            data_quality["portfolio_risk"] = {"status": "failed", "error": str(e)}

        # Moat score (0-100, from competitive moat analysis)
        try:
            moat_result = self.moat.score_moat(ticker)
            scores["moat"] = moat_result.get("composite_moat_score")
            details["moat"] = moat_result
            data_quality["moat"] = {"status": "ok", "error": None}
        except Exception as e:
            logger.error("Moat analysis failed: %s", e)
            scores["moat"] = None
            data_quality["moat"] = {"status": "failed", "error": str(e)}

        # Composite — skip None scores, redistribute weights
        available = {k: v for k, v in scores.items() if v is not None and k in self.WEIGHTS}
        available_weight = sum(self.WEIGHTS[k] for k in available)
        if available_weight > 0:
            composite = sum(available[k] * self.WEIGHTS[k] / available_weight for k in available)
        else:
            composite = 50.0  # Total failure fallback

        # Minimum coverage threshold — refuse recommendation if too few engines succeeded
        insufficient_data = available_weight < MIN_WEIGHT_COVERAGE

        # Recommendation
        if insufficient_data:
            recommendation = "INSUFFICIENT DATA"
        elif composite >= 75:
            recommendation = "STRONG BUY"
        elif composite >= 60:
            recommendation = "BUY"
        elif composite >= 45:
            recommendation = "HOLD"
        elif composite >= 30:
            recommendation = "SELL"
        else:
            recommendation = "STRONG SELL"

        # Conviction meta-score (use available scores only)
        scores_for_conviction = {k: v for k, v in scores.items() if v is not None}
        conviction = self._compute_conviction(scores_for_conviction, details)

        # Cross-analyzer conflict detection
        conflicts = self._detect_conflicts(scores_for_conviction, details)

        # Red flags from fundamentals
        fund_detail = details.get("fundamental", {})
        red_flags = fund_detail.get("red_flags", {})

        # Data quality summary
        total_engines = len(data_quality)
        ok_engines = [k for k, v in data_quality.items() if v["status"] == "ok"]
        failed_engines = [k for k, v in data_quality.items() if v["status"] == "failed"]
        quality_summary = {
            "engines_succeeded": ok_engines,
            "engines_failed": failed_engines,
            "coverage_pct": round(len(ok_engines) / total_engines * 100, 1) if total_engines else 0,
            "weight_coverage_pct": round(available_weight * 100, 1),
            "details": data_quality,
        }

        # Model governance — fingerprint from weights + engine list
        model_version = self._model_version()

        # Backtest validation status per engine
        validation_status = {
            "backtest_validated": [
                k for k in available
                if k in ("technical", "risk")
            ],
            "backtest_unvalidated": [
                k for k in available
                if k not in ("technical", "risk")
            ],
            "note": (
                "Only price-based engines (technical, risk) are backtest-validated "
                "via walk-forward point-in-time scoring. Fundamental, valuation, "
                "sentiment, and other engines require historical data providers "
                "(e.g. Compustat) for true point-in-time backtesting."
            ),
        }

        return {
            "ticker": ticker,
            "composite_score": round(composite, 1),
            "recommendation": recommendation,
            "component_scores": {k: round(v, 1) for k, v in available.items()},
            "weights": self.WEIGHTS,
            "conviction": conviction,
            "conflicts": conflicts,
            "red_flags": red_flags,
            "data_quality": quality_summary,
            "validation_status": validation_status,
            "model_version": model_version,
            "details": details,
        }

    @classmethod
    def _model_version(cls) -> str:
        """Deterministic model fingerprint from weights and engine list."""
        sig = str(sorted(cls.WEIGHTS.items()))
        return "v1-" + hashlib.md5(sig.encode()).hexdigest()[:8]

    @staticmethod
    def _detect_conflicts(scores: dict, details: dict) -> dict:
        """Detect cross-analyzer conflicts that should flag for review.

        Looks for situations where different analysis dimensions
        strongly disagree, which lowers the reliability of the composite.
        """
        conflicts: list[dict] = []

        fund_score = scores.get("fundamental", 50)
        val_score = scores.get("valuation", 50)
        tech_score = scores.get("technical", 50)
        sent_score = scores.get("sentiment", 50)
        risk_score = scores.get("risk", 50)

        # 1. Technical BUY but DCF says overvalued
        if tech_score > 65 and val_score < 35:
            conflicts.append({
                "type": "technical_vs_valuation",
                "severity": "HIGH",
                "detail": f"Technical signals bullish ({tech_score:.0f}) but valuation bearish ({val_score:.0f}) — momentum may not be justified by fundamentals",
            })

        # 2. DCF undervalued but technical SELL (falling knife)
        if val_score > 65 and tech_score < 35:
            conflicts.append({
                "type": "valuation_vs_technical",
                "severity": "HIGH",
                "detail": f"Valuation attractive ({val_score:.0f}) but technicals bearish ({tech_score:.0f}) — potential value trap / falling knife",
            })

        # 3. Strong fundamentals but bearish sentiment
        if fund_score > 65 and sent_score < 35:
            conflicts.append({
                "type": "fundamental_vs_sentiment",
                "severity": "MEDIUM",
                "detail": f"Fundamentals strong ({fund_score:.0f}) but sentiment bearish ({sent_score:.0f}) — contrarian opportunity or market knows something",
            })

        # 4. High risk but bullish everything else
        avg_other = (fund_score + val_score + tech_score) / 3
        if risk_score < 30 and avg_other > 60:
            conflicts.append({
                "type": "risk_vs_opportunity",
                "severity": "MEDIUM",
                "detail": f"Bullish signals (avg {avg_other:.0f}) but high risk ({risk_score:.0f}) — size positions accordingly",
            })

        # 5. Insider selling while analyst targets high
        sent_detail = details.get("sentiment", {})
        insider_trades = sent_detail.get("raw_data", {}).get("insider_trades", [])
        analyst_targets = sent_detail.get("analyst_targets", {})
        if insider_trades:
            net_insider = sum(t.get("change", 0) for t in insider_trades[:10])
            upside = analyst_targets.get("upside_pct", 0)
            if net_insider < 0 and upside and upside > 20:
                conflicts.append({
                    "type": "insider_vs_analyst",
                    "severity": "MEDIUM",
                    "detail": f"Insiders net selling while analysts see {upside:.0f}% upside — insiders may have better information",
                })

        return {
            "conflicts": conflicts,
            "count": len(conflicts),
            "has_high_severity": any(c["severity"] == "HIGH" for c in conflicts),
        }

    @staticmethod
    def _compute_conviction(scores: dict, details: dict) -> dict:
        """Compute conviction level — how much agreement is there across dimensions.

        High conviction = most dimensions agree (all bullish or all bearish).
        Low conviction = mixed signals across dimensions.
        """
        # Normalize all scores to -1 (bearish) to +1 (bullish)
        normalized = {}
        for k, v in scores.items():
            normalized[k] = (v - 50) / 50  # maps 0-100 → -1 to +1

        vals = list(normalized.values())
        if len(vals) < 2:
            return {"level": "LOW", "score": 0, "detail": "Insufficient data"}

        std = float(np.std(vals))
        mean = float(np.mean(vals))
        # Low std = high agreement = high conviction
        agreement = max(0, 1 - std * 2)  # 0-1 scale
        extremity = abs(mean)  # 0-1 scale

        conviction_score = round((agreement * 0.6 + extremity * 0.4) * 100, 1)

        # Directional signals
        bullish_count = sum(1 for v in vals if v > 0.1)
        bearish_count = sum(1 for v in vals if v < -0.1)

        # Cross-dimensional confirmations.
        # Each confirmation is scaled by the agreement score so that
        # boosters amplify conviction only when engines already agree.
        # Max total boost capped at 15 points.
        boosters = []
        _MAX_TOTAL_BOOST = 15.0
        _total_boost = 0.0

        def _apply_boost(base_pts: float, label: str) -> None:
            nonlocal conviction_score, _total_boost
            if _total_boost >= _MAX_TOTAL_BOOST:
                return
            scaled = base_pts * agreement  # scale by inter-engine agreement
            scaled = min(scaled, _MAX_TOTAL_BOOST - _total_boost)
            if scaled > 0.5:  # Don't bother with negligible boosts
                conviction_score = min(100, conviction_score + scaled)
                _total_boost += scaled
                boosters.append(f"{label} (+{scaled:.1f})")

        # Piotroski confirmation — only boost if enough tests were evaluable
        piotroski = details.get("fundamental", {}).get("piotroski", {})
        pio_score = piotroski.get("score")
        pio_max = piotroski.get("max_score", 0)
        if pio_score is not None and pio_max >= 5:
            if pio_score >= 7:
                _apply_boost(6.0, "Piotroski F-Score confirms strength")
            elif pio_score <= 2 and pio_max >= 7:
                _apply_boost(6.0, "Piotroski F-Score confirms weakness")

        # Insider + analyst alignment
        sent = details.get("sentiment", {})
        insider_pct = sent.get("ownership", {}).get("insider_pct")
        analyst_targets = sent.get("analyst_targets", {})
        if insider_pct and insider_pct > 0.05 and analyst_targets.get("upside_pct", 0) > 15:
            _apply_boost(5.0, "Insiders hold significant stake + analysts see upside")

        # DCF + comps alignment
        val_details = details.get("valuation", {})
        dcf_mos = val_details.get("dcf", {}).get("margin_of_safety_pct", 0)
        comps_premium = 0
        comps_data = val_details.get("comparables", {}).get("comparison", {})
        if comps_data:
            premiums = [v.get("premium_pct", 0) for v in comps_data.values() if v.get("premium_pct") is not None]
            comps_premium = sum(premiums) / len(premiums) if premiums else 0
        if dcf_mos > 15 and comps_premium < -10:
            _apply_boost(6.0, "DCF and comps both signal undervaluation")
        elif dcf_mos < -15 and comps_premium > 10:
            _apply_boost(6.0, "DCF and comps both signal overvaluation")

        # Earnings quality confirmation
        eq = details.get("fundamental", {}).get("earnings_quality", {})
        if eq.get("fcf_ni_ratio") is not None and eq["fcf_ni_ratio"] > 1.2:
            _apply_boost(4.0, "High earnings quality (FCF > Net Income)")

        if conviction_score >= 70:
            level = "HIGH"
        elif conviction_score >= 45:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {
            "level": level,
            "score": conviction_score,
            "bullish_dimensions": bullish_count,
            "bearish_dimensions": bearish_count,
            "agreement": round(agreement, 3),
            "boosters": boosters,
        }
