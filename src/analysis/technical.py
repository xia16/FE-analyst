"""Technical analysis engine using the 'ta' library.

Enhanced with multi-timeframe confirmation, volume analysis, OBV divergence,
trend-filtered MA signals, and signal confidence scoring.
"""

import pandas as pd
import numpy as np
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

        # Volume - 20-day average volume
        result["VOL_SMA_20"] = volume.rolling(window=20).mean()

        return result

    def get_signals(self, df: pd.DataFrame) -> dict:
        """Generate buy/sell/hold signals from indicators with confirmations."""
        df = self.compute_indicators(df)
        latest = df.iloc[-1]
        signals = {}

        # RSI signal with multi-period confirmation
        rsi = latest.get("RSI_14")
        if rsi is not None and pd.notna(rsi):
            rsi_signal = {"value": round(rsi, 2)}
            if rsi < 30:
                rsi_signal["signal"] = "BUY"
                rsi_signal["reason"] = "Oversold"
                # Confirmation: check if RSI was oversold for multiple days (more reliable)
                rsi_series = df["RSI_14"].dropna().tail(5)
                days_oversold = sum(1 for v in rsi_series if v < 35)
                rsi_signal["confirmation"] = f"Oversold {days_oversold}/5 days"
                rsi_signal["confidence"] = "HIGH" if days_oversold >= 3 else "LOW"
            elif rsi > 70:
                rsi_signal["signal"] = "SELL"
                rsi_signal["reason"] = "Overbought"
                rsi_series = df["RSI_14"].dropna().tail(5)
                days_overbought = sum(1 for v in rsi_series if v > 65)
                rsi_signal["confirmation"] = f"Overbought {days_overbought}/5 days"
                rsi_signal["confidence"] = "HIGH" if days_overbought >= 3 else "LOW"
            else:
                rsi_signal["signal"] = "HOLD"
                rsi_signal["reason"] = "Neutral"
                rsi_signal["confidence"] = "MEDIUM"
            signals["rsi"] = rsi_signal

        # Moving average crossover with TREND FILTER
        sma_20 = latest.get("SMA_20")
        sma_50 = latest.get("SMA_50")
        sma_200 = latest.get("SMA_200")
        price = latest.get("Close")

        if sma_20 is not None and sma_50 is not None and pd.notna(sma_20) and pd.notna(sma_50):
            ma_signal = {}
            # Check if SMA_50 is rising (trend filter)
            sma50_series = df["SMA_50"].dropna().tail(10)
            sma50_rising = len(sma50_series) >= 2 and float(sma50_series.iloc[-1]) > float(sma50_series.iloc[-5]) if len(sma50_series) >= 5 else None

            if sma_20 > sma_50 and price > sma_20:
                ma_signal["signal"] = "BUY"
                if sma50_rising:
                    ma_signal["reason"] = "Price above rising MAs (trend confirmed)"
                    ma_signal["confidence"] = "HIGH"
                else:
                    ma_signal["reason"] = "Price above MAs but SMA50 still declining"
                    ma_signal["confidence"] = "LOW"
            elif sma_20 < sma_50 and price < sma_20:
                ma_signal["signal"] = "SELL"
                ma_signal["reason"] = "Price below falling MAs"
                ma_signal["confidence"] = "HIGH" if sma50_rising is False else "MEDIUM"
            else:
                ma_signal["signal"] = "HOLD"
                ma_signal["reason"] = "Mixed MA signals"
                ma_signal["confidence"] = "MEDIUM"

            # SMA 200 trend context
            if sma_200 is not None and pd.notna(sma_200):
                ma_signal["above_sma200"] = bool(price > sma_200)
                ma_signal["sma200_distance_pct"] = round(((price - sma_200) / sma_200) * 100, 1)

            signals["ma_crossover"] = ma_signal

        # MACD
        macd_val = latest.get("MACD")
        macd_signal_val = latest.get("MACD_signal")
        macd_hist = latest.get("MACD_hist")
        if macd_val is not None and macd_signal_val is not None and pd.notna(macd_val) and pd.notna(macd_signal_val):
            macd_sig = {}
            if macd_val > macd_signal_val:
                macd_sig["signal"] = "BUY"
                macd_sig["reason"] = "MACD above signal"
            else:
                macd_sig["signal"] = "SELL"
                macd_sig["reason"] = "MACD below signal"
            # Histogram momentum
            if macd_hist is not None and pd.notna(macd_hist):
                hist_series = df["MACD_hist"].dropna().tail(3)
                if len(hist_series) >= 3:
                    hist_expanding = all(
                        abs(float(hist_series.iloc[i])) > abs(float(hist_series.iloc[i - 1]))
                        for i in range(1, len(hist_series))
                    )
                    macd_sig["histogram_momentum"] = "Expanding" if hist_expanding else "Contracting"
                    macd_sig["confidence"] = "HIGH" if hist_expanding else "LOW"
                else:
                    macd_sig["confidence"] = "MEDIUM"
            signals["macd"] = macd_sig

        # Bollinger Bands with volatility context
        bb_upper = latest.get("BB_upper")
        bb_lower = latest.get("BB_lower")
        atr = latest.get("ATR_14")
        if bb_upper is not None and bb_lower is not None and price is not None and pd.notna(bb_upper):
            bb_sig = {}
            bb_width = (bb_upper - bb_lower) / latest.get("BB_mid", bb_upper) if latest.get("BB_mid") else 0
            bb_sig["bandwidth"] = round(bb_width, 4)

            if price < bb_lower:
                bb_sig["signal"] = "BUY"
                bb_sig["reason"] = "Below lower band"
                # High bandwidth = high vol = less reliable reversion
                bb_sig["confidence"] = "LOW" if bb_width > 0.15 else "HIGH"
            elif price > bb_upper:
                bb_sig["signal"] = "SELL"
                bb_sig["reason"] = "Above upper band"
                bb_sig["confidence"] = "LOW" if bb_width > 0.15 else "HIGH"
            else:
                bb_sig["signal"] = "HOLD"
                bb_sig["reason"] = "Within bands"
                bb_sig["confidence"] = "MEDIUM"
            signals["bbands"] = bb_sig

        # --- NEW: Volume confirmation ---
        vol_signal = self._volume_analysis(df, latest)
        if vol_signal:
            signals["volume"] = vol_signal

        # --- NEW: OBV divergence ---
        obv_signal = self._obv_divergence(df)
        if obv_signal:
            signals["obv_divergence"] = obv_signal

        return signals

    def _volume_analysis(self, df: pd.DataFrame, latest: pd.Series) -> dict | None:
        """Analyze volume patterns for confirmation."""
        try:
            volume = latest.get("Volume")
            vol_avg = latest.get("VOL_SMA_20")

            if volume is None or vol_avg is None or pd.isna(volume) or pd.isna(vol_avg) or vol_avg == 0:
                return None

            vol_ratio = volume / vol_avg
            result = {
                "value": round(vol_ratio, 2),
                "volume": int(volume),
                "avg_volume_20d": int(vol_avg),
            }

            # Volume spike (>1.5x average) confirms price moves
            if vol_ratio > 2.0:
                result["signal"] = "HIGH VOLUME"
                result["reason"] = f"Volume {vol_ratio:.1f}x average — strong conviction"
                result["confidence"] = "HIGH"
            elif vol_ratio > 1.5:
                result["signal"] = "ELEVATED"
                result["reason"] = f"Volume {vol_ratio:.1f}x average — moderate conviction"
                result["confidence"] = "MEDIUM"
            elif vol_ratio < 0.5:
                result["signal"] = "LOW VOLUME"
                result["reason"] = f"Volume {vol_ratio:.1f}x average — weak conviction"
                result["confidence"] = "LOW"
            else:
                result["signal"] = "NORMAL"
                result["reason"] = "Normal volume"
                result["confidence"] = "MEDIUM"

            return result
        except Exception:
            return None

    def _obv_divergence(self, df: pd.DataFrame) -> dict | None:
        """Detect OBV (On-Balance Volume) divergence with price.

        Bullish divergence: price making lower lows but OBV making higher lows.
        Bearish divergence: price making higher highs but OBV making lower highs.
        """
        try:
            if "OBV" not in df.columns or len(df) < 30:
                return None

            # Look at 20-day windows
            recent = df.tail(20).dropna(subset=["Close", "OBV"])
            if len(recent) < 15:
                return None

            close = recent["Close"]
            obv = recent["OBV"]

            # Split into two halves and compare
            mid = len(close) // 2
            price_first = close.iloc[:mid].min()
            price_second = close.iloc[mid:].min()
            obv_first = obv.iloc[:mid].min()
            obv_second = obv.iloc[mid:].min()

            price_high_first = close.iloc[:mid].max()
            price_high_second = close.iloc[mid:].max()
            obv_high_first = obv.iloc[:mid].max()
            obv_high_second = obv.iloc[mid:].max()

            # Bullish divergence: lower price low + higher OBV low
            if price_second < price_first * 0.98 and obv_second > obv_first * 1.02:
                return {
                    "signal": "BUY",
                    "reason": "Bullish OBV divergence — accumulation despite price decline",
                    "confidence": "MEDIUM",
                    "type": "bullish_divergence",
                }

            # Bearish divergence: higher price high + lower OBV high
            if price_high_second > price_high_first * 1.02 and obv_high_second < obv_high_first * 0.98:
                return {
                    "signal": "SELL",
                    "reason": "Bearish OBV divergence — distribution despite price rise",
                    "confidence": "MEDIUM",
                    "type": "bearish_divergence",
                }

            return None
        except Exception:
            return None

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

        # Weighted scoring: BUY=1.0, HOLD=0.5, SELL=0.0
        # High confidence signals get 1.5x weight
        weighted_sum = 0
        total_weight = 0
        for s in signals.values():
            sig = s.get("signal", "HOLD")
            conf = s.get("confidence", "MEDIUM")
            weight = 1.5 if conf == "HIGH" else 1.0 if conf == "MEDIUM" else 0.5

            if sig == "BUY":
                weighted_sum += 1.0 * weight
            elif sig == "HOLD" or sig == "NORMAL" or sig == "ELEVATED" or sig == "HIGH VOLUME" or sig == "LOW VOLUME":
                weighted_sum += 0.5 * weight
            else:
                weighted_sum += 0.0 * weight
            total_weight += weight

        score = (weighted_sum / total_weight) * 100 if total_weight > 0 else 50
        return {"signals": signals, "support_resistance": support_res, "score": round(score, 1)}
