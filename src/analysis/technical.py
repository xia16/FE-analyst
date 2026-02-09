"""Technical analysis engine using the 'ta' library."""

import pandas as pd
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator

from src.utils.logger import setup_logger

logger = setup_logger("technical")


class TechnicalAnalyzer:
    """Compute technical indicators and generate signals."""

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all standard technical indicators to an OHLCV DataFrame."""
        result = df.copy()
        close = result["Close"]
        high = result["High"]
        low = result["Low"]
        volume = result["Volume"]

        # Trend - SMAs
        result["SMA_20"] = SMAIndicator(close, window=20).sma_indicator()
        result["SMA_50"] = SMAIndicator(close, window=50).sma_indicator()
        result["SMA_200"] = SMAIndicator(close, window=200).sma_indicator()

        # Trend - EMAs
        result["EMA_12"] = EMAIndicator(close, window=12).ema_indicator()
        result["EMA_26"] = EMAIndicator(close, window=26).ema_indicator()

        # Momentum - RSI
        result["RSI_14"] = RSIIndicator(close, window=14).rsi()

        # Momentum - MACD
        macd = MACD(close, window_slow=26, window_fast=12, window_sign=9)
        result["MACD"] = macd.macd()
        result["MACD_signal"] = macd.macd_signal()
        result["MACD_hist"] = macd.macd_diff()

        # Volatility - Bollinger Bands
        bb = BollingerBands(close, window=20, window_dev=2)
        result["BB_upper"] = bb.bollinger_hband()
        result["BB_lower"] = bb.bollinger_lband()
        result["BB_mid"] = bb.bollinger_mavg()

        # Volatility - ATR
        result["ATR_14"] = AverageTrueRange(high, low, close, window=14).average_true_range()

        # Volume - OBV
        result["OBV"] = OnBalanceVolumeIndicator(close, volume).on_balance_volume()

        return result

    def get_signals(self, df: pd.DataFrame) -> dict:
        """Generate buy/sell/hold signals from indicators."""
        df = self.compute_indicators(df)
        latest = df.iloc[-1]
        signals = {}

        # RSI signal
        rsi = latest.get("RSI_14")
        if rsi is not None and pd.notna(rsi):
            if rsi < 30:
                signals["rsi"] = {"signal": "BUY", "value": round(rsi, 2), "reason": "Oversold"}
            elif rsi > 70:
                signals["rsi"] = {"signal": "SELL", "value": round(rsi, 2), "reason": "Overbought"}
            else:
                signals["rsi"] = {"signal": "HOLD", "value": round(rsi, 2), "reason": "Neutral"}

        # Moving average crossover
        sma_20 = latest.get("SMA_20")
        sma_50 = latest.get("SMA_50")
        price = latest.get("Close")
        if sma_20 is not None and sma_50 is not None and pd.notna(sma_20) and pd.notna(sma_50):
            if sma_20 > sma_50 and price > sma_20:
                signals["ma_crossover"] = {"signal": "BUY", "reason": "Price above rising MAs"}
            elif sma_20 < sma_50 and price < sma_20:
                signals["ma_crossover"] = {"signal": "SELL", "reason": "Price below falling MAs"}
            else:
                signals["ma_crossover"] = {"signal": "HOLD", "reason": "Mixed MA signals"}

        # MACD
        macd_val = latest.get("MACD")
        macd_signal = latest.get("MACD_signal")
        if macd_val is not None and macd_signal is not None and pd.notna(macd_val) and pd.notna(macd_signal):
            if macd_val > macd_signal:
                signals["macd"] = {"signal": "BUY", "reason": "MACD above signal"}
            else:
                signals["macd"] = {"signal": "SELL", "reason": "MACD below signal"}

        # Bollinger Bands
        bb_upper = latest.get("BB_upper")
        bb_lower = latest.get("BB_lower")
        if bb_upper is not None and bb_lower is not None and price is not None and pd.notna(bb_upper):
            if price < bb_lower:
                signals["bbands"] = {"signal": "BUY", "reason": "Below lower band"}
            elif price > bb_upper:
                signals["bbands"] = {"signal": "SELL", "reason": "Above upper band"}
            else:
                signals["bbands"] = {"signal": "HOLD", "reason": "Within bands"}

        return signals

    def get_support_resistance(self, df: pd.DataFrame, window: int = 20) -> dict:
        """Identify support and resistance levels."""
        highs = df["High"].rolling(window=window).max()
        lows = df["Low"].rolling(window=window).min()
        return {
            "resistance": float(highs.iloc[-1]),
            "support": float(lows.iloc[-1]),
            "current": float(df["Close"].iloc[-1]),
        }


# --- Plugin adapter for pipeline ---
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer


class TechnicalAnalyzerPlugin(_BaseAnalyzer):
    name = "technical"
    default_weight = 0.20

    def __init__(self):
        self._analyzer = TechnicalAnalyzer()

    def analyze(self, ticker, ctx):
        df = ctx.price_data.get(ticker)
        if df is None or df.empty:
            return {"error": "No price data", "score": 50}
        signals = self._analyzer.get_signals(df)
        support_res = self._analyzer.get_support_resistance(df)
        buy_count = sum(1 for s in signals.values() if s.get("signal") == "BUY")
        total = max(len(signals), 1)
        score = (buy_count / total) * 100
        return {"signals": signals, "support_resistance": support_res, "score": round(score, 1)}
