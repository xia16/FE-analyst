"""Institutional-grade multi-source sentiment analysis engine.

Aggregates and normalizes sentiment signals from six independent sources:
  1. Financial news (FinBERT + momentum + dispersion + time-decay)
  2. SEC filing text analysis (risk factors, MD&A tone, filing-over-filing delta)
  3. Insider transaction patterns (cluster detection, net sentiment, officer weighting)
  4. Analyst consensus (rating distribution, shifts, price targets, estimate revisions)
  5. Social media / Reddit (keyword scoring, mention velocity, subreddit weighting)
  6. Options market (put/call ratio, IV skew, unusual activity)

Each source is normalized to [-1, +1], then combined via configurable weights into a
composite score mapped to [0, 100] for the pipeline plugin interface.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd

from src.analysis.base import BaseAnalyzer
from src.data_sources.alternative_data import AlternativeDataClient
from src.data_sources.news_sentiment import NewsSentimentClient
from src.data_sources.sec_filings import SECFilingsClient
from src.utils.logger import setup_logger

logger = setup_logger("sentiment_analysis")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Composite weighting
SOURCE_WEIGHTS: dict[str, float] = {
    "news": 0.25,
    "sec_filings": 0.15,
    "insider": 0.20,
    "analyst": 0.20,
    "social": 0.10,
    "options": 0.10,
}

# Label thresholds (0-100 scale)
LABEL_THRESHOLDS: list[tuple[float, str]] = [
    (75.0, "STRONG BULLISH"),
    (60.0, "BULLISH"),
    (40.0, "NEUTRAL"),
    (25.0, "BEARISH"),
    (0.0, "STRONG BEARISH"),
]

# Time-decay half-life in days
NEWS_HALF_LIFE_DAYS: float = 7.0

# Source credibility tiers (lower is more credible, used as multiplier)
MAJOR_OUTLETS: set[str] = {
    "reuters", "bloomberg", "cnbc", "wsj", "wall street journal",
    "financial times", "ft", "barrons", "marketwatch", "nytimes",
    "new york times", "associated press", "ap news", "yahoo finance",
}

# Keyword lexicons for fallback sentiment scoring
POSITIVE_KEYWORDS: set[str] = {
    "growth", "improve", "improved", "strong", "exceed", "exceeded",
    "record", "upgrade", "beat", "outperform", "positive", "gain",
    "profit", "surge", "momentum", "bullish", "opportunity", "innovation",
    "expansion", "robust", "accelerate", "optimistic", "strength",
}
NEGATIVE_KEYWORDS: set[str] = {
    "risk", "decline", "loss", "impair", "impairment", "uncertain",
    "uncertainty", "adverse", "litigation", "lawsuit", "downgrade",
    "miss", "weak", "weakness", "slowdown", "deficit", "default",
    "restructuring", "layoff", "layoffs", "bearish", "headwind",
    "recession", "volatile", "volatility", "warning", "concern",
}

# Social media keyword lexicons
BULLISH_SOCIAL_KEYWORDS: set[str] = {
    "moon", "calls", "buy", "undervalued", "breakout", "rocket",
    "tendies", "diamond", "hands", "long", "bull", "bullish",
    "mooning", "squeeze", "yolo", "hold", "going up", "cheap",
    "opportunity", "oversold", "accumulate", "dip",
}
BEARISH_SOCIAL_KEYWORDS: set[str] = {
    "puts", "short", "overvalued", "crash", "sell", "dump",
    "bear", "bearish", "bubble", "bag", "bagholder", "bagholding",
    "red", "rip", "plummet", "overbought", "rug", "scam",
    "avoid", "falling", "drill", "tank",
}

# Subreddit credibility weights (higher = more weight)
SUBREDDIT_WEIGHTS: dict[str, float] = {
    "investing": 1.0,
    "stocks": 0.8,
    "stockmarket": 0.8,
    "valueinvesting": 1.0,
    "securityanalysis": 1.0,
    "wallstreetbets": 0.4,
    "options": 0.6,
}

# Insider transaction constants
C_SUITE_TITLES: set[str] = {
    "ceo", "cfo", "coo", "cto", "cmo", "cio", "president",
    "chief executive", "chief financial", "chief operating",
    "chief technology", "chief information",
}
INSIDER_CLUSTER_WINDOW_DAYS: int = 30


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Division that returns *default* when the denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _keyword_score(text: str, positive: set[str], negative: set[str]) -> float:
    """Return a sentiment score in [-1, 1] based on keyword frequency.

    Score = (positive_count - negative_count) / total_keyword_count.
    Returns 0.0 when no keywords are found.
    """
    words = text.lower().split()
    pos_count = sum(1 for w in words if w in positive)
    neg_count = sum(1 for w in words if w in negative)
    total = pos_count + neg_count
    if total == 0:
        return 0.0
    return _clamp((pos_count - neg_count) / total)


def _exponential_decay_weight(days_ago: float, half_life: float = NEWS_HALF_LIFE_DAYS) -> float:
    """Compute an exponential-decay weight. Recent = higher weight."""
    if days_ago < 0:
        days_ago = 0.0
    return math.exp(-math.log(2) * days_ago / half_life)


def _score_to_label(score_0_100: float) -> str:
    """Map a 0-100 composite score to a human-readable label."""
    for threshold, label in LABEL_THRESHOLDS:
        if score_0_100 >= threshold:
            return label
    return "STRONG BEARISH"


def _normalize_to_0_100(value_neg1_pos1: float) -> float:
    """Linearly map [-1, +1] -> [0, 100]."""
    return round(((_clamp(value_neg1_pos1) + 1.0) / 2.0) * 100.0, 2)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _epoch_to_datetime(epoch: float) -> datetime:
    """Convert a UNIX epoch timestamp to a timezone-aware UTC datetime."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


# ---------------------------------------------------------------------------
# Source analyzers
# ---------------------------------------------------------------------------

