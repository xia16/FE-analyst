"""LLM-based sentiment analysis using Claude.

Replaces FinBERT with a single LLM call that analyzes all gathered
data sources (news, Reddit, analyst recommendations, insider trades)
holistically and returns a structured sentiment assessment.
"""

import json

from src.config import Keys
from src.utils.logger import setup_logger

logger = setup_logger("llm_sentiment")

SENTIMENT_SYSTEM_PROMPT = """\
You are a senior equity research analyst performing sentiment analysis.
You will receive raw data about a stock: news headlines, Reddit posts,
analyst recommendations, and insider transactions.

Analyze ALL sources holistically and return a JSON object with EXACTLY
this structure (no markdown, no commentary, just valid JSON):

{
  "overall_score": <float from -1.0 to 1.0>,
  "overall_label": "<BULLISH|BEARISH|NEUTRAL>",
  "confidence": <float from 0.0 to 1.0>,
  "news_sentiment": {
    "score": <float from -1.0 to 1.0>,
    "label": "<BULLISH|BEARISH|NEUTRAL>",
    "key_themes": ["<theme 1>", "<theme 2>", "<theme 3>"],
    "notable_headlines": ["<most impactful headline 1>", "<headline 2>"]
  },
  "social_sentiment": {
    "score": <float from -1.0 to 1.0>,
    "label": "<BULLISH|BEARISH|NEUTRAL>",
    "summary": "<1-2 sentence summary of retail investor mood>"
  },
  "analyst_sentiment": {
    "score": <float from -1.0 to 1.0>,
    "label": "<BULLISH|BEARISH|NEUTRAL>",
    "consensus": "<Strong Buy|Buy|Hold|Sell|Strong Sell>",
    "recent_changes": "<summary of recent rating changes>"
  },
  "insider_sentiment": {
    "score": <float from -1.0 to 1.0>,
    "label": "<BULLISH|BEARISH|NEUTRAL|NO DATA>",
    "summary": "<1-2 sentence summary of insider activity>"
  },
  "reasoning": "<2-4 sentence synthesis explaining the overall sentiment rating, citing specific data points>"
}

Scoring guide:
- Score > 0.3: BULLISH (clear positive catalysts, upgrades, strong buying)
- Score 0.1 to 0.3: Lean BULLISH
- Score -0.1 to 0.1: NEUTRAL (mixed signals, no clear direction)
- Score -0.3 to -0.1: Lean BEARISH
- Score < -0.3: BEARISH (clear negative catalysts, downgrades, selling)

Be objective and evidence-based. Do not hallucinate data points.
If a data source is empty or unavailable, score it 0.0 and label NO DATA.\
"""


