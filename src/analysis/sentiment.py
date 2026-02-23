"""Sentiment data collector and aggregator.

Gathers raw data from news, Reddit, analyst recommendations, insider
trades, ownership data, earnings calendar, and analyst price targets
into a structured format. Sentiment interpretation is performed
by the analyst (Claude) when reading the output — no NLP model or API
call is needed.

The data collector scores a simple heuristic baseline (analyst consensus
+ insider net buy/sell + ownership signals) for the pipeline composite,
but the real analysis happens when Claude reads the raw data during
report generation.
"""

import yfinance as yf
import pandas as pd

from src.data_sources.news_sentiment import NewsSentimentClient
from src.data_sources.alternative_data import AlternativeDataClient
from src.utils.logger import setup_logger

logger = setup_logger("sentiment_analysis")


class SentimentAnalyzer:
    """Gather multi-source sentiment data for analyst interpretation."""

    def __init__(self):
        self.news_client = NewsSentimentClient()
        self.alt_client = AlternativeDataClient()

    def analyze(self, ticker: str) -> dict:
        """Gather all sentiment data sources into a structured result.

        Returns a dict with raw data from each source, plus a simple
        heuristic score for the pipeline composite. The raw data is
        designed to be read and interpreted by Claude during analysis.
        """
        logger.info("Gathering sentiment data for %s", ticker)

        # 1. Fetch news headlines
        news = []
        try:
            news = self.news_client.get_company_news(ticker)
        except Exception as e:
            logger.warning("  News fetch failed: %s", e)
        logger.info("  News articles: %d", len(news))

        # 2. Fetch Reddit posts from multiple subreddits
        reddit_posts = []
        subreddits = ["wallstreetbets", "stocks", "investing"]
        for sub in subreddits:
            try:
                posts = self.alt_client.get_reddit_sentiment(
                    ticker, subreddit=sub, limit=20
                )
                for p in posts:
                    p["subreddit"] = sub
                reddit_posts.extend(posts)
            except Exception as e:
                logger.warning("  Reddit r/%s fetch failed: %s", sub, e)
        logger.info("  Reddit posts: %d", len(reddit_posts))

        # 3. Fetch analyst recommendations
        analyst_recs = []
        try:
            recs_df = self.alt_client.get_analyst_recommendations(ticker)
            if recs_df is not None and not recs_df.empty:
                analyst_recs = recs_df.iloc[:10].to_dict("records")
        except Exception as e:
            logger.warning("  Analyst recs fetch failed: %s", e)
        logger.info("  Analyst recommendations: %d", len(analyst_recs))

        # 4. Fetch insider trades
        insider_trades = []
        try:
            insider_trades = self.alt_client.get_insider_trades(ticker)
        except Exception as e:
            logger.warning("  Insider trades fetch failed: %s", e)
        logger.info("  Insider trades: %d", len(insider_trades))

        # 5. Fetch institutional ownership
        institutional = []
        try:
            inst_df = self.alt_client.get_institutional_ownership(ticker)
            if inst_df is not None and not inst_df.empty:
                institutional = inst_df.iloc[:10].to_dict("records")
        except Exception as e:
            logger.warning("  Institutional ownership fetch failed: %s", e)
        logger.info("  Institutional holders: %d", len(institutional))

        # 6. Insider ownership % and major holders breakdown
        ownership = self._get_ownership_data(ticker)

        # 7. Earnings calendar
        earnings_calendar = self._get_earnings_calendar(ticker)

        # 8. Analyst price targets
        analyst_targets = self._get_analyst_targets(ticker)

        # 9. Short interest data
        short_interest = self._get_short_interest(ticker)

        # Build heuristic score for pipeline composite
        heuristic_score = self._compute_heuristic(
            analyst_recs, insider_trades, ownership, short_interest
        )

        return {
            "ticker": ticker,
            "overall_score": heuristic_score,
            "overall_label": self._label_from_score(heuristic_score),
            # Structured data
            "ownership": ownership,
            "earnings_calendar": earnings_calendar,
            "analyst_targets": analyst_targets,
            "short_interest": short_interest,
            # Raw data for Claude to interpret
            "raw_data": {
                "news": news[:30],
                "reddit_posts": reddit_posts[:30],
                "analyst_recommendations": analyst_recs,
                "insider_trades": insider_trades[:20],
                "institutional_holders": institutional,
            },
            "source_counts": {
                "news_articles": len(news),
                "reddit_posts": len(reddit_posts),
                "analyst_recommendations": len(analyst_recs),
                "insider_trades": len(insider_trades),
                "institutional_holders": len(institutional),
            },
        }

    # ------------------------------------------------------------------
    # Ownership data
    # ------------------------------------------------------------------

    @staticmethod
    def _get_ownership_data(ticker: str) -> dict:
        """Get insider and institutional ownership percentages."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            result = {
                "insider_pct": info.get("heldPercentInsiders"),
                "institutional_pct": info.get("heldPercentInstitutions"),
                "float_shares": info.get("floatShares"),
                "shares_outstanding": info.get("sharesOutstanding"),
            }
            # Major holders table
            try:
                mh = stock.major_holders
                if mh is not None and not mh.empty:
                    holders = {}
                    for _, row in mh.iterrows():
                        val = row.iloc[0]
                        label = str(row.iloc[1]) if len(row) > 1 else ""
                        if "insider" in label.lower():
                            holders["insider_label"] = f"{val} {label}"
                        elif "institution" in label.lower():
                            holders["institutional_label"] = f"{val} {label}"
                    result["major_holders"] = holders
            except Exception:
                pass
            return result
        except Exception as e:
            logger.warning("Ownership data failed for %s: %s", ticker, e)
            return {}

    # ------------------------------------------------------------------
    # Earnings calendar
    # ------------------------------------------------------------------

    @staticmethod
    def _get_earnings_calendar(ticker: str) -> dict:
        """Get next earnings date and recent earnings history."""
        try:
            stock = yf.Ticker(ticker)
            result = {}

            # Next earnings date from calendar
            try:
                cal = stock.calendar
                if cal is not None:
                    if isinstance(cal, dict):
                        dates = cal.get("Earnings Date", [])
                        if dates:
                            result["next_earnings_date"] = str(dates[0])
                            if len(dates) > 1:
                                result["earnings_date_range_end"] = str(dates[1])
                    elif isinstance(cal, pd.DataFrame) and not cal.empty:
                        if "Earnings Date" in cal.index:
                            result["next_earnings_date"] = str(cal.loc["Earnings Date"].iloc[0])
            except Exception:
                pass

            # Recent earnings surprises
            try:
                ed = stock.earnings_dates
                if ed is not None and not ed.empty:
                    recent = ed.dropna(subset=["Reported EPS"]).head(4)
                    surprises = []
                    for idx, row in recent.iterrows():
                        surprises.append({
                            "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
                            "eps_estimate": row.get("EPS Estimate"),
                            "eps_actual": row.get("Reported EPS"),
                            "surprise_pct": row.get("Surprise(%)"),
                        })
                    result["recent_surprises"] = surprises
                    # Beat rate
                    beats = sum(1 for s in surprises if s.get("surprise_pct") and s["surprise_pct"] > 0)
                    result["beat_rate"] = beats / len(surprises) if surprises else None
            except Exception:
                pass

            return result
        except Exception as e:
            logger.warning("Earnings calendar failed for %s: %s", ticker, e)
            return {}

    # ------------------------------------------------------------------
    # Analyst price targets
    # ------------------------------------------------------------------

    @staticmethod
    def _get_analyst_targets(ticker: str) -> dict:
        """Get analyst consensus price targets."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            result = {
                "target_mean": info.get("targetMeanPrice"),
                "target_high": info.get("targetHighPrice"),
                "target_low": info.get("targetLowPrice"),
                "target_median": info.get("targetMedianPrice"),
                "analyst_count": info.get("numberOfAnalystOpinions"),
                "recommendation": info.get("recommendationKey"),
                "current_price": info.get("currentPrice", info.get("regularMarketPrice")),
            }
            # Compute upside/downside
            price = result["current_price"]
            if price and result["target_mean"]:
                result["upside_pct"] = round(
                    (result["target_mean"] / price - 1) * 100, 2
                )
            if price and result["target_high"]:
                result["upside_to_high_pct"] = round(
                    (result["target_high"] / price - 1) * 100, 2
                )
            if price and result["target_low"]:
                result["downside_to_low_pct"] = round(
                    (result["target_low"] / price - 1) * 100, 2
                )
            return result
        except Exception as e:
            logger.warning("Analyst targets failed for %s: %s", ticker, e)
            return {}

    # ------------------------------------------------------------------
    # Short interest
    # ------------------------------------------------------------------

    @staticmethod
    def _get_short_interest(ticker: str) -> dict:
        """Get short interest metrics from yfinance."""
        try:
            info = yf.Ticker(ticker).info
            shares_short = info.get("sharesShort")
            short_ratio = info.get("shortRatio")
            short_pct = info.get("shortPercentOfFloat")
            prior_month = info.get("sharesShortPriorMonth")

            result = {
                "shares_short": shares_short,
                "short_ratio_days": short_ratio,
                "short_pct_of_float": short_pct,
                "shares_short_prior_month": prior_month,
            }

            # Change vs prior month
            if shares_short and prior_month and prior_month > 0:
                result["short_change_pct"] = round(
                    (shares_short / prior_month - 1) * 100, 2
                )

            # Signal
            if short_pct is not None:
                if short_pct > 0.20:
                    result["signal"] = "HIGH SHORT INTEREST"
                elif short_pct > 0.10:
                    result["signal"] = "ELEVATED"
                else:
                    result["signal"] = "NORMAL"
            else:
                result["signal"] = "NO DATA"

            return result
        except Exception as e:
            logger.warning("Short interest failed for %s: %s", ticker, e)
            return {"signal": "NO DATA"}

    # ------------------------------------------------------------------
    # Heuristic scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_heuristic(
        analyst_recs: list[dict],
        insider_trades: list[dict],
        ownership: dict,
        short_interest: dict,
    ) -> float:
        """Weighted heuristic score from analyst consensus + insider + ownership signals.

        Returns float from -1.0 to 1.0.
        Uses explicit weights instead of equal-weight averaging:
        - Analyst consensus: 40% (most informative for price direction)
        - Insider activity: 25% (strongest signal when present)
        - Ownership structure: 15% (mild directional signal)
        - Short interest: 20% (contrarian/risk indicator)
        """
        components: list[tuple[float, float]] = []  # (score, weight)

        # Analyst consensus heuristic (40% weight)
        analyst_score = 0.0
        if analyst_recs:
            grade_map = {
                "Strong Buy": 1.0, "Buy": 0.5, "Overweight": 0.4,
                "Outperform": 0.4, "Market Outperform": 0.3,
                "Hold": 0.0, "Neutral": 0.0, "Equal-Weight": 0.0,
                "Market Perform": 0.0, "Sector Perform": 0.0,
                "Underweight": -0.3, "Underperform": -0.4,
                "Sell": -0.5, "Strong Sell": -1.0, "Reduce": -0.4,
            }
            # Weight recent recommendations higher (exponential decay)
            grades = []
            for i, rec in enumerate(analyst_recs):
                grade = rec.get("To Grade", rec.get("toGrade", ""))
                if grade in grade_map:
                    recency_weight = 0.8 ** i  # most recent = 1.0, older = decaying
                    grades.append((grade_map[grade], recency_weight))
            if grades:
                analyst_score = sum(g * w for g, w in grades) / sum(w for _, w in grades)
        components.append((analyst_score, 0.40))

        # Insider trade heuristic (25% weight) — now considers trade SIZE
        insider_score = 0.0
        if insider_trades:
            # Weight by absolute change size (large trades matter more)
            changes = [t.get("change", 0) for t in insider_trades[:20]]
            abs_total = sum(abs(c) for c in changes) or 1
            weighted_net = sum(c for c in changes) / abs_total  # -1 to +1

            if weighted_net > 0.3:
                insider_score = 0.5
            elif weighted_net > 0.1:
                insider_score = 0.3
            elif weighted_net < -0.3:
                insider_score = -0.4
            elif weighted_net < -0.1:
                insider_score = -0.2
        components.append((insider_score, 0.25))

        # Ownership structure (15% weight)
        ownership_score = 0.0
        insider_pct = ownership.get("insider_pct")
        if insider_pct is not None:
            if insider_pct > 0.10:
                ownership_score = 0.3
            elif insider_pct > 0.05:
                ownership_score = 0.2
            elif insider_pct > 0.02:
                ownership_score = 0.1
        components.append((ownership_score, 0.15))

        # Short interest (20% weight) — dual signal: bearish but also squeeze potential
        short_score = 0.0
        short_pct = short_interest.get("short_pct_of_float")
        short_change = short_interest.get("short_change_pct")
        if short_pct is not None:
            if short_pct > 0.20:
                short_score = -0.4
            elif short_pct > 0.10:
                short_score = -0.2
            elif short_pct > 0.05:
                short_score = -0.1
            # If short interest is declining, that's bullish
            if short_change is not None and short_change < -10:
                short_score += 0.15  # shorts covering
        components.append((short_score, 0.20))

        # Weighted average
        total_weight = sum(w for _, w in components)
        if total_weight > 0:
            return round(sum(s * w for s, w in components) / total_weight, 3)
        return 0.0

    @staticmethod
    def _label_from_score(score: float) -> str:
        if score > 0.2:
            return "BULLISH"
        elif score < -0.2:
            return "BEARISH"
        elif score == 0.0:
            return "NO DATA"
        return "NEUTRAL"


# --- Plugin adapter for pipeline ---
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer


class SentimentAnalyzerPlugin(_BaseAnalyzer):
    name = "sentiment"
    default_weight = 0.10

    def __init__(self):
        self._analyzer = SentimentAnalyzer()

    def analyze(self, ticker, ctx):
        result = self._analyzer.analyze(ticker)
        # Convert -1..1 score to 0-100 scale for composite scoring
        overall = result.get("overall_score", 0)
        score = max(0, min(100, 50 + overall * 100))
        result["score"] = round(score, 1)
        return result