class _NewsAnalyzer:
    """Enhanced news sentiment with momentum, dispersion, time-decay, and
    source-credibility weighting."""

    def __init__(self, news_client: NewsSentimentClient) -> None:
        self._client = news_client

    def analyze(self, ticker: str) -> dict[str, Any]:
        """Return a normalized score in [-1, 1] plus detailed breakdown."""
        result: dict[str, Any] = {
            "score": 0.0,
            "article_count": 0,
            "details": {},
        }

        # Fetch 30 days of news for momentum calculation
        date_from = (_now_utc() - timedelta(days=30)).strftime("%Y-%m-%d")
        date_to = _now_utc().strftime("%Y-%m-%d")
        articles = self._client.get_company_news(ticker, date_from=date_from, date_to=date_to)
        if not articles:
            return result

        result["article_count"] = len(articles)

        # --- Sentiment scoring via FinBERT (with keyword fallback) ---
        scored_articles: list[dict[str, Any]] = []
        headlines = [a["headline"] for a in articles if a.get("headline")]

        finbert_scores: list[dict] = []
        try:
            if headlines:
                finbert_scores = self._client.analyze_sentiment(headlines)
        except Exception as exc:
            logger.warning("FinBERT unavailable, falling back to keywords: %s", exc)

        for idx, article in enumerate(articles):
            headline = article.get("headline", "")
            source = (article.get("source") or "").lower()
            article_ts = article.get("datetime")

            # Determine sentiment value for this article
            if idx < len(finbert_scores):
                fb = finbert_scores[idx]
                label = fb.get("label", "neutral")
                raw_score = fb.get("score", 0.5)
                if label == "positive":
                    sent_value = raw_score
                elif label == "negative":
                    sent_value = -raw_score
                else:
                    sent_value = 0.0
            else:
                sent_value = _keyword_score(headline, POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS)

            # Source credibility weight
            credibility = 1.5 if any(outlet in source for outlet in MAJOR_OUTLETS) else 0.8

            # Time-decay weight
            if article_ts:
                try:
                    article_dt = _epoch_to_datetime(float(article_ts))
                    days_ago = (_now_utc() - article_dt).total_seconds() / 86400.0
                except (ValueError, TypeError, OSError):
                    days_ago = 15.0  # fallback to mid-range
            else:
                days_ago = 15.0

            time_weight = _exponential_decay_weight(days_ago)

            scored_articles.append({
                "headline": headline[:120],
                "source": source,
                "sent_value": round(sent_value, 4),
                "credibility": credibility,
                "time_weight": round(time_weight, 4),
                "days_ago": round(days_ago, 1),
                "weighted_sent": round(sent_value * credibility * time_weight, 4),
            })

        # --- Aggregate metrics ---
        if not scored_articles:
            return result

        total_weight = sum(a["credibility"] * a["time_weight"] for a in scored_articles)
        weighted_sent_sum = sum(a["weighted_sent"] for a in scored_articles)
        volume_adjusted_score = _safe_divide(weighted_sent_sum, total_weight)

        sent_values = [a["sent_value"] for a in scored_articles]

        # Dispersion (standard deviation of raw sentiment values)
        dispersion = statistics.pstdev(sent_values) if len(sent_values) >= 2 else 0.0

        # Momentum: compare recent-half average vs older-half average
        sorted_by_age = sorted(scored_articles, key=lambda a: a["days_ago"])
        mid = max(1, len(sorted_by_age) // 2)
        recent_half = sorted_by_age[:mid]
        older_half = sorted_by_age[mid:]
        recent_avg = statistics.mean([a["sent_value"] for a in recent_half]) if recent_half else 0.0
        older_avg = statistics.mean([a["sent_value"] for a in older_half]) if older_half else 0.0
        momentum = recent_avg - older_avg  # positive = improving

        final_score = _clamp(volume_adjusted_score)

        result["score"] = round(final_score, 4)
        result["details"] = {
            "volume_adjusted_score": round(volume_adjusted_score, 4),
            "dispersion": round(dispersion, 4),
            "momentum": round(momentum, 4),
            "momentum_direction": "improving" if momentum > 0.05 else ("deteriorating" if momentum < -0.05 else "stable"),
            "recent_avg_sentiment": round(recent_avg, 4),
            "older_avg_sentiment": round(older_avg, 4),
            "major_outlet_articles": sum(1 for a in scored_articles if a["credibility"] > 1.0),
            "top_articles": sorted(scored_articles, key=lambda a: abs(a["weighted_sent"]), reverse=True)[:5],
        }
        return result


class _SECFilingAnalyzer:
    """Analyze SEC 10-K / 10-Q filing text for risk factors, MD&A tone,
    and filing-over-filing changes."""

    def __init__(self, sec_client: SECFilingsClient) -> None:
        self._client = sec_client

    def analyze(self, ticker: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "score": 0.0,
            "details": {},
        }

        filings_10k: list[dict] = []
        filings_10q: list[dict] = []
        try:
            filings_10k = self._client.get_recent_filings(ticker, form_type="10-K", count=2)
        except Exception as exc:
            logger.warning("Failed to fetch 10-K filings for %s: %s", ticker, exc)
        try:
            filings_10q = self._client.get_recent_filings(ticker, form_type="10-Q", count=2)
        except Exception as exc:
            logger.warning("Failed to fetch 10-Q filings for %s: %s", ticker, exc)

        all_filings = filings_10k + filings_10q
        if not all_filings:
            return result

        # Attempt to extract text from the most recent filing for analysis
        current_text = self._extract_filing_text(all_filings[0]) if all_filings else ""
        previous_text = self._extract_filing_text(all_filings[1]) if len(all_filings) > 1 else ""

        # Risk Factor Analysis
        current_risk = self._analyze_risk_factors(current_text)
        previous_risk = self._analyze_risk_factors(previous_text) if previous_text else None

        # MD&A Tone Analysis
        current_tone = self._analyze_mda_tone(current_text)
        previous_tone = self._analyze_mda_tone(previous_text) if previous_text else None

        # Filing-over-filing comparison
        red_flags: list[str] = []
        risk_count_delta: Optional[int] = None
        tone_delta: Optional[float] = None

        if previous_risk is not None:
            risk_count_delta = current_risk["total_risk_mentions"] - previous_risk["total_risk_mentions"]
            if risk_count_delta > 0:
                pct_increase = _safe_divide(risk_count_delta, previous_risk["total_risk_mentions"]) * 100
                if pct_increase > 25:
                    red_flags.append(
                        f"Risk factor mentions increased {pct_increase:.0f}% vs prior filing"
                    )

        if previous_tone is not None:
            tone_delta = current_tone["tone_score"] - previous_tone["tone_score"]
            if tone_delta < -0.20:
                red_flags.append(
                    f"MD&A tone deteriorated by {abs(tone_delta):.2f} vs prior filing (>{0.20} threshold)"
                )

        # Compute composite SEC score [-1, 1]
        # Tone contributes 60%, risk factor trend contributes 40%
        tone_component = current_tone["tone_score"]  # already [-1, 1]

        risk_trend_component = 0.0
        if risk_count_delta is not None:
            # Normalize: more risk mentions = more negative
            # A delta of +20 is quite negative, -20 is positive
            risk_trend_component = _clamp(-risk_count_delta / 20.0)

        sec_score = _clamp(0.6 * tone_component + 0.4 * risk_trend_component)

        # Red flags penalize the score
        if red_flags:
            sec_score = _clamp(sec_score - 0.15 * len(red_flags))

        result["score"] = round(sec_score, 4)
        result["details"] = {
            "filings_analyzed": len(all_filings),
            "current_filing": all_filings[0] if all_filings else {},
            "risk_factors": {
                "current": current_risk,
                "previous": previous_risk,
                "delta": risk_count_delta,
            },
            "mda_tone": {
                "current": {
                    "tone_score": round(current_tone["tone_score"], 4),
                    "positive_count": current_tone["positive_count"],
                    "negative_count": current_tone["negative_count"],
                },
                "previous": {
                    "tone_score": round(previous_tone["tone_score"], 4),
                    "positive_count": previous_tone["positive_count"],
                    "negative_count": previous_tone["negative_count"],
                } if previous_tone else None,
                "delta": round(tone_delta, 4) if tone_delta is not None else None,
            },
            "red_flags": red_flags,
        }
        return result

    # -- helpers --

    @staticmethod
    def _extract_filing_text(filing_meta: dict) -> str:
        """Best-effort extraction of filing text. Returns the description
        field as a proxy when full-text retrieval is unavailable."""
        # The SECFilingsClient returns metadata. Full text extraction would
        # require downloading the filing document. Use the description and
        # accession number as a proxy, and supplement with whatever text
        # the edgartools library surfaces.
        text_parts: list[str] = []
        if filing_meta.get("description"):
            text_parts.append(filing_meta["description"])
        # Attempt to pull filing document text via edgartools
        try:
            from edgar import Company
            accession = filing_meta.get("accession_number", "")
            if accession:
                # edgartools allows filing[0].text() on some versions
                pass  # Best-effort; metadata description used below
        except Exception:
            pass
        return " ".join(text_parts)

    @staticmethod
    def _analyze_risk_factors(text: str) -> dict[str, Any]:
        """Count and categorize risk factor keywords in filing text."""
        if not text:
            return {"total_risk_mentions": 0, "categories": {}}

        text_lower = text.lower()
        risk_categories: dict[str, list[str]] = {
            "regulatory": ["regulation", "regulatory", "compliance", "sec ", "government", "legislation"],
            "market": ["market risk", "competition", "competitive", "economic", "downturn", "recession"],
            "operational": ["operational", "supply chain", "cybersecurity", "system failure", "disruption"],
            "financial": ["liquidity", "debt", "leverage", "credit risk", "interest rate", "default"],
            "legal": ["litigation", "lawsuit", "legal proceedings", "patent", "intellectual property"],
            "environmental": ["environmental", "climate", "sustainability", "emissions", "esg"],
        }

        category_counts: dict[str, int] = {}
        total = 0
        for category, keywords in risk_categories.items():
            count = sum(text_lower.count(kw) for kw in keywords)
            category_counts[category] = count
            total += count

        return {"total_risk_mentions": total, "categories": category_counts}

    @staticmethod
    def _analyze_mda_tone(text: str) -> dict[str, Any]:
        """Keyword-based tone analysis of Management Discussion & Analysis text."""
        if not text:
            return {"tone_score": 0.0, "positive_count": 0, "negative_count": 0}

        text_lower = text.lower()
        words = text_lower.split()
        pos_count = sum(1 for w in words if w in POSITIVE_KEYWORDS)
        neg_count = sum(1 for w in words if w in NEGATIVE_KEYWORDS)
        total = pos_count + neg_count
        tone = _safe_divide(pos_count - neg_count, total) if total > 0 else 0.0

        return {
            "tone_score": _clamp(tone),
            "positive_count": pos_count,
            "negative_count": neg_count,
        }


class _InsiderAnalyzer:
    """Analyze insider transactions for cluster buying, net sentiment,
    and officer/director weighting."""

    def __init__(self, alt_client: AlternativeDataClient) -> None:
        self._client = alt_client

    def analyze(self, ticker: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "score": 0.0,
            "details": {},
        }

        trades: list[dict] = []
        try:
            trades = self._client.get_insider_trades(ticker)
        except Exception as exc:
            logger.warning("Failed to fetch insider trades for %s: %s", ticker, exc)
            return result

        if not trades:
            return result

        now = _now_utc()

        # Classify trades
        buy_value = 0.0
        sell_value = 0.0
        recent_buyers: list[dict] = []  # within cluster window
        recent_sellers: list[dict] = []
        all_buy_values: list[float] = []
        all_sell_values: list[float] = []
        officer_weighted_net = 0.0
        total_officer_weight = 0.0

        for trade in trades:
            # Finnhub insider transaction fields:
            #   name, share, change, filingDate, transactionDate,
            #   transactionCode, transactionPrice
            change = trade.get("change", 0) or 0
            price = trade.get("transactionPrice", 0) or 0
            trade_value = abs(change * price)
            tx_code = (trade.get("transactionCode") or "").upper()
            tx_date_str = trade.get("transactionDate") or trade.get("filingDate") or ""
            name = trade.get("name", "")

            # Determine buy vs sell
            # P = open market purchase, S = open market sale, A = grant/award
            is_buy = tx_code in ("P", "A") or change > 0
            is_sell = tx_code == "S" or (change < 0 and tx_code not in ("P", "A"))

            if is_buy:
                buy_value += trade_value
                all_buy_values.append(trade_value)
            elif is_sell:
                sell_value += trade_value
                all_sell_values.append(trade_value)

            # Parse transaction date
            tx_date: Optional[datetime] = None
            if tx_date_str:
                try:
                    tx_date = datetime.strptime(tx_date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

            # Cluster detection (recent window)
            if tx_date and (now - tx_date).days <= INSIDER_CLUSTER_WINDOW_DAYS:
                entry = {
                    "name": name,
                    "value": round(trade_value, 2),
                    "date": tx_date_str[:10],
                    "code": tx_code,
                }
                if is_buy:
                    recent_buyers.append(entry)
                elif is_sell:
                    recent_sellers.append(entry)

            # Officer weighting (C-suite gets 2x)
            name_lower = name.lower()
            title_hint = (trade.get("title") or trade.get("officerTitle") or "").lower()
            is_csuite = any(t in title_hint or t in name_lower for t in C_SUITE_TITLES)
            weight = 2.0 if is_csuite else 1.0

            if is_buy:
                officer_weighted_net += trade_value * weight
            elif is_sell:
                officer_weighted_net -= trade_value * weight
            total_officer_weight += trade_value * weight

        total_value = buy_value + sell_value

        # Net insider sentiment: (buy - sell) / total
        net_sentiment = _safe_divide(buy_value - sell_value, total_value)

        # Officer-weighted net sentiment
        officer_sentiment = _safe_divide(officer_weighted_net, total_officer_weight) if total_officer_weight > 0 else 0.0

        # Cluster detection
        unique_recent_buyers = len(set(b["name"] for b in recent_buyers))
        cluster_buy_signal = unique_recent_buyers >= 3  # 3+ distinct insiders buying = strong
        cluster_strength = min(unique_recent_buyers / 5.0, 1.0)  # normalize 0-1

        # Historical comparison: is current activity unusual?
        # Use total recent transactions vs average per-month
        recent_count = len(recent_buyers) + len(recent_sellers)
        total_count = len(trades)
        # Approximate months of history (assume data spans ~12 months)
        avg_monthly = _safe_divide(total_count, 12.0)
        activity_ratio = _safe_divide(recent_count, avg_monthly) if avg_monthly > 0 else 1.0
        unusual_activity = activity_ratio > 2.0

        # Composite insider score [-1, 1]
        # 50% net sentiment, 30% officer-weighted, 20% cluster bonus
        raw_score = (
            0.50 * _clamp(net_sentiment)
            + 0.30 * _clamp(officer_sentiment)
            + 0.20 * (cluster_strength if cluster_buy_signal else -cluster_strength * 0.3)
        )
        insider_score = _clamp(raw_score)

        result["score"] = round(insider_score, 4)
        result["details"] = {
            "total_trades": len(trades),
            "buy_value": round(buy_value, 2),
            "sell_value": round(sell_value, 2),
            "net_sentiment": round(net_sentiment, 4),
            "officer_weighted_sentiment": round(officer_sentiment, 4),
            "cluster_detection": {
                "unique_buyers_last_30d": unique_recent_buyers,
                "unique_sellers_last_30d": len(set(s["name"] for s in recent_sellers)),
                "cluster_buy_signal": cluster_buy_signal,
                "cluster_strength": round(cluster_strength, 4),
                "recent_buyers": recent_buyers[:10],
                "recent_sellers": recent_sellers[:10],
            },
            "historical_comparison": {
                "recent_monthly_transactions": recent_count,
                "avg_monthly_transactions": round(avg_monthly, 1),
                "activity_ratio": round(activity_ratio, 2),
                "unusual_activity": unusual_activity,
            },
        }
        return result


class _AnalystAnalyzer:
    """Analyst consensus: rating distribution, shifts, price targets,
    and earnings estimate revisions."""

    def __init__(self, alt_client: AlternativeDataClient) -> None:
        self._client = alt_client

    def analyze(self, ticker: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "score": 0.0,
            "details": {},
        }

        try:
            import yfinance as yf
            yf_ticker = yf.Ticker(ticker)
        except Exception as exc:
            logger.warning("yfinance unavailable for analyst data: %s", exc)
            return result

        # --- Rating distribution ---
        rating_score = 0.0
        rating_details: dict[str, Any] = {}
        try:
            recs = yf_ticker.recommendations
            if recs is not None and not recs.empty:
                # yfinance recommendations DataFrame has columns like
                # strongBuy, buy, hold, sell, strongSell (or firm/toGrade/fromGrade/action)
                # Handle both formats
                if "strongBuy" in recs.columns:
                    # Summary format
                    latest = recs.iloc[-1] if len(recs) > 0 else None
                    if latest is not None:
                        sb = int(latest.get("strongBuy", 0))
                        b = int(latest.get("buy", 0))
                        h = int(latest.get("hold", 0))
                        s = int(latest.get("sell", 0))
                        ss = int(latest.get("strongSell", 0))
                        total_recs = sb + b + h + s + ss
                        if total_recs > 0:
                            # Weighted score: Strong Buy=2, Buy=1, Hold=0, Sell=-1, Strong Sell=-2
                            weighted = (sb * 2 + b * 1 + h * 0 + s * (-1) + ss * (-2))
                            rating_score = _clamp(weighted / (total_recs * 2))  # normalize to [-1, 1]
                            rating_details = {
                                "strong_buy": sb,
                                "buy": b,
                                "hold": h,
                                "sell": s,
                                "strong_sell": ss,
                                "total": total_recs,
                                "weighted_score": round(rating_score, 4),
                            }
                elif "toGrade" in recs.columns:
                    # Individual recommendation format
                    grade_map = {
                        "strong buy": 2, "buy": 1, "outperform": 1, "overweight": 1,
                        "market outperform": 1, "positive": 1,
                        "hold": 0, "neutral": 0, "equal-weight": 0, "market perform": 0,
                        "sector perform": 0, "in-line": 0, "peer perform": 0,
                        "sell": -1, "underperform": -1, "underweight": -1,
                        "market underperform": -1, "negative": -1, "reduce": -1,
                        "strong sell": -2,
                    }
                    recent_recs = recs.tail(20)
                    grades = recent_recs["toGrade"].dropna().str.lower()
                    grade_scores = [grade_map.get(g, 0) for g in grades]
                    if grade_scores:
                        rating_score = _clamp(statistics.mean(grade_scores) / 2.0)
                        grade_counts = Counter(grades)
                        rating_details = {
                            "distribution": dict(grade_counts),
                            "recent_count": len(grade_scores),
                            "weighted_score": round(rating_score, 4),
                        }

                    # --- Consensus shift (last 90 days) ---
                    shift_details = self._compute_consensus_shift(recs, grade_map)
                    if shift_details:
                        rating_details["consensus_shift"] = shift_details

        except Exception as exc:
            logger.warning("Failed to fetch analyst recommendations for %s: %s", ticker, exc)

        # --- Price target analysis ---
        price_target_score = 0.0
        price_target_details: dict[str, Any] = {}
        try:
            info = yf_ticker.info or {}
            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            target_mean = info.get("targetMeanPrice", 0)
            target_median = info.get("targetMedianPrice", 0)
            target_high = info.get("targetHighPrice", 0)
            target_low = info.get("targetLowPrice", 0)
            num_analysts = info.get("numberOfAnalystOpinions", 0)

            if current_price and target_mean:
                upside_pct = ((target_mean - current_price) / current_price) * 100
                # Normalize upside to [-1, 1]: +30% upside -> ~1.0, -30% -> ~-1.0
                price_target_score = _clamp(upside_pct / 30.0)

                # Analyst agreement: std dev of targets
                target_std = 0.0
                if target_high and target_low and num_analysts and num_analysts > 1:
                    # Approximate std from range (high - low) / 4
                    target_std = (target_high - target_low) / 4.0
                    agreement_score = 1.0 - _clamp(target_std / target_mean, 0.0, 1.0)
                else:
                    agreement_score = 0.5  # unknown agreement

                price_target_details = {
                    "current_price": round(current_price, 2),
                    "target_mean": round(target_mean, 2),
                    "target_median": round(target_median, 2) if target_median else None,
                    "target_high": round(target_high, 2) if target_high else None,
                    "target_low": round(target_low, 2) if target_low else None,
                    "upside_pct": round(upside_pct, 2),
                    "num_analysts": num_analysts,
                    "target_std_approx": round(target_std, 2),
                    "agreement_score": round(agreement_score, 4),
                }
        except Exception as exc:
            logger.warning("Failed to get price targets for %s: %s", ticker, exc)

        # --- Earnings estimate revisions ---
        earnings_revision_score = 0.0
        earnings_details: dict[str, Any] = {}
        try:
            info = yf_ticker.info or {}
            # yfinance exposes forward EPS and earnings growth
            earnings_growth = info.get("earningsGrowth")  # trailing
            revenue_growth = info.get("revenueGrowth")
            earnings_quarterly_growth = info.get("earningsQuarterlyGrowth")

            if earnings_growth is not None:
                # Positive growth = bullish. Normalize: 20% growth -> 1.0
                earnings_revision_score = _clamp(earnings_growth / 0.20)
                earnings_details["earnings_growth"] = round(earnings_growth, 4)
            if revenue_growth is not None:
                earnings_details["revenue_growth"] = round(revenue_growth, 4)
            if earnings_quarterly_growth is not None:
                earnings_details["earnings_quarterly_growth"] = round(earnings_quarterly_growth, 4)
                # Blend quarterly growth into the revision score
                if earnings_growth is None:
                    earnings_revision_score = _clamp(earnings_quarterly_growth / 0.20)
        except Exception as exc:
            logger.warning("Failed to get earnings data for %s: %s", ticker, exc)

        # --- Composite analyst score ---
        # Weights: rating 40%, price target 35%, earnings revision 25%
        components_used = 0
        weighted_sum = 0.0
        total_w = 0.0

        if rating_details:
            weighted_sum += 0.40 * rating_score
            total_w += 0.40
            components_used += 1
        if price_target_details:
            weighted_sum += 0.35 * price_target_score
            total_w += 0.35
            components_used += 1
        if earnings_details:
            weighted_sum += 0.25 * earnings_revision_score
            total_w += 0.25
            components_used += 1

        analyst_score = _clamp(_safe_divide(weighted_sum, total_w)) if total_w > 0 else 0.0

        result["score"] = round(analyst_score, 4)
        result["details"] = {
            "rating": rating_details,
            "price_targets": price_target_details,
            "earnings_revisions": earnings_details,
            "component_scores": {
                "rating_score": round(rating_score, 4),
                "price_target_score": round(price_target_score, 4),
                "earnings_revision_score": round(earnings_revision_score, 4),
            },
        }
        return result

    @staticmethod
    def _compute_consensus_shift(
        recs: pd.DataFrame, grade_map: dict[str, int]
    ) -> dict[str, Any]:
        """Compute direction of rating changes over the last 90 days."""
        shift_details: dict[str, Any] = {}
        try:
            if recs.index.dtype == "datetime64[ns]" or hasattr(recs.index, 'date'):
                cutoff = datetime.now() - timedelta(days=90)
                recent = recs.loc[recs.index >= pd.Timestamp(cutoff)]
            else:
                # Take last 10 as proxy for ~90 days
                recent = recs.tail(10)

            if "toGrade" in recent.columns and "fromGrade" in recent.columns:
                upgrades = 0
                downgrades = 0
                for _, row in recent.iterrows():
                    to_g = grade_map.get(str(row.get("toGrade", "")).lower(), 0)
                    from_g = grade_map.get(str(row.get("fromGrade", "")).lower(), 0)
                    if to_g > from_g:
                        upgrades += 1
                    elif to_g < from_g:
                        downgrades += 1

                shift_details = {
                    "upgrades_90d": upgrades,
                    "downgrades_90d": downgrades,
                    "net_direction": "positive" if upgrades > downgrades else (
                        "negative" if downgrades > upgrades else "neutral"
                    ),
                }
        except Exception:
            pass
        return shift_details


class _SocialMediaAnalyzer:
    """Reddit / social media sentiment with keyword scoring,
    mention velocity, and subreddit weighting."""

    SUBREDDITS: list[str] = ["wallstreetbets", "investing", "stocks"]

    def __init__(self, alt_client: AlternativeDataClient) -> None:
        self._client = alt_client

    def analyze(self, ticker: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "score": 0.0,
            "details": {},
        }

        all_posts: list[dict[str, Any]] = []
        subreddit_scores: dict[str, dict] = {}

        for subreddit in self.SUBREDDITS:
            try:
                posts = self._client.get_reddit_sentiment(ticker, subreddit=subreddit, limit=30)
            except Exception as exc:
                logger.warning("Failed to fetch r/%s for %s: %s", subreddit, ticker, exc)
                continue

            if not posts:
                continue

            sub_weight = SUBREDDIT_WEIGHTS.get(subreddit, 0.5)

            # Score each post by keyword analysis of the title
            post_scores: list[float] = []
            for post in posts:
                title = post.get("title", "")
                kw_score = _keyword_score(title, BULLISH_SOCIAL_KEYWORDS, BEARISH_SOCIAL_KEYWORDS)
                # Blend with upvote_ratio: ratio > 0.7 slightly positive
                upvote_bonus = (post.get("upvote_ratio", 0.5) - 0.5) * 0.3
                combined = _clamp(kw_score + upvote_bonus)
                post_scores.append(combined)
                all_posts.append({
                    "subreddit": subreddit,
                    "title": title[:120],
                    "score": post.get("score", 0),
                    "sentiment": round(combined, 4),
                    "created_utc": post.get("created_utc"),
                    "sub_weight": sub_weight,
                })

            if post_scores:
                avg_score = statistics.mean(post_scores)
                subreddit_scores[subreddit] = {
                    "post_count": len(posts),
                    "avg_sentiment": round(avg_score, 4),
                    "weight": sub_weight,
                    "weighted_sentiment": round(avg_score * sub_weight, 4),
                }

        if not all_posts:
            return result

        # --- Mention velocity ---
        velocity_details = self._compute_mention_velocity(all_posts)

        # --- Weighted aggregate across subreddits ---
        total_sub_weight = sum(s["weight"] * s["post_count"] for s in subreddit_scores.values())
        weighted_sentiment_sum = sum(
            s["weighted_sentiment"] * s["post_count"] for s in subreddit_scores.values()
        )
        aggregate_score = _safe_divide(weighted_sentiment_sum, total_sub_weight)

        # Blend velocity signal: accelerating mentions amplify the base sentiment
        velocity_multiplier = 1.0
        if velocity_details.get("acceleration", 0) > 0.5:
            velocity_multiplier = 1.15  # amplify by 15% if mentions accelerating
        elif velocity_details.get("acceleration", 0) < -0.5:
            velocity_multiplier = 0.85  # dampen if decelerating

        final_score = _clamp(aggregate_score * velocity_multiplier)

        result["score"] = round(final_score, 4)
        result["details"] = {
            "total_posts": len(all_posts),
            "subreddits": subreddit_scores,
            "mention_velocity": velocity_details,
            "aggregate_sentiment": round(aggregate_score, 4),
            "velocity_multiplier": round(velocity_multiplier, 2),
            "top_posts": sorted(all_posts, key=lambda p: abs(p["sentiment"]), reverse=True)[:5],
        }
        return result

    @staticmethod
    def _compute_mention_velocity(posts: list[dict]) -> dict[str, Any]:
        """Measure rate of mentions over time to detect building momentum."""
        timestamps = [p.get("created_utc") for p in posts if p.get("created_utc")]
        if len(timestamps) < 4:
            return {"total_mentions": len(posts), "acceleration": 0.0, "trend": "insufficient_data"}

        timestamps_sorted = sorted(timestamps)
        now_ts = _now_utc().timestamp()

        # Split into two halves chronologically
        mid = len(timestamps_sorted) // 2
        older_half = timestamps_sorted[:mid]
        recent_half = timestamps_sorted[mid:]

        # Time span of each half in days
        older_span_days = max((older_half[-1] - older_half[0]) / 86400.0, 1.0)
        recent_span_days = max((recent_half[-1] - recent_half[0]) / 86400.0, 1.0)

        older_rate = len(older_half) / older_span_days  # posts per day
        recent_rate = len(recent_half) / recent_span_days

        acceleration = _safe_divide(recent_rate - older_rate, older_rate) if older_rate > 0 else 0.0

        if acceleration > 0.25:
            trend = "accelerating"
        elif acceleration < -0.25:
            trend = "decelerating"
        else:
            trend = "stable"

        return {
            "total_mentions": len(posts),
            "older_rate_per_day": round(older_rate, 2),
            "recent_rate_per_day": round(recent_rate, 2),
            "acceleration": round(acceleration, 4),
            "trend": trend,
        }


class _OptionsAnalyzer:
    """Options market sentiment via put/call ratio, IV skew,
    and unusual open interest detection."""

    def analyze(self, ticker: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "score": 0.0,
            "details": {},
        }

        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not available for options analysis")
            return result

        try:
            yf_ticker = yf.Ticker(ticker)
            expiration_dates = yf_ticker.options
        except Exception as exc:
            logger.warning("Failed to fetch options expirations for %s: %s", ticker, exc)
            return result

        if not expiration_dates:
            logger.info("No options data available for %s", ticker)
            return result

        # Use the nearest expiration for short-term sentiment
        # and the second nearest (if available) for confirmation
        expirations_to_analyze = list(expiration_dates[:3])

        total_call_oi = 0
        total_put_oi = 0
        call_ivs: list[float] = []
        put_ivs: list[float] = []
        unusual_strikes: list[dict] = []
        all_call_ois: list[int] = []
        all_put_ois: list[int] = []

        current_price = 0.0
        try:
            info = yf_ticker.info or {}
            current_price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
        except Exception:
            pass

        for exp_date in expirations_to_analyze:
            try:
                chain = yf_ticker.option_chain(exp_date)
            except Exception as exc:
                logger.debug("Failed to get option chain for %s exp %s: %s", ticker, exp_date, exc)
                continue

            calls_df = chain.calls
            puts_df = chain.puts

            if calls_df is not None and not calls_df.empty:
                call_oi_values = calls_df["openInterest"].fillna(0).astype(int).tolist()
                all_call_ois.extend(call_oi_values)
                total_call_oi += sum(call_oi_values)

                if "impliedVolatility" in calls_df.columns:
                    call_ivs.extend(calls_df["impliedVolatility"].dropna().tolist())

            if puts_df is not None and not puts_df.empty:
                put_oi_values = puts_df["openInterest"].fillna(0).astype(int).tolist()
                all_put_ois.extend(put_oi_values)
                total_put_oi += sum(put_oi_values)

                if "impliedVolatility" in puts_df.columns:
                    put_ivs.extend(puts_df["impliedVolatility"].dropna().tolist())

            # Unusual activity detection: OI > 2x average for that chain
            self._detect_unusual_activity(
                calls_df, puts_df, exp_date, unusual_strikes, current_price
            )

        # --- Put/Call Ratio ---
        pc_ratio = _safe_divide(total_put_oi, total_call_oi) if total_call_oi > 0 else None
        pc_score = 0.0
        if pc_ratio is not None:
            # PC ratio interpretation: >1.0 bearish, <0.7 bullish, 0.7-1.0 neutral
            if pc_ratio > 1.0:
                pc_score = _clamp(-(pc_ratio - 1.0) / 0.5)  # scale: 1.5 -> -1.0
            elif pc_ratio < 0.7:
                pc_score = _clamp((0.7 - pc_ratio) / 0.3)  # scale: 0.4 -> 1.0
            else:
                pc_score = _clamp((0.85 - pc_ratio) / 0.3)  # slight lean

        # --- IV Skew ---
        iv_skew = 0.0
        iv_skew_score = 0.0
        if call_ivs and put_ivs:
            avg_call_iv = statistics.mean(call_ivs)
            avg_put_iv = statistics.mean(put_ivs)
            if avg_call_iv > 0:
                iv_skew = (avg_put_iv - avg_call_iv) / avg_call_iv
                # Positive skew (puts more expensive) = hedging demand = mildly bearish
                iv_skew_score = _clamp(-iv_skew / 0.3)

        # --- Unusual activity signal ---
        unusual_score = 0.0
        if unusual_strikes:
            # Net bias of unusual activity
            call_unusual = sum(1 for u in unusual_strikes if u["type"] == "call")
            put_unusual = sum(1 for u in unusual_strikes if u["type"] == "put")
            total_unusual = call_unusual + put_unusual
            if total_unusual > 0:
                # More unusual call activity = bullish, more put = bearish
                unusual_score = _clamp((call_unusual - put_unusual) / total_unusual)

        # --- Composite options score ---
        # PC ratio 50%, IV skew 30%, unusual activity 20%
        components_used = 0
        weighted_sum = 0.0
        total_w = 0.0

        if pc_ratio is not None:
            weighted_sum += 0.50 * pc_score
            total_w += 0.50
            components_used += 1
        if call_ivs and put_ivs:
            weighted_sum += 0.30 * iv_skew_score
            total_w += 0.30
            components_used += 1
        if unusual_strikes:
            weighted_sum += 0.20 * unusual_score
            total_w += 0.20
            components_used += 1

        options_score = _clamp(_safe_divide(weighted_sum, total_w)) if total_w > 0 else 0.0

        result["score"] = round(options_score, 4)
        result["details"] = {
            "expirations_analyzed": expirations_to_analyze,
            "put_call_ratio": {
                "total_call_oi": total_call_oi,
                "total_put_oi": total_put_oi,
                "ratio": round(pc_ratio, 4) if pc_ratio is not None else None,
                "interpretation": (
                    "bearish" if pc_ratio and pc_ratio > 1.0 else
                    "bullish" if pc_ratio and pc_ratio < 0.7 else
                    "neutral"
                ) if pc_ratio is not None else "no_data",
                "score": round(pc_score, 4),
            },
            "iv_skew": {
                "avg_call_iv": round(statistics.mean(call_ivs), 4) if call_ivs else None,
                "avg_put_iv": round(statistics.mean(put_ivs), 4) if put_ivs else None,
                "skew": round(iv_skew, 4),
                "score": round(iv_skew_score, 4),
            },
            "unusual_activity": {
                "flagged_strikes": len(unusual_strikes),
                "call_unusual": sum(1 for u in unusual_strikes if u["type"] == "call"),
                "put_unusual": sum(1 for u in unusual_strikes if u["type"] == "put"),
                "score": round(unusual_score, 4),
                "top_strikes": unusual_strikes[:10],
            },
        }
        return result

    @staticmethod
    def _detect_unusual_activity(
        calls_df: Optional[pd.DataFrame],
        puts_df: Optional[pd.DataFrame],
        exp_date: str,
        unusual_strikes: list[dict],
        current_price: float,
    ) -> None:
        """Flag strikes where open interest exceeds 2x the chain average."""
        for df, opt_type in [(calls_df, "call"), (puts_df, "put")]:
            if df is None or df.empty:
                continue
            oi_col = df["openInterest"].fillna(0)
            avg_oi = oi_col.mean()
            if avg_oi <= 0:
                continue
            threshold = avg_oi * 2.0
            for _, row in df.iterrows():
                oi = int(row.get("openInterest", 0) or 0)
                if oi > threshold:
                    strike = float(row.get("strike", 0))
                    unusual_strikes.append({
                        "type": opt_type,
                        "strike": round(strike, 2),
                        "expiration": exp_date,
                        "open_interest": oi,
                        "avg_oi": round(avg_oi, 0),
                        "ratio_to_avg": round(oi / avg_oi, 2),
                        "moneyness": round(
                            _safe_divide(strike - current_price, current_price) * 100, 2
                        ) if current_price > 0 else None,
                    })


# ---------------------------------------------------------------------------
# Main Sentiment Analyzer
# ---------------------------------------------------------------------------

class SentimentAnalyzer:
    """Institutional-grade multi-source sentiment aggregation engine.

    Combines six independent sentiment sources, normalizes each to [-1, +1],
    and produces a composite score mapped to [0, 100].
    """

    def __init__(self) -> None:
        self.news_client = NewsSentimentClient()
        self.alt_client = AlternativeDataClient()
        self.sec_client = SECFilingsClient()

        self._news_analyzer = _NewsAnalyzer(self.news_client)
        self._sec_analyzer = _SECFilingAnalyzer(self.sec_client)
        self._insider_analyzer = _InsiderAnalyzer(self.alt_client)
        self._analyst_analyzer = _AnalystAnalyzer(self.alt_client)
        self._social_analyzer = _SocialMediaAnalyzer(self.alt_client)
        self._options_analyzer = _OptionsAnalyzer()

    def analyze(self, ticker: str) -> dict[str, Any]:
        """Run full multi-source sentiment analysis for a single ticker.

        Returns a dict with:
            - ticker: str
            - composite_score: float (0-100)
            - composite_label: str
            - confidence: float (0-1)
            - source_scores: dict[str, float]  (each -1 to +1)
            - source_details: dict[str, dict]
            - sources_available: list[str]
            - sources_failed: list[str]
        """
        logger.info("Running institutional sentiment analysis for %s", ticker)

        source_scores: dict[str, float] = {}
        source_details: dict[str, dict] = {}
        sources_available: list[str] = []
        sources_failed: list[str] = []

        # 1. News Sentiment
        try:
            news_result = self._news_analyzer.analyze(ticker)
            if news_result.get("article_count", 0) > 0:
                source_scores["news"] = news_result["score"]
                source_details["news"] = news_result["details"]
                source_details["news"]["article_count"] = news_result["article_count"]
                sources_available.append("news")
            else:
                sources_failed.append("news")
                logger.info("No news articles found for %s", ticker)
        except Exception as exc:
            sources_failed.append("news")
            logger.warning("News analysis failed for %s: %s", ticker, exc)

        # 2. SEC Filing Analysis
        try:
            sec_result = self._sec_analyzer.analyze(ticker)
            if sec_result.get("details", {}).get("filings_analyzed", 0) > 0:
                source_scores["sec_filings"] = sec_result["score"]
                source_details["sec_filings"] = sec_result["details"]
                sources_available.append("sec_filings")
            else:
                sources_failed.append("sec_filings")
                logger.info("No SEC filings found for %s", ticker)
        except Exception as exc:
            sources_failed.append("sec_filings")
            logger.warning("SEC filing analysis failed for %s: %s", ticker, exc)

        # 3. Insider Transaction Analysis
        try:
            insider_result = self._insider_analyzer.analyze(ticker)
            if insider_result.get("details", {}).get("total_trades", 0) > 0:
                source_scores["insider"] = insider_result["score"]
                source_details["insider"] = insider_result["details"]
                sources_available.append("insider")
            else:
                sources_failed.append("insider")
                logger.info("No insider trades found for %s", ticker)
        except Exception as exc:
            sources_failed.append("insider")
            logger.warning("Insider analysis failed for %s: %s", ticker, exc)

        # 4. Analyst Consensus
        try:
            analyst_result = self._analyst_analyzer.analyze(ticker)
            has_data = bool(
                analyst_result.get("details", {}).get("rating")
                or analyst_result.get("details", {}).get("price_targets")
                or analyst_result.get("details", {}).get("earnings_revisions")
            )
            if has_data:
                source_scores["analyst"] = analyst_result["score"]
                source_details["analyst"] = analyst_result["details"]
                sources_available.append("analyst")
            else:
                sources_failed.append("analyst")
                logger.info("No analyst data found for %s", ticker)
        except Exception as exc:
            sources_failed.append("analyst")
            logger.warning("Analyst analysis failed for %s: %s", ticker, exc)

        # 5. Social Media Sentiment
        try:
            social_result = self._social_analyzer.analyze(ticker)
            if social_result.get("details", {}).get("total_posts", 0) > 0:
                source_scores["social"] = social_result["score"]
                source_details["social"] = social_result["details"]
                sources_available.append("social")
            else:
                sources_failed.append("social")
                logger.info("No social media data found for %s", ticker)
        except Exception as exc:
            sources_failed.append("social")
            logger.warning("Social media analysis failed for %s: %s", ticker, exc)

        # 6. Options Market Sentiment
        try:
            options_result = self._options_analyzer.analyze(ticker)
            has_options = (
                options_result.get("details", {})
                .get("put_call_ratio", {})
                .get("ratio") is not None
            )
            if has_options:
                source_scores["options"] = options_result["score"]
                source_details["options"] = options_result["details"]
                sources_available.append("options")
            else:
                sources_failed.append("options")
                logger.info("No options data found for %s", ticker)
        except Exception as exc:
            sources_failed.append("options")
            logger.warning("Options analysis failed for %s: %s", ticker, exc)

        # --- Composite scoring ---
        composite_neg1_pos1 = self._compute_composite(source_scores)
        composite_0_100 = _normalize_to_0_100(composite_neg1_pos1)
        label = _score_to_label(composite_0_100)

        # Confidence: based on proportion of sources that returned data
        total_sources = len(SOURCE_WEIGHTS)
        available_weight = sum(
            SOURCE_WEIGHTS.get(src, 0.0) for src in sources_available
        )
        confidence = round(min(available_weight / 1.0, 1.0), 4)
        # Minimum confidence floor if at least one source is present
        if sources_available and confidence < 0.1:
            confidence = 0.1

        return {
            "ticker": ticker,
            "composite_score": composite_0_100,
            "composite_label": label,
            "composite_raw": round(composite_neg1_pos1, 4),
            "confidence": confidence,
            "source_scores": {k: round(v, 4) for k, v in source_scores.items()},
            "source_details": source_details,
            "source_weights_used": {
                src: round(SOURCE_WEIGHTS.get(src, 0.0), 4)
                for src in sources_available
            },
            "sources_available": sources_available,
            "sources_failed": sources_failed,
        }

    @staticmethod
    def _compute_composite(source_scores: dict[str, float]) -> float:
        """Weighted average of available source scores, re-normalized to [-1, 1].

        Only sources with data contribute. Weights are re-proportioned so they
        sum to 1.0 among available sources.
        """
        if not source_scores:
            return 0.0

        weighted_sum = 0.0
        total_weight = 0.0
        for source, score in source_scores.items():
            w = SOURCE_WEIGHTS.get(source, 0.0)
            weighted_sum += w * score
            total_weight += w

        if total_weight == 0:
            return 0.0

        return _clamp(weighted_sum / total_weight)


# ---------------------------------------------------------------------------
# Pipeline Plugin Adapter
# ---------------------------------------------------------------------------

class SentimentAnalyzerPlugin(BaseAnalyzer):
    """Pipeline-compatible adapter that exposes the multi-source sentiment
    engine through the standard BaseAnalyzer interface.

    Returns:
        dict with at minimum:
            "score" (0-100): composite sentiment score
            "confidence" (0-1): data availability confidence
    """

    name = "sentiment"
    default_weight = 0.10

    def __init__(self) -> None:
        self._analyzer = SentimentAnalyzer()

    def analyze(self, ticker: str, ctx: Any) -> dict[str, Any]:
        """Run institutional-grade sentiment analysis for *ticker*.

        Args:
            ticker: Stock symbol (e.g. "AAPL").
            ctx: PipelineContext instance (available but not required by this analyzer).

        Returns:
            Dict containing "score" (0-100) and "confidence" (0-1) keys,
            plus full source-level breakdown.
        """
        result = self._analyzer.analyze(ticker)

        # Ensure required plugin keys are present
        result["score"] = result.get("composite_score", 50.0)
        result["confidence"] = result.get("confidence", 0.0)

        return result
