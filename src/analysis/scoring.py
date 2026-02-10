"""Hedge-fund-grade composite scoring engine.

Combines fundamental, valuation, technical, sentiment, risk, and moat analyses
into a confidence-weighted, regime-aware composite score with signal-interaction
detection and conviction-graded recommendations.

Architecture
------------
Each analysis engine returns a dict with at least a ``"score"`` key (0-100).
The scorer wraps every engine call, extracts its score, computes a data-quality
*confidence* weight (0-1), applies regime-based weight adjustments, detects
cross-signal interactions (value traps, momentum divergence, etc.), and
produces a fully-decomposed output suitable for portfolio-construction systems.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd

from src.analysis.technical import TechnicalAnalyzer
from src.analysis.fundamental import FundamentalAnalyzer
from src.analysis.valuation import ValuationAnalyzer
from src.analysis.sentiment import SentimentAnalyzer
from src.analysis.risk import RiskAnalyzer
from src.analysis.moat import MoatAnalyzer
from src.data_sources.market_data import MarketDataClient
from src.utils.logger import setup_logger

logger = setup_logger("scoring")

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
RegimeType = Literal["bull", "bear", "volatile", "normal"]
RecommendationType = Literal[
    "STRONG BUY", "BUY", "BUY WITH CAUTION", "HOLD",
    "SELL", "STRONG SELL",
]
ConvictionLevel = Literal["HIGH", "MEDIUM", "LOW"]

# ---------------------------------------------------------------------------
# Default base weights -- sum to 1.0
# ---------------------------------------------------------------------------
_BASE_WEIGHTS: Dict[str, float] = {
    "fundamental": 0.25,
    "valuation": 0.20,
    "technical": 0.15,
    "sentiment": 0.10,
    "risk": 0.15,
    "moat": 0.15,
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_NEUTRAL_SCORE: float = 50.0
_NEUTRAL_CONFIDENCE: float = 0.2


# ===================================================================
# Confidence estimators
# ===================================================================

def _fundamental_confidence(result: Dict[str, Any]) -> float:
    """Estimate confidence based on how many sub-models produced real data.

    Checks: Piotroski flags available, Altman Z computable, DuPont
    decomposition, quality-of-earnings, capital allocation, trends.
    """
    available = 0
    total = 6

    piotroski = result.get("piotroski", {})
    if piotroski.get("f_score") is not None:
        available += 1

    altman = result.get("altman_z", {})
    if altman.get("z_score") is not None:
        available += 1

    dupont = result.get("dupont", {})
    if dupont.get("current", {}).get("roe") is not None:
        available += 1

    quality = result.get("quality_of_earnings", {})
    if quality.get("accrual_ratio") is not None or quality.get("cash_conversion_ratio") is not None:
        available += 1

    capital = result.get("capital_allocation", {})
    if capital.get("roic") is not None:
        available += 1

    trends = result.get("trends", {})
    if trends.get("revenue_cagr") is not None:
        available += 1

    ratio = available / total
    # Map to confidence: all 6 -> 1.0, 4 -> ~0.7, 2 -> ~0.35, 0 -> 0.1
    return max(0.1, round(ratio, 4))


def _valuation_confidence(result: Dict[str, Any]) -> float:
    """1.0 if DCF + Monte Carlo both ran, 0.7 if only DCF, 0.3 on error."""
    dcf_ok = "error" not in result.get("dcf", {"error": True})
    mc_ok = "error" not in result.get("monte_carlo", {"error": True})

    if dcf_ok and mc_ok:
        return 1.0
    if dcf_ok:
        return 0.7
    return 0.3


def _technical_confidence(data_length: int) -> float:
    """Confidence based on number of OHLCV bars available.

    >200 bars -> 1.0, >50 -> 0.7, else 0.3.
    """
    if data_length > 200:
        return 1.0
    if data_length > 50:
        return 0.7
    return 0.3


def _risk_confidence(result: Dict[str, Any]) -> float:
    """1.0 if the factor model ran successfully, 0.6 otherwise."""
    factor = result.get("factor_model", {})
    if "error" not in factor and factor.get("r_squared") is not None:
        return 1.0
    return 0.6


def _sentiment_confidence(result: Dict[str, Any]) -> float:
    """Use the 'confidence' field returned by the sentiment engine."""
    return float(result.get("confidence", 0.3))


def _moat_confidence(has_overrides: bool) -> float:
    """1.0 if moat overrides were provided, 0.5 if using defaults."""
    return 1.0 if has_overrides else 0.5


# ===================================================================
# Regime detection & weight adjustment
# ===================================================================

def _detect_regime(market: MarketDataClient) -> RegimeType:
    """Auto-detect market regime from SPY price data.

    Bull:     SPY 50-day SMA > 200-day SMA and ATR-based volatility low
    Bear:     SPY 50-day SMA < 200-day SMA
    Volatile: ATR (14-day) as fraction of price > 2% (VIX proxy)
    Normal:   default fallback
    """
    try:
        df = market.get_price_history("SPY", period="1y", interval="1d")
        if df is None or df.empty or len(df) < 200:
            return "normal"

        close = df["Close"].values.astype(float)
        high = df["High"].values.astype(float)
        low = df["Low"].values.astype(float)

        sma_50 = float(np.mean(close[-50:]))
        sma_200 = float(np.mean(close[-200:]))

        # ATR-14 as volatility proxy (substitute for VIX)
        tr_values: List[float] = []
        for i in range(1, min(15, len(close))):
            tr = max(
                high[-i] - low[-i],
                abs(high[-i] - close[-i - 1]),
                abs(low[-i] - close[-i - 1]),
            )
            tr_values.append(tr)
        atr_14 = float(np.mean(tr_values)) if tr_values else 0.0
        current_price = float(close[-1])
        atr_pct = atr_14 / current_price if current_price > 0 else 0.0

        # Volatile check first (can override bull/bear)
        if atr_pct > 0.02:
            return "volatile"
        if sma_50 > sma_200:
            return "bull"
        if sma_50 < sma_200:
            return "bear"
        return "normal"

    except Exception as exc:
        logger.warning("Regime detection failed, defaulting to 'normal': %s", exc)
        return "normal"


def _apply_regime_adjustments(
    weights: Dict[str, float],
    regime: RegimeType,
) -> Dict[str, float]:
    """Return a new weight dict with regime-specific adjustments applied.

    Adjustments are multiplicative on the base weight:
      Bull:     technical +20%, risk -20%
      Bear:     risk +30%, technical -20%, fundamental +10%
      Volatile: risk +40%, sentiment -50%
      Normal:   no change

    After adjustment, weights are re-normalized to sum to 1.0.
    """
    adjusted = dict(weights)

    if regime == "bull":
        adjusted["technical"] *= 1.20
        adjusted["risk"] *= 0.80
    elif regime == "bear":
        adjusted["risk"] *= 1.30
        adjusted["technical"] *= 0.80
        adjusted["fundamental"] *= 1.10
    elif regime == "volatile":
        adjusted["risk"] *= 1.40
        adjusted["sentiment"] *= 0.50

    # Re-normalize to sum to 1.0
    total = sum(adjusted.values())
    if total > 0:
        adjusted = {k: v / total for k, v in adjusted.items()}

    return adjusted


# ===================================================================
# Signal interaction detection
# ===================================================================

def _detect_signal_interactions(
    scores: Dict[str, float],
) -> Tuple[List[str], Dict[str, float]]:
    """Detect cross-signal interactions and return flags + score caps.

    Returns
    -------
    flags : list[str]
        Human-readable interaction flags.
    caps : dict[str, float]
        Component-name -> maximum allowed score (for value-trap capping).
    """
    flags: List[str] = []
    caps: Dict[str, float] = {}

    fundamental = scores.get("fundamental", _NEUTRAL_SCORE)
    valuation = scores.get("valuation", _NEUTRAL_SCORE)
    technical = scores.get("technical", _NEUTRAL_SCORE)
    risk = scores.get("risk", _NEUTRAL_SCORE)

    # Value trap: fundamentals weak but appears cheap
    if fundamental < 40 and valuation > 70:
        flags.append(
            "potential_value_trap: weak fundamentals (score={:.1f}) "
            "but high valuation score ({:.1f}) -- may be a value trap".format(
                fundamental, valuation,
            )
        )
        caps["valuation"] = 50.0

    # Momentum divergence: technicals strong but fundamentals weak
    if technical > 70 and fundamental < 40:
        flags.append(
            "momentum_without_fundamentals: strong technicals (score={:.1f}) "
            "not supported by fundamentals ({:.1f})".format(
                technical, fundamental,
            )
        )

    # Quality premium flag (applied as multiplier later, not a cap)
    if fundamental > 75:
        flags.append(
            "quality_premium: strong fundamental quality (score={:.1f}) "
            "-- 1.1x composite multiplier applied".format(fundamental)
        )

    # Distress discount flag (applied as multiplier later)
    if risk < 25:
        flags.append(
            "distress_discount: speculative risk profile (score={:.1f}) "
            "-- 0.9x composite multiplier applied".format(risk)
        )

    return flags, caps


# ===================================================================
# Recommendation engine
# ===================================================================

def _compute_conviction(scores: Dict[str, float]) -> ConvictionLevel:
    """Conviction based on how tightly component scores agree.

    HIGH:   all within 15 pts of each other
    MEDIUM: all within 25 pts
    LOW:    spread > 25 pts
    """
    if not scores:
        return "LOW"

    values = list(scores.values())
    spread = max(values) - min(values)

    if spread <= 15:
        return "HIGH"
    if spread <= 25:
        return "MEDIUM"
    return "LOW"


def _compute_recommendation(
    composite: float,
    risk_score: float,
    conviction: ConvictionLevel,
) -> RecommendationType:
    """Determine recommendation from composite score, risk, and conviction.

    Base thresholds:
      STRONG BUY  >= 80
      BUY         >= 65
      HOLD        40 - 65
      SELL        25 - 40
      STRONG SELL < 25

    Risk adjustment:
      If the base recommendation is BUY or STRONG BUY but risk_score < 35
      (aggressive/speculative), downgrade to "BUY WITH CAUTION".
    """
    if composite >= 80:
        base: RecommendationType = "STRONG BUY"
    elif composite >= 65:
        base = "BUY"
    elif composite >= 40:
        base = "HOLD"
    elif composite >= 25:
        base = "SELL"
    else:
        base = "STRONG SELL"

    # Risk-adjusted downgrade
    if base in ("STRONG BUY", "BUY") and risk_score < 35:
        return "BUY WITH CAUTION"

    return base


def _generate_key_reasons(
    component_details: Dict[str, Dict[str, Any]],
    scores: Dict[str, float],
    flags: List[str],
) -> List[str]:
    """Generate 1-3 concise key reasons for the recommendation.

    Draws from the highest-contributing and lowest-contributing components
    and any detected interaction flags.
    """
    reasons: List[str] = []

    if not scores:
        return ["Insufficient data for analysis"]

    # Sort components by score (descending)
    sorted_comps = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Top positive driver
    best_name, best_score = sorted_comps[0]
    if best_score >= 60:
        detail_snippet = _extract_reason_snippet(best_name, component_details.get(best_name, {}))
        reasons.append(
            f"Strong {best_name} signal (score {best_score:.1f})"
            + (f": {detail_snippet}" if detail_snippet else "")
        )

    # Top negative driver
    worst_name, worst_score = sorted_comps[-1]
    if worst_score < 40:
        detail_snippet = _extract_reason_snippet(worst_name, component_details.get(worst_name, {}))
        reasons.append(
            f"Weak {worst_name} signal (score {worst_score:.1f})"
            + (f": {detail_snippet}" if detail_snippet else "")
        )

    # Add first interaction flag if present
    for flag in flags:
        short_flag = flag.split(":")[0].replace("_", " ")
        reasons.append(f"Signal interaction detected: {short_flag}")
        break

    # Ensure at least one reason
    if not reasons:
        mid_name, mid_score = sorted_comps[len(sorted_comps) // 2]
        reasons.append(f"Balanced signals -- {mid_name} at {mid_score:.1f}")

    return reasons[:3]


def _extract_reason_snippet(component: str, details: Dict[str, Any]) -> str:
    """Pull a one-liner from component details for the reason string."""
    if component == "fundamental":
        piotroski = details.get("piotroski", {})
        f_score = piotroski.get("f_score")
        interp = piotroski.get("interpretation", "")
        if f_score is not None:
            return f"Piotroski F-Score {f_score}/9 ({interp})"
        health = details.get("health", {})
        reasons_list = health.get("reasons", [])
        if reasons_list:
            return reasons_list[0]

    elif component == "valuation":
        dcf = details.get("dcf", {})
        mos = dcf.get("margin_of_safety_pct")
        verdict = dcf.get("verdict", "")
        if mos is not None:
            return f"DCF margin of safety {mos:+.1f}% ({verdict})"

    elif component == "technical":
        scoring_data = details.get("scoring", {})
        bias = scoring_data.get("bias", "")
        score_val = scoring_data.get("score")
        if bias:
            return f"Technical bias: {bias}" + (f" (score {score_val})" if score_val else "")

    elif component == "sentiment":
        label = details.get("composite_label", "")
        conf = details.get("confidence", 0)
        if label:
            return f"{label} sentiment (confidence {conf:.0%})"

    elif component == "risk":
        classification = details.get("risk_classification", {})
        tier = classification.get("risk_tier", "")
        risk_flags = classification.get("risk_flags", [])
        if tier:
            snippet = f"Risk tier: {tier}"
            if risk_flags:
                snippet += f" [{', '.join(risk_flags[:2])}]"
            return snippet

    elif component == "moat":
        moat_class = details.get("moat_classification", "")
        if moat_class:
            return f"Moat: {moat_class}"

    return ""


def _identify_key_drivers(
    contributions: Dict[str, float],
) -> Dict[str, List[Dict[str, Any]]]:
    """Return top 3 positive and top 3 negative drivers by contribution."""
    sorted_items = sorted(contributions.items(), key=lambda x: x[1], reverse=True)

    positive = [
        {"component": name, "contribution": round(val, 2)}
        for name, val in sorted_items if val > 0
    ][:3]

    negative = [
        {"component": name, "contribution": round(val, 2)}
        for name, val in reversed(sorted_items) if val < 0
    ][:3]

    # If all positive, still report bottom 3 as "least contributing"
    if not negative:
        negative = [
            {"component": name, "contribution": round(val, 2)}
            for name, val in reversed(sorted_items)
        ][:3]

    return {"positive": positive, "negative": negative}


# ===================================================================
# Main Scorer
# ===================================================================

class StockScorer:
    """Hedge-fund-grade composite stock scoring system.

    Produces a confidence-weighted, regime-aware composite score (0-100)
    with signal-interaction detection and conviction-graded recommendations.

    Parameters
    ----------
    base_weights : dict[str, float] | None
        Override default component weights. Keys: fundamental, valuation,
        technical, sentiment, risk, moat. Must sum to ~1.0.
    """

    def __init__(
        self,
        base_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.base_weights: Dict[str, float] = dict(base_weights or _BASE_WEIGHTS)
        self.market = MarketDataClient()
        self.tech = TechnicalAnalyzer()
        self.fund = FundamentalAnalyzer()
        self.val = ValuationAnalyzer()
        self.sent = SentimentAnalyzer()
        self.risk = RiskAnalyzer()
        self.moat = MoatAnalyzer()

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def score(
        self,
        ticker: str,
        regime: Optional[RegimeType] = None,
        moat_overrides: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Compute the composite investment score for *ticker*.

        Parameters
        ----------
        ticker : str
            Stock symbol (e.g. ``"AAPL"``).
        regime : str | None
            Market regime override: ``"bull"``, ``"bear"``, ``"volatile"``,
            ``"normal"``.  Auto-detected from SPY data when ``None``.
        moat_overrides : dict | None
            Manual qualitative moat dimension scores (0-100).

        Returns
        -------
        dict
            JSON-serializable result with keys:
            ``composite_score``, ``recommendation``, ``conviction``,
            ``regime``, ``component_scores`` (per-component breakdown),
            ``flags``, ``key_drivers``, ``key_reasons``, ``details``.
        """
        logger.info("Scoring %s", ticker)

        # -- 1. Detect or accept regime ------------------------------------
        effective_regime: RegimeType = regime or _detect_regime(self.market)

        # -- 2. Fetch price data once (shared by technical & risk) ----------
        price_df: Optional[pd.DataFrame] = None
        data_length: int = 0
        try:
            price_df = self.market.get_price_history(ticker, period="2y")
            if price_df is not None and not price_df.empty:
                data_length = len(price_df)
        except Exception as exc:
            logger.error("Failed to fetch price data for %s: %s", ticker, exc)

        # -- 3. Run each analysis engine -----------------------------------
        raw_scores: Dict[str, float] = {}
        confidences: Dict[str, float] = {}
        details: Dict[str, Dict[str, Any]] = {}

        # 3a. Fundamental
        fund_result = self._run_fundamental(ticker)
        raw_scores["fundamental"] = fund_result["score"]
        confidences["fundamental"] = fund_result["confidence"]
        details["fundamental"] = fund_result["data"]

        # 3b. Valuation
        val_result = self._run_valuation(ticker)
        raw_scores["valuation"] = val_result["score"]
        confidences["valuation"] = val_result["confidence"]
        details["valuation"] = val_result["data"]

        # 3c. Technical
        tech_result = self._run_technical(ticker, price_df, data_length)
        raw_scores["technical"] = tech_result["score"]
        confidences["technical"] = tech_result["confidence"]
        details["technical"] = tech_result["data"]

        # 3d. Sentiment
        sent_result = self._run_sentiment(ticker)
        raw_scores["sentiment"] = sent_result["score"]
        confidences["sentiment"] = sent_result["confidence"]
        details["sentiment"] = sent_result["data"]

        # 3e. Risk
        risk_result = self._run_risk(ticker)
        raw_scores["risk"] = risk_result["score"]
        confidences["risk"] = risk_result["confidence"]
        details["risk"] = risk_result["data"]

        # 3f. Moat
        moat_result = self._run_moat(ticker, moat_overrides)
        raw_scores["moat"] = moat_result["score"]
        confidences["moat"] = moat_result["confidence"]
        details["moat"] = moat_result["data"]

        # -- 4. Signal interaction detection --------------------------------
        flags, score_caps = _detect_signal_interactions(raw_scores)

        # Apply caps (value-trap capping)
        capped_scores: Dict[str, float] = {}
        for comp, sc in raw_scores.items():
            cap = score_caps.get(comp)
            if cap is not None and sc > cap:
                capped_scores[comp] = cap
            else:
                capped_scores[comp] = sc

        # -- 5. Regime-aware weight adjustment ------------------------------
        regime_weights = _apply_regime_adjustments(self.base_weights, effective_regime)

        # -- 6. Confidence-weighted scoring --------------------------------
        effective_weights: Dict[str, float] = {}
        for comp in regime_weights:
            effective_weights[comp] = regime_weights[comp] * confidences.get(comp, _NEUTRAL_CONFIDENCE)

        # Re-normalize effective weights to sum to 1.0
        ew_total = sum(effective_weights.values())
        if ew_total > 0:
            effective_weights = {k: v / ew_total for k, v in effective_weights.items()}

        # Compute weighted composite
        composite: float = sum(
            capped_scores.get(comp, _NEUTRAL_SCORE) * effective_weights.get(comp, 0.0)
            for comp in effective_weights
        )

        # Per-component contribution to composite
        contributions: Dict[str, float] = {}
        for comp in effective_weights:
            comp_contribution = (
                (capped_scores.get(comp, _NEUTRAL_SCORE) - _NEUTRAL_SCORE)
                * effective_weights.get(comp, 0.0)
            )
            contributions[comp] = round(comp_contribution, 4)

        # -- 7. Apply quality premium / distress discount multipliers ------
        multiplier: float = 1.0
        if raw_scores.get("fundamental", _NEUTRAL_SCORE) > 75:
            multiplier *= 1.1
        if raw_scores.get("risk", _NEUTRAL_SCORE) < 25:
            multiplier *= 0.9

        composite = composite * multiplier
        composite = max(0.0, min(100.0, composite))

        # -- 8. Recommendation, conviction, reasons -------------------------
        conviction = _compute_conviction(raw_scores)
        recommendation = _compute_recommendation(
            composite, raw_scores.get("risk", _NEUTRAL_SCORE), conviction,
        )
        key_reasons = _generate_key_reasons(details, raw_scores, flags)
        key_drivers = _identify_key_drivers(contributions)

        # -- 9. Build per-component breakdown --------------------------------
        component_breakdown: Dict[str, Dict[str, Any]] = {}
        for comp in effective_weights:
            component_breakdown[comp] = {
                "raw_score": round(raw_scores.get(comp, _NEUTRAL_SCORE), 2),
                "confidence": round(confidences.get(comp, _NEUTRAL_CONFIDENCE), 4),
                "effective_weight": round(effective_weights.get(comp, 0.0), 4),
                "contribution_to_composite": round(contributions.get(comp, 0.0), 4),
            }

        # -- 10. Assemble final output --------------------------------------
        return {
            "ticker": ticker,
            "composite_score": round(composite, 1),
            "recommendation": recommendation,
            "conviction": conviction,
            "regime": effective_regime,
            "multiplier_applied": round(multiplier, 2),
            "component_scores": component_breakdown,
            "flags": flags,
            "key_drivers": key_drivers,
            "key_reasons": key_reasons,
            "weights": {
                "base": {k: round(v, 4) for k, v in self.base_weights.items()},
                "regime_adjusted": {k: round(v, 4) for k, v in regime_weights.items()},
                "confidence_weighted": {k: round(v, 4) for k, v in effective_weights.items()},
            },
            "details": details,
        }

    # ------------------------------------------------------------------ #
    # Engine runners (each returns score, confidence, data)               #
    # ------------------------------------------------------------------ #

    def _run_fundamental(self, ticker: str) -> Dict[str, Any]:
        """Run fundamental analysis and extract score + confidence."""
        try:
            result = self.fund.analyze(ticker)
            score = float(result.get("score", _NEUTRAL_SCORE))
            confidence = _fundamental_confidence(result)
            return {"score": score, "confidence": confidence, "data": result}
        except Exception as exc:
            logger.error("Fundamental analysis failed for %s: %s", ticker, exc)
            return {
                "score": _NEUTRAL_SCORE,
                "confidence": _NEUTRAL_CONFIDENCE,
                "data": {"error": str(exc)},
            }

    def _run_valuation(self, ticker: str) -> Dict[str, Any]:
        """Run valuation analysis (DCF + Monte Carlo + comps) and extract score + confidence."""
        try:
            # Run DCF
            dcf: Dict[str, Any] = {}
            try:
                dcf = self.val.dcf_valuation(ticker)
            except Exception as dcf_exc:
                logger.warning("DCF valuation failed for %s: %s", ticker, dcf_exc)
                dcf = {"error": str(dcf_exc)}

            # Run Monte Carlo
            mc: Dict[str, Any] = {}
            try:
                mc = self.val.monte_carlo_dcf(ticker)
            except Exception as mc_exc:
                logger.warning("Monte Carlo DCF failed for %s: %s", ticker, mc_exc)
                mc = {"error": str(mc_exc)}

            # Compute valuation score from DCF margin-of-safety + MC probability
            dcf_mos = dcf.get("margin_of_safety_pct", 0.0) if "error" not in dcf else 0.0
            mc_prob = mc.get("probability_undervalued_pct", 50.0) if "error" not in mc else 50.0

            dcf_score = max(0.0, min(100.0, 50.0 + dcf_mos))
            mc_score = max(0.0, min(100.0, mc_prob))

            dcf_ok = "error" not in dcf
            mc_ok = "error" not in mc

            if dcf_ok and mc_ok:
                score = 0.6 * dcf_score + 0.4 * mc_score
            elif dcf_ok:
                score = dcf_score
            elif mc_ok:
                score = mc_score
            else:
                score = _NEUTRAL_SCORE

            score = max(0.0, min(100.0, score))

            combined_result: Dict[str, Any] = {"dcf": dcf, "monte_carlo": mc}
            confidence = _valuation_confidence(combined_result)
            return {"score": score, "confidence": confidence, "data": combined_result}

        except Exception as exc:
            logger.error("Valuation analysis failed for %s: %s", ticker, exc)
            return {
                "score": _NEUTRAL_SCORE,
                "confidence": 0.3,
                "data": {"error": str(exc)},
            }

    def _run_technical(
        self,
        ticker: str,
        price_df: Optional[pd.DataFrame],
        data_length: int,
    ) -> Dict[str, Any]:
        """Run technical analysis and extract score + confidence."""
        if price_df is None or price_df.empty:
            return {
                "score": _NEUTRAL_SCORE,
                "confidence": 0.3,
                "data": {"error": "No price data available"},
            }

        try:
            result = self.tech.full_analysis(price_df)
            score = float(result.get("score", _NEUTRAL_SCORE))
            confidence = _technical_confidence(data_length)
            return {"score": score, "confidence": confidence, "data": result}
        except Exception as exc:
            logger.error("Technical analysis failed for %s: %s", ticker, exc)
            # Fallback: try basic signals
            try:
                signals = self.tech.get_signals(price_df)
                buy_count = sum(1 for s in signals.values() if s.get("signal") == "BUY")
                total = max(len(signals), 1)
                score = (buy_count / total) * 100
                return {
                    "score": score,
                    "confidence": _technical_confidence(data_length) * 0.7,
                    "data": {"signals": signals, "fallback": True},
                }
            except Exception as inner_exc:
                logger.error("Technical fallback also failed for %s: %s", ticker, inner_exc)
                return {
                    "score": _NEUTRAL_SCORE,
                    "confidence": _NEUTRAL_CONFIDENCE,
                    "data": {"error": str(exc)},
                }

    def _run_sentiment(self, ticker: str) -> Dict[str, Any]:
        """Run sentiment analysis and extract score + confidence."""
        try:
            result = self.sent.analyze(ticker)
            score = float(result.get("composite_score", result.get("score", _NEUTRAL_SCORE)))
            confidence = _sentiment_confidence(result)
            return {"score": score, "confidence": confidence, "data": result}
        except Exception as exc:
            logger.error("Sentiment analysis failed for %s: %s", ticker, exc)
            return {
                "score": _NEUTRAL_SCORE,
                "confidence": _NEUTRAL_CONFIDENCE,
                "data": {"error": str(exc)},
            }

    def _run_risk(self, ticker: str) -> Dict[str, Any]:
        """Run risk analysis and extract score + confidence.

        Note: risk score is 0-100 where higher = less risky = better.
        """
        try:
            result = self.risk.analyze(ticker)
            score = float(result.get("score", _NEUTRAL_SCORE))
            confidence = _risk_confidence(result)
            return {"score": score, "confidence": confidence, "data": result}
        except Exception as exc:
            logger.error("Risk analysis failed for %s: %s", ticker, exc)
            return {
                "score": _NEUTRAL_SCORE,
                "confidence": _NEUTRAL_CONFIDENCE,
                "data": {"error": str(exc)},
            }

    def _run_moat(
        self,
        ticker: str,
        moat_overrides: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Run moat analysis and extract score + confidence."""
        try:
            result = self.moat.score_moat(ticker, moat_overrides=moat_overrides)
            score = float(result.get("composite_moat_score", _NEUTRAL_SCORE))
            has_overrides = bool(moat_overrides)
            confidence = _moat_confidence(has_overrides)
            # Add the score key for consistency
            result["score"] = score
            return {"score": score, "confidence": confidence, "data": result}
        except Exception as exc:
            logger.error("Moat analysis failed for %s: %s", ticker, exc)
            return {
                "score": _NEUTRAL_SCORE,
                "confidence": _NEUTRAL_CONFIDENCE,
                "data": {"error": str(exc)},
            }