class LLMSentimentClient:
    """Analyze sentiment using Claude as the reasoning engine."""

    def __init__(self, model: str = "claude-sonnet-4-5-20250929"):
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not Keys.ANTHROPIC:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not set. Add it to your .env file."
                )
            import anthropic
            self._client = anthropic.Anthropic(api_key=Keys.ANTHROPIC)
        return self._client

    def analyze(
        self,
        ticker: str,
        news: list[dict],
        reddit_posts: list[dict],
        analyst_recs: list[dict],
        insider_trades: list[dict],
    ) -> dict:
        """Send all raw data to Claude for holistic sentiment analysis.

        Args:
            ticker: Stock symbol
            news: List of news article dicts (headline, summary, source, datetime)
            reddit_posts: List of Reddit post dicts (title, score, upvote_ratio)
            analyst_recs: List of analyst recommendation dicts
            insider_trades: List of insider transaction dicts

        Returns:
            Structured sentiment assessment dict
        """
        user_prompt = self._build_prompt(ticker, news, reddit_posts, analyst_recs, insider_trades)

        if not user_prompt.strip():
            logger.warning("No sentiment data available for %s", ticker)
            return self._empty_result()

        logger.info("Running LLM sentiment analysis for %s", ticker)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SENTIMENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            raw_text = response.content[0].text.strip()
            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()

            result = json.loads(raw_text)
            result["ticker"] = ticker
            result["model"] = self.model
            return result

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response for %s: %s", ticker, e)
            logger.debug("Raw response: %s", raw_text)
            return self._empty_result()
        except Exception as e:
            logger.error("LLM sentiment failed for %s: %s", ticker, e)
            return self._empty_result()

    def _build_prompt(
        self,
        ticker: str,
        news: list[dict],
        reddit_posts: list[dict],
        analyst_recs: list[dict],
        insider_trades: list[dict],
    ) -> str:
        """Assemble the user prompt from all data sources."""
        sections = [f"# Sentiment Data for {ticker}\n"]

        # News
        if news:
            sections.append("## Recent News Headlines")
            for i, article in enumerate(news[:30], 1):  # cap at 30 articles
                headline = article.get("headline", "")
                source = article.get("source", "")
                summary = article.get("summary", "")
                dt = article.get("datetime", "")
                line = f"{i}. [{source}] {headline}"
                if summary:
                    line += f"\n   Summary: {summary[:200]}"
                sections.append(line)
            sections.append("")
        else:
            sections.append("## Recent News Headlines\nNo news data available.\n")

        # Reddit
        if reddit_posts:
            sections.append("## Reddit Posts")
            for i, post in enumerate(reddit_posts[:20], 1):
                title = post.get("title", "")
                score = post.get("score", 0)
                comments = post.get("num_comments", 0)
                ratio = post.get("upvote_ratio", 0)
                sections.append(
                    f"{i}. \"{title}\" (score: {score}, comments: {comments}, "
                    f"upvote_ratio: {ratio:.2f})"
                )
            sections.append("")
        else:
            sections.append("## Reddit Posts\nNo Reddit data available.\n")

        # Analyst recommendations
        if analyst_recs:
            sections.append("## Analyst Recommendations (Recent)")
            for rec in analyst_recs[:10]:
                firm = rec.get("Firm", rec.get("firm", "Unknown"))
                grade = rec.get("To Grade", rec.get("toGrade", ""))
                from_grade = rec.get("From Grade", rec.get("fromGrade", ""))
                action = rec.get("Action", rec.get("action", ""))
                date = rec.get("Date", rec.get("date", ""))
                line = f"- {firm}: {action} → {grade}"
                if from_grade:
                    line += f" (from {from_grade})"
                if date:
                    line += f" [{date}]"
                sections.append(line)
            sections.append("")
        else:
            sections.append("## Analyst Recommendations\nNo analyst data available.\n")

        # Insider trades
        if insider_trades:
            sections.append("## Insider Transactions (Recent)")
            for trade in insider_trades[:15]:
                name = trade.get("name", "Unknown")
                change = trade.get("change", 0)
                tx_type = trade.get("transactionType", "")
                shares = trade.get("share", 0)
                date = trade.get("transactionDate", "")
                sections.append(
                    f"- {name}: {tx_type} {shares:,} shares "
                    f"(change: {change:,}) [{date}]"
                )
            sections.append("")
        else:
            sections.append("## Insider Transactions\nNo insider data available.\n")

        return "\n".join(sections)

    @staticmethod
    def _empty_result() -> dict:
        """Return a neutral result when analysis fails."""
        empty_source = {"score": 0.0, "label": "NO DATA"}
        return {
            "overall_score": 0.0,
            "overall_label": "NO DATA",
            "confidence": 0.0,
            "news_sentiment": {**empty_source, "key_themes": [], "notable_headlines": []},
            "social_sentiment": {**empty_source, "summary": "No data available"},
            "analyst_sentiment": {
                **empty_source,
                "consensus": "N/A",
                "recent_changes": "No data available",
            },
            "insider_sentiment": {**empty_source, "summary": "No data available"},
            "reasoning": "Insufficient data for sentiment analysis.",
        }
