"""Institutional-grade technical analysis engine.

Provides multi-timeframe indicator computation, divergence detection,
chart-pattern recognition, volume analysis, and a weighted signal-scoring
framework.  Uses TA-Lib (C-based) for standard indicators and raw
pandas/numpy for Ichimoku, VWAP, Fibonacci, patterns, and volume profiling.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import talib

from src.utils.logger import setup_logger

logger = setup_logger("technical")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MIN_ROWS_BASIC = 30       # minimum for short-window indicators
_MIN_ROWS_FULL = 200       # ideal for SMA-200 / Ichimoku
_DIVERGENCE_LOOKBACK = 20  # bars to scan for peaks / troughs
_SR_CLUSTER_PCT = 0.015    # 1.5 % tolerance for clustering S/R levels
_PATTERN_SHOULDER_TOL = 0.05   # 5 % tolerance for H&S shoulder matching
_PATTERN_DOUBLE_TOL = 0.02     # 2 % tolerance for double top/bottom
_VOLUME_BREAKOUT_MULT = 2.0    # current vol > N * 20-day avg
_FIBONACCI_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]


# ---------------------------------------------------------------------------
# Data classes for structured signal output
# ---------------------------------------------------------------------------
@dataclass
class Signal:
    signal_name: str
    direction: str          # BUY / SELL / HOLD
    strength: float         # -100 .. +100
    reason: str
    timeframe: str = "daily"
    confluence: float = 1.0  # multiplier when confirmed across timeframes

    def to_dict(self) -> dict:
        return {
            "signal_name": self.signal_name,
            "direction": self.direction,
            "strength": round(self.strength, 2),
            "reason": self.reason,
            "timeframe": self.timeframe,
            "confluence": round(self.confluence, 2),
        }


@dataclass
class Divergence:
    divergence_type: str   # bullish / bearish / none
    indicator: str
    lookback_bars: int

    def to_dict(self) -> dict:
        return {
            "divergence_type": self.divergence_type,
            "indicator": self.indicator,
            "lookback_bars": self.lookback_bars,
        }


@dataclass
class PatternMatch:
    pattern_name: str
    confidence: float      # 0-1
    direction: str         # bullish / bearish

    def to_dict(self) -> dict:
        return {
            "pattern_name": self.pattern_name,
            "confidence": round(self.confidence, 3),
            "direction": self.direction,
        }


# =====================================================================
# Core Technical Analyzer
# =====================================================================
class TechnicalAnalyzer:
    """Compute indicators, detect divergences, recognise patterns,
    analyse volume, and produce scored signals across multiple timeframes."""

    # ------------------------------------------------------------------
    # 1. Enhanced Indicators
    # ------------------------------------------------------------------
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all technical indicators to an OHLCV DataFrame.

        Gracefully handles short DataFrames by skipping indicators that
        require more history than available.
        """
        r = df.copy()
        n = len(r)
        close = r["Close"].values.astype(float)
        high = r["High"].values.astype(float)
        low = r["Low"].values.astype(float)
        volume = r["Volume"].values.astype(float)

        # --- Trend: SMAs ------------------------------------------------
        if n >= 20:
            r["SMA_20"] = talib.SMA(close, timeperiod=20)
        if n >= 50:
            r["SMA_50"] = talib.SMA(close, timeperiod=50)
        if n >= 200:
            r["SMA_200"] = talib.SMA(close, timeperiod=200)

        # --- Trend: EMAs ------------------------------------------------
        if n >= 12:
            r["EMA_12"] = talib.EMA(close, timeperiod=12)
        if n >= 26:
            r["EMA_26"] = talib.EMA(close, timeperiod=26)

        # --- Momentum: RSI -----------------------------------------------
        if n >= 15:
            r["RSI_14"] = talib.RSI(close, timeperiod=14)

        # --- Momentum: MACD ----------------------------------------------
        if n >= 35:
            macd, macd_signal, macd_hist = talib.MACD(
                close, fastperiod=12, slowperiod=26, signalperiod=9,
            )
            r["MACD"] = macd
            r["MACD_signal"] = macd_signal
            r["MACD_hist"] = macd_hist

        # --- Volatility: Bollinger Bands ---------------------------------
        if n >= 20:
            bb_upper, bb_mid, bb_lower = talib.BBANDS(
                close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0,
            )
            r["BB_upper"] = bb_upper
            r["BB_mid"] = bb_mid
            r["BB_lower"] = bb_lower

        # --- Volatility: ATR ---------------------------------------------
        if n >= 15:
            r["ATR_14"] = talib.ATR(high, low, close, timeperiod=14)

        # --- Volume: OBV ------------------------------------------------
        r["OBV"] = talib.OBV(close, volume)

        # --- Momentum: Stochastic RSI -----------------------------------
        if n >= 20:
            fastk, fastd = talib.STOCHRSI(
                close, timeperiod=14, fastk_period=3, fastd_period=3, fastd_matype=0,
            )
            r["StochRSI_K"] = fastk
            r["StochRSI_D"] = fastd

        # --- Momentum: Williams %R ---------------------------------------
        if n >= 14:
            r["Williams_R"] = talib.WILLR(high, low, close, timeperiod=14)

        # --- Trend: CCI --------------------------------------------------
        if n >= 20:
            r["CCI"] = talib.CCI(high, low, close, timeperiod=20)

        # --- Trend: ADX ---------------------------------------------------
        if n >= 28:
            r["ADX"] = talib.ADX(high, low, close, timeperiod=14)
            r["PLUS_DI"] = talib.PLUS_DI(high, low, close, timeperiod=14)
            r["MINUS_DI"] = talib.MINUS_DI(high, low, close, timeperiod=14)

        # --- Ichimoku Cloud (manual) -------------------------------------
        self._compute_ichimoku(r, n)

        # --- VWAP (manual – intraday-style, resets daily) ----------------
        self._compute_vwap(r)

        # --- Fibonacci Retracement (recent swing) ------------------------
        self._compute_fibonacci(r, n)

        # --- Pivot Points (standard) ------------------------------------
        self._compute_pivot_points(r)

        return r

    # ---- Ichimoku -------------------------------------------------------
    @staticmethod
    def _compute_ichimoku(r: pd.DataFrame, n: int) -> None:
        """Compute Ichimoku Cloud components directly on *r*."""
        if n < 52:
            return
        high_s = r["High"]
        low_s = r["Low"]
        close_s = r["Close"]

        # Tenkan-sen (conversion line) – 9-period
        nine_high = high_s.rolling(window=9).max()
        nine_low = low_s.rolling(window=9).min()
        r["ichimoku_tenkan"] = (nine_high + nine_low) / 2

        # Kijun-sen (base line) – 26-period
        twenty_six_high = high_s.rolling(window=26).max()
        twenty_six_low = low_s.rolling(window=26).min()
        r["ichimoku_kijun"] = (twenty_six_high + twenty_six_low) / 2

        # Senkou Span A (leading span A) – midpoint of tenkan & kijun shifted 26
        r["ichimoku_senkou_a"] = (
            (r["ichimoku_tenkan"] + r["ichimoku_kijun"]) / 2
        ).shift(26)

        # Senkou Span B (leading span B) – 52-period high/low midpoint shifted 26
        fifty_two_high = high_s.rolling(window=52).max()
        fifty_two_low = low_s.rolling(window=52).min()
        r["ichimoku_senkou_b"] = ((fifty_two_high + fifty_two_low) / 2).shift(26)

        # Chikou Span (lagging span) – close shifted back 26
        r["ichimoku_chikou"] = close_s.shift(-26)

    # ---- VWAP -----------------------------------------------------------
    @staticmethod
    def _compute_vwap(r: pd.DataFrame) -> None:
        """Cumulative VWAP over the entire DataFrame (suitable for daily bars
        where each day is one bar).  For true intraday VWAP the data would
        need a date grouper."""
        tp = (r["High"] + r["Low"] + r["Close"]) / 3
        cum_tp_vol = (tp * r["Volume"]).cumsum()
        cum_vol = r["Volume"].cumsum().replace(0, np.nan)
        r["VWAP"] = cum_tp_vol / cum_vol

    # ---- Fibonacci Retracement ------------------------------------------
    @staticmethod
    def _compute_fibonacci(r: pd.DataFrame, n: int) -> None:
        """Identify the most recent swing high/low over the last
        min(120, n) bars and set Fibonacci retracement columns."""
        lookback = min(120, n)
        segment = r.iloc[-lookback:]
        swing_high = float(segment["High"].max())
        swing_low = float(segment["Low"].min())
        diff = swing_high - swing_low
        if diff < 1e-9:
            return
        for lvl in _FIBONACCI_LEVELS:
            r[f"fib_{lvl}"] = swing_high - diff * lvl

    # ---- Pivot Points ---------------------------------------------------
    @staticmethod
    def _compute_pivot_points(r: pd.DataFrame) -> None:
        """Standard pivot points from the previous bar."""
        if len(r) < 2:
            return
        prev = r.iloc[-2]
        pp = (float(prev["High"]) + float(prev["Low"]) + float(prev["Close"])) / 3
        r["PP"] = pp
        r["R1"] = 2 * pp - float(prev["Low"])
        r["S1"] = 2 * pp - float(prev["High"])
        r["R2"] = pp + (float(prev["High"]) - float(prev["Low"]))
        r["S2"] = pp - (float(prev["High"]) - float(prev["Low"]))
        r["R3"] = float(prev["High"]) + 2 * (pp - float(prev["Low"]))
        r["S3"] = float(prev["Low"]) - 2 * (float(prev["High"]) - pp)

    # ------------------------------------------------------------------
    # 2. Multi-Timeframe Analysis
    # ------------------------------------------------------------------
    def multi_timeframe_analysis(
        self, df: pd.DataFrame,
    ) -> Dict[str, Dict]:
        """Compute indicators on daily, weekly, and monthly timeframes.

        Returns a dict keyed by timeframe label with sub-dicts containing
        the latest indicator snapshot and a list of signals.
        """
        results: Dict[str, Dict] = {}
        timeframes = {"daily": df}

        # Resample to weekly / monthly if enough data
        if len(df) >= 10:
            weekly = self._resample_ohlcv(df, "W")
            if len(weekly) >= 5:
                timeframes["weekly"] = weekly
        if len(df) >= 30:
            monthly = self._resample_ohlcv(df, "ME")
            if len(monthly) >= 3:
                timeframes["monthly"] = monthly

        for tf_label, tf_df in timeframes.items():
            ind = self.compute_indicators(tf_df)
            latest = ind.iloc[-1]
            snapshot = {}
            for col in ["RSI_14", "MACD", "MACD_signal", "MACD_hist",
                         "SMA_20", "SMA_50", "SMA_200", "ADX",
                         "StochRSI_K", "StochRSI_D", "Williams_R", "CCI",
                         "ichimoku_tenkan", "ichimoku_kijun",
                         "ichimoku_senkou_a", "ichimoku_senkou_b"]:
                val = latest.get(col)
                if val is not None and pd.notna(val):
                    snapshot[col] = round(float(val), 4)
            snapshot["close"] = round(float(latest["Close"]), 4)
            signals = self._generate_signals_for_timeframe(ind, tf_label)
            results[tf_label] = {"snapshot": snapshot, "signals": signals}

        return results

    @staticmethod
    def _resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
        """Resample an OHLCV DataFrame to a coarser frequency."""
        # Ensure index is datetime
        tmp = df.copy()
        if not isinstance(tmp.index, pd.DatetimeIndex):
            if "Date" in tmp.columns:
                tmp.index = pd.to_datetime(tmp["Date"])
            else:
                tmp.index = pd.to_datetime(tmp.index)
        agg = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
        resampled = tmp.resample(rule).agg(agg).dropna(subset=["Close"])
        return resampled

    # ------------------------------------------------------------------
    # 3. Divergence Detection
    # ------------------------------------------------------------------
    def detect_divergences(self, df: pd.DataFrame) -> List[Divergence]:
        """Scan for RSI, MACD-histogram, and OBV divergences."""
        ind = self.compute_indicators(df)
        divs: List[Divergence] = []

        if len(ind) < _DIVERGENCE_LOOKBACK + 5:
            return divs

        close = ind["Close"].values.astype(float)
        tail = ind.iloc[-_DIVERGENCE_LOOKBACK:]

        # RSI divergence
        if "RSI_14" in ind.columns:
            rsi = ind["RSI_14"].values.astype(float)
            d = self._check_divergence(close, rsi, _DIVERGENCE_LOOKBACK, "RSI")
            if d:
                divs.append(d)

        # MACD histogram divergence
        if "MACD_hist" in ind.columns:
            macd_h = ind["MACD_hist"].values.astype(float)
            d = self._check_divergence(close, macd_h, _DIVERGENCE_LOOKBACK, "MACD_hist")
            if d:
                divs.append(d)

        # OBV divergence
        if "OBV" in ind.columns:
            obv = ind["OBV"].values.astype(float)
            d = self._check_divergence(close, obv, _DIVERGENCE_LOOKBACK, "OBV")
            if d:
                divs.append(d)

        return divs

    @staticmethod
    def _check_divergence(
        price: np.ndarray,
        indicator: np.ndarray,
        lookback: int,
        indicator_name: str,
    ) -> Optional[Divergence]:
        """Return a Divergence if a bearish or bullish divergence is found
        in the last *lookback* bars.  Uses simple peak/trough scanning."""
        n = len(price)
        if n < lookback + 2:
            return None

        seg_price = price[-(lookback):]
        seg_ind = indicator[-(lookback):]

        # Remove NaNs
        valid = ~(np.isnan(seg_price) | np.isnan(seg_ind))
        if valid.sum() < lookback // 2:
            return None
        seg_price = np.where(valid, seg_price, np.nan)
        seg_ind = np.where(valid, seg_ind, np.nan)

        # Find local peaks (order-2 simple scan)
        peaks = _local_extrema(seg_price, mode="peak")
        troughs = _local_extrema(seg_price, mode="trough")

        # Bearish divergence: price peak higher, indicator peak lower
        if len(peaks) >= 2:
            p1, p2 = peaks[-2], peaks[-1]
            if (not np.isnan(seg_price[p1]) and not np.isnan(seg_price[p2])
                    and not np.isnan(seg_ind[p1]) and not np.isnan(seg_ind[p2])):
                if seg_price[p2] > seg_price[p1] and seg_ind[p2] < seg_ind[p1]:
                    return Divergence("bearish", indicator_name, lookback)

        # Bullish divergence: price trough lower, indicator trough higher
        if len(troughs) >= 2:
            t1, t2 = troughs[-2], troughs[-1]
            if (not np.isnan(seg_price[t1]) and not np.isnan(seg_price[t2])
                    and not np.isnan(seg_ind[t1]) and not np.isnan(seg_ind[t2])):
                if seg_price[t2] < seg_price[t1] and seg_ind[t2] > seg_ind[t1]:
                    return Divergence("bullish", indicator_name, lookback)

        return None

    # ------------------------------------------------------------------
    # 4. Chart Pattern Recognition
    # ------------------------------------------------------------------
    def detect_patterns(self, df: pd.DataFrame) -> List[PatternMatch]:
        """Detect double-top/bottom, head-and-shoulders, and compute
        support/resistance levels and trend channel info."""
        patterns: List[PatternMatch] = []
        if len(df) < 30:
            return patterns

        close = df["Close"].values.astype(float)
        high = df["High"].values.astype(float)
        low = df["Low"].values.astype(float)

        # --- Double Top ---
        dt = self._detect_double_top(high, close)
        if dt:
            patterns.append(dt)

        # --- Double Bottom ---
        db = self._detect_double_bottom(low, close)
        if db:
            patterns.append(db)

        # --- Head and Shoulders ---
        hs = self._detect_head_and_shoulders(high, close)
        if hs:
            patterns.append(hs)

        # --- Inverse Head and Shoulders ---
        ihs = self._detect_inverse_head_and_shoulders(low, close)
        if ihs:
            patterns.append(ihs)

        # --- Trend Channel ---
        tc = self._detect_trend_channel(high, low)
        if tc:
            patterns.append(tc)

        return patterns

    def get_support_resistance(
        self, df: pd.DataFrame, window: int = 20, num_levels: int = 5,
    ) -> dict:
        """Identify clustered support and resistance levels using rolling
        highs/lows with proximity-based grouping."""
        if len(df) < window:
            return {
                "resistance_levels": [],
                "support_levels": [],
                "current": float(df["Close"].iloc[-1]) if len(df) > 0 else 0.0,
            }

        high_s = df["High"]
        low_s = df["Low"]
        current = float(df["Close"].iloc[-1])

        # Collect candidate levels from rolling highs/lows
        candidates: List[float] = []
        step = max(1, window // 4)
        for start in range(0, len(df) - window + 1, step):
            seg = df.iloc[start: start + window]
            candidates.append(float(seg["High"].max()))
            candidates.append(float(seg["Low"].min()))

        # Cluster nearby levels
        candidates.sort()
        clusters = self._cluster_levels(candidates, tolerance=_SR_CLUSTER_PCT)

        resistance = sorted([c for c in clusters if c > current])[:num_levels]
        support = sorted([c for c in clusters if c <= current], reverse=True)[:num_levels]

        return {
            "resistance_levels": [round(v, 4) for v in resistance],
            "support_levels": [round(v, 4) for v in support],
            "current": round(current, 4),
        }

    @staticmethod
    def _cluster_levels(values: List[float], tolerance: float) -> List[float]:
        """Merge nearby price levels into clusters, returning the average
        of each cluster."""
        if not values:
            return []
        clusters: List[List[float]] = [[values[0]]]
        for v in values[1:]:
            if abs(v - clusters[-1][-1]) / max(abs(clusters[-1][-1]), 1e-9) <= tolerance:
                clusters[-1].append(v)
            else:
                clusters.append([v])
        return [float(np.mean(c)) for c in clusters]

    # ---- Pattern helpers -----------------------------------------------
    @staticmethod
    def _detect_double_top(high: np.ndarray, close: np.ndarray) -> Optional[PatternMatch]:
        peaks = _local_extrema(high[-60:], mode="peak", order=5)
        if len(peaks) < 2:
            return None
        p1, p2 = peaks[-2], peaks[-1]
        v1, v2 = high[-60:][p1], high[-60:][p2]
        if np.isnan(v1) or np.isnan(v2):
            return None
        if abs(v1 - v2) / max(abs(v1), 1e-9) < _PATTERN_DOUBLE_TOL:
            # Check for valley between
            valley = np.nanmin(close[-60:][p1:p2 + 1]) if p2 > p1 else None
            if valley is not None and valley < min(v1, v2) * 0.98:
                conf = 1.0 - abs(v1 - v2) / max(abs(v1), 1e-9) / _PATTERN_DOUBLE_TOL
                return PatternMatch("double_top", min(max(conf, 0.5), 1.0), "bearish")
        return None

    @staticmethod
    def _detect_double_bottom(low: np.ndarray, close: np.ndarray) -> Optional[PatternMatch]:
        troughs = _local_extrema(low[-60:], mode="trough", order=5)
        if len(troughs) < 2:
            return None
        t1, t2 = troughs[-2], troughs[-1]
        v1, v2 = low[-60:][t1], low[-60:][t2]
        if np.isnan(v1) or np.isnan(v2):
            return None
        if abs(v1 - v2) / max(abs(v1), 1e-9) < _PATTERN_DOUBLE_TOL:
            peak = np.nanmax(close[-60:][t1:t2 + 1]) if t2 > t1 else None
            if peak is not None and peak > max(v1, v2) * 1.02:
                conf = 1.0 - abs(v1 - v2) / max(abs(v1), 1e-9) / _PATTERN_DOUBLE_TOL
                return PatternMatch("double_bottom", min(max(conf, 0.5), 1.0), "bullish")
        return None

    @staticmethod
    def _detect_head_and_shoulders(
        high: np.ndarray, close: np.ndarray,
    ) -> Optional[PatternMatch]:
        peaks = _local_extrema(high[-90:], mode="peak", order=5)
        if len(peaks) < 3:
            return None
        # Take last 3 peaks
        p_left, p_head, p_right = peaks[-3], peaks[-2], peaks[-1]
        vl = high[-90:][p_left]
        vh = high[-90:][p_head]
        vr = high[-90:][p_right]
        if np.isnan(vl) or np.isnan(vh) or np.isnan(vr):
            return None
        # Head must be highest
        if vh <= vl or vh <= vr:
            return None
        # Shoulders within tolerance
        if abs(vl - vr) / max(abs(vl), 1e-9) < _PATTERN_SHOULDER_TOL:
            conf = min(1.0, (vh - max(vl, vr)) / max(abs(vh), 1e-9) * 5)
            return PatternMatch("head_and_shoulders", min(max(conf, 0.4), 1.0), "bearish")
        return None

    @staticmethod
    def _detect_inverse_head_and_shoulders(
        low: np.ndarray, close: np.ndarray,
    ) -> Optional[PatternMatch]:
        troughs = _local_extrema(low[-90:], mode="trough", order=5)
        if len(troughs) < 3:
            return None
        t_left, t_head, t_right = troughs[-3], troughs[-2], troughs[-1]
        vl = low[-90:][t_left]
        vh = low[-90:][t_head]
        vr = low[-90:][t_right]
        if np.isnan(vl) or np.isnan(vh) or np.isnan(vr):
            return None
        if vh >= vl or vh >= vr:
            return None
        if abs(vl - vr) / max(abs(vl), 1e-9) < _PATTERN_SHOULDER_TOL:
            conf = min(1.0, (min(vl, vr) - vh) / max(abs(vh), 1e-9) * 5)
            return PatternMatch("inverse_head_and_shoulders", min(max(conf, 0.4), 1.0), "bullish")
        return None

    @staticmethod
    def _detect_trend_channel(
        high: np.ndarray, low: np.ndarray, window: int = 40,
    ) -> Optional[PatternMatch]:
        """Fit linear regression to highs and lows to detect trend channels."""
        seg_high = high[-window:]
        seg_low = low[-window:]
        if len(seg_high) < window:
            return None

        valid_high = ~np.isnan(seg_high)
        valid_low = ~np.isnan(seg_low)
        if valid_high.sum() < window // 2 or valid_low.sum() < window // 2:
            return None

        x = np.arange(len(seg_high), dtype=float)

        # Fit highs
        slope_h, intercept_h = np.polyfit(x[valid_high], seg_high[valid_high], 1)
        # Fit lows
        slope_l, intercept_l = np.polyfit(x[valid_low], seg_low[valid_low], 1)

        # Parallel-ish slopes indicate a channel
        if abs(slope_h) < 1e-9 and abs(slope_l) < 1e-9:
            return None

        slope_ratio = slope_l / slope_h if abs(slope_h) > 1e-9 else 0
        is_parallel = 0.5 < slope_ratio < 2.0

        if is_parallel:
            direction = "bullish" if slope_h > 0 else "bearish"
            parallelism = 1.0 - abs(1.0 - slope_ratio)
            conf = min(max(parallelism, 0.3), 0.9)
            return PatternMatch(
                f"trend_channel_{'ascending' if slope_h > 0 else 'descending'}",
                conf,
                direction,
            )
        return None

    # ------------------------------------------------------------------
    # 5. Volume Analysis
    # ------------------------------------------------------------------
    def analyze_volume(self, df: pd.DataFrame) -> dict:
        """Comprehensive volume analysis."""
        result: dict = {
            "volume_profile": {},
            "volume_trend": "unknown",
            "accumulation_distribution": 0.0,
            "volume_breakout": False,
            "details": {},
        }
        if len(df) < 20:
            return result

        close = df["Close"].values.astype(float)
        high = df["High"].values.astype(float)
        low = df["Low"].values.astype(float)
        volume = df["Volume"].values.astype(float)

        # --- Volume Profile: volume-weighted price levels ----------------
        typical_price = (high + low + close) / 3
        valid = ~(np.isnan(typical_price) | np.isnan(volume) | (volume == 0))
        if valid.sum() > 10:
            tp_valid = typical_price[valid]
            vol_valid = volume[valid]
            # 10-bin histogram
            price_min, price_max = float(np.nanmin(tp_valid)), float(np.nanmax(tp_valid))
            if price_max - price_min > 1e-9:
                bin_edges = np.linspace(price_min, price_max, 11)
                bin_indices = np.digitize(tp_valid, bin_edges) - 1
                bin_indices = np.clip(bin_indices, 0, 9)
                profile = {}
                for i in range(10):
                    mask = bin_indices == i
                    mid = round((bin_edges[i] + bin_edges[i + 1]) / 2, 2)
                    profile[mid] = float(np.sum(vol_valid[mask]))
                result["volume_profile"] = profile

                # Point-of-control: price level with highest volume
                poc_idx = max(profile, key=profile.get)
                result["details"]["point_of_control"] = poc_idx

        # --- Volume trend: expanding or contracting ----------------------
        vol_20 = volume[-20:]
        vol_first_half = vol_20[:10]
        vol_second_half = vol_20[10:]
        avg_first = float(np.nanmean(vol_first_half))
        avg_second = float(np.nanmean(vol_second_half))
        if avg_first > 0:
            vol_change = (avg_second - avg_first) / avg_first
            if vol_change > 0.1:
                result["volume_trend"] = "expanding"
            elif vol_change < -0.1:
                result["volume_trend"] = "contracting"
            else:
                result["volume_trend"] = "stable"
            result["details"]["volume_change_pct"] = round(vol_change * 100, 2)

        # --- Accumulation / Distribution ratio ---------------------------
        price_change = np.diff(close)
        vol_for_ad = volume[1:]
        valid_ad = ~(np.isnan(price_change) | np.isnan(vol_for_ad))
        if valid_ad.sum() > 5:
            up_vol = float(np.sum(vol_for_ad[(price_change > 0) & valid_ad]))
            down_vol = float(np.sum(vol_for_ad[(price_change < 0) & valid_ad]))
            total_vol = up_vol + down_vol
            if total_vol > 0:
                result["accumulation_distribution"] = round(
                    (up_vol - down_vol) / total_vol, 4,
                )

        # --- Volume breakout detection -----------------------------------
        avg_20_vol = float(np.nanmean(volume[-20:]))
        current_vol = float(volume[-1]) if not np.isnan(volume[-1]) else 0.0
        if avg_20_vol > 0 and current_vol > _VOLUME_BREAKOUT_MULT * avg_20_vol:
            result["volume_breakout"] = True
            result["details"]["breakout_ratio"] = round(
                current_vol / avg_20_vol, 2,
            )

        return result

    # ------------------------------------------------------------------
    # 7. Trend Analysis
    # ------------------------------------------------------------------
    def analyze_trend(self, df: pd.DataFrame) -> dict:
        """ADX-based trend strength, direction, duration, and Ichimoku position."""
        ind = self.compute_indicators(df)
        latest = ind.iloc[-1]
        close = float(latest["Close"])
        result: dict = {
            "trend_strength": "no_trend",
            "trend_direction": "neutral",
            "trend_duration_bars": 0,
            "adx_value": None,
            "ichimoku_position": "unknown",
        }

        # ADX trend strength
        adx = latest.get("ADX")
        if adx is not None and pd.notna(adx):
            adx_val = float(adx)
            result["adx_value"] = round(adx_val, 2)
            if adx_val < 20:
                result["trend_strength"] = "no_trend"
            elif adx_val < 40:
                result["trend_strength"] = "trending"
            else:
                result["trend_strength"] = "strong_trend"

        # Direction from 50/200 SMA relationship
        sma50 = latest.get("SMA_50")
        sma200 = latest.get("SMA_200")
        if sma50 is not None and sma200 is not None and pd.notna(sma50) and pd.notna(sma200):
            if float(sma50) > float(sma200):
                result["trend_direction"] = "bullish"
            elif float(sma50) < float(sma200):
                result["trend_direction"] = "bearish"
            else:
                result["trend_direction"] = "neutral"

        # Trend duration: how many consecutive bars has close been
        # above (bullish) or below (bearish) the 50-SMA?
        if "SMA_50" in ind.columns:
            sma_col = ind["SMA_50"].values
            close_col = ind["Close"].values
            duration = 0
            if result["trend_direction"] == "bullish":
                for i in range(len(ind) - 1, -1, -1):
                    if pd.notna(sma_col[i]) and close_col[i] > sma_col[i]:
                        duration += 1
                    else:
                        break
            elif result["trend_direction"] == "bearish":
                for i in range(len(ind) - 1, -1, -1):
                    if pd.notna(sma_col[i]) and close_col[i] < sma_col[i]:
                        duration += 1
                    else:
                        break
            result["trend_duration_bars"] = duration

        # Price position relative to Ichimoku cloud
        senkou_a = latest.get("ichimoku_senkou_a")
        senkou_b = latest.get("ichimoku_senkou_b")
        if (senkou_a is not None and senkou_b is not None
                and pd.notna(senkou_a) and pd.notna(senkou_b)):
            cloud_top = max(float(senkou_a), float(senkou_b))
            cloud_bot = min(float(senkou_a), float(senkou_b))
            if close > cloud_top:
                result["ichimoku_position"] = "above_cloud"
            elif close < cloud_bot:
                result["ichimoku_position"] = "below_cloud"
            else:
                result["ichimoku_position"] = "inside_cloud"

        return result

    # ------------------------------------------------------------------
    # Signal generation per timeframe
    # ------------------------------------------------------------------
    def _generate_signals_for_timeframe(
        self, ind: pd.DataFrame, tf_label: str,
    ) -> List[dict]:
        """Produce a list of Signal dicts from an indicator DataFrame."""
        signals: List[Signal] = []
        if len(ind) < 2:
            return [s.to_dict() for s in signals]

        latest = ind.iloc[-1]
        prev = ind.iloc[-2]
        close = float(latest["Close"])

        # ---- RSI --------------------------------------------------------
        rsi = latest.get("RSI_14")
        if rsi is not None and pd.notna(rsi):
            rsi = float(rsi)
            if rsi < 20:
                signals.append(Signal("rsi_extreme", "BUY", 40, f"RSI deeply oversold ({rsi:.1f})", tf_label))
            elif rsi < 30:
                signals.append(Signal("rsi_oversold", "BUY", 30, f"RSI oversold ({rsi:.1f})", tf_label))
            elif rsi > 80:
                signals.append(Signal("rsi_extreme", "SELL", -40, f"RSI deeply overbought ({rsi:.1f})", tf_label))
            elif rsi > 70:
                signals.append(Signal("rsi_overbought", "SELL", -30, f"RSI overbought ({rsi:.1f})", tf_label))
            else:
                signals.append(Signal("rsi_neutral", "HOLD", 0, f"RSI neutral ({rsi:.1f})", tf_label))

        # ---- MACD crossover ---------------------------------------------
        macd_val = latest.get("MACD")
        macd_sig = latest.get("MACD_signal")
        prev_macd = prev.get("MACD")
        prev_sig = prev.get("MACD_signal")
        if (all(v is not None and pd.notna(v) for v in [macd_val, macd_sig, prev_macd, prev_sig])):
            macd_val, macd_sig = float(macd_val), float(macd_sig)
            prev_macd, prev_sig = float(prev_macd), float(prev_sig)
            if prev_macd <= prev_sig and macd_val > macd_sig:
                signals.append(Signal("macd_crossover", "BUY", 55, "MACD bullish crossover", tf_label))
            elif prev_macd >= prev_sig and macd_val < macd_sig:
                signals.append(Signal("macd_crossover", "SELL", -55, "MACD bearish crossover", tf_label))
            elif macd_val > macd_sig:
                signals.append(Signal("macd_position", "BUY", 25, "MACD above signal", tf_label))
            else:
                signals.append(Signal("macd_position", "SELL", -25, "MACD below signal", tf_label))

        # ---- SMA crossovers --------------------------------------------
        sma20 = latest.get("SMA_20")
        sma50 = latest.get("SMA_50")
        sma200 = latest.get("SMA_200")
        prev_sma20 = prev.get("SMA_20")
        prev_sma50 = prev.get("SMA_50")

        if all(v is not None and pd.notna(v) for v in [sma20, sma50, prev_sma20, prev_sma50]):
            sma20_f, sma50_f = float(sma20), float(sma50)
            p_sma20_f, p_sma50_f = float(prev_sma20), float(prev_sma50)
            if p_sma20_f <= p_sma50_f and sma20_f > sma50_f:
                signals.append(Signal("golden_cross_20_50", "BUY", 60, "SMA20 crossed above SMA50", tf_label))
            elif p_sma20_f >= p_sma50_f and sma20_f < sma50_f:
                signals.append(Signal("death_cross_20_50", "SELL", -60, "SMA20 crossed below SMA50", tf_label))

        if sma50 is not None and sma200 is not None and pd.notna(sma50) and pd.notna(sma200):
            prev_sma200 = prev.get("SMA_200")
            if prev_sma200 is not None and pd.notna(prev_sma200):
                if float(prev.get("SMA_50", 0)) <= float(prev_sma200) and float(sma50) > float(sma200):
                    signals.append(Signal("golden_cross_50_200", "BUY", 70, "SMA50 crossed above SMA200 (golden cross)", tf_label))
                elif float(prev.get("SMA_50", 0)) >= float(prev_sma200) and float(sma50) < float(sma200):
                    signals.append(Signal("death_cross_50_200", "SELL", -70, "SMA50 crossed below SMA200 (death cross)", tf_label))

        # ---- Price vs SMAs (weak) ----------------------------------------
        if sma200 is not None and pd.notna(sma200):
            if close > float(sma200):
                signals.append(Signal("price_above_sma200", "BUY", 20, "Price above SMA200", tf_label))
            else:
                signals.append(Signal("price_below_sma200", "SELL", -20, "Price below SMA200", tf_label))

        # ---- Bollinger Bands --------------------------------------------
        bb_upper = latest.get("BB_upper")
        bb_lower = latest.get("BB_lower")
        if bb_upper is not None and bb_lower is not None and pd.notna(bb_upper) and pd.notna(bb_lower):
            bb_upper_f, bb_lower_f = float(bb_upper), float(bb_lower)
            if close < bb_lower_f:
                signals.append(Signal("bb_oversold", "BUY", 35, "Price below lower Bollinger Band", tf_label))
            elif close > bb_upper_f:
                signals.append(Signal("bb_overbought", "SELL", -35, "Price above upper Bollinger Band", tf_label))

        # ---- Stochastic RSI ---------------------------------------------
        stoch_k = latest.get("StochRSI_K")
        stoch_d = latest.get("StochRSI_D")
        if stoch_k is not None and stoch_d is not None and pd.notna(stoch_k) and pd.notna(stoch_d):
            stoch_k_f, stoch_d_f = float(stoch_k), float(stoch_d)
            prev_k = prev.get("StochRSI_K")
            prev_d = prev.get("StochRSI_D")
            if prev_k is not None and prev_d is not None and pd.notna(prev_k) and pd.notna(prev_d):
                if float(prev_k) <= float(prev_d) and stoch_k_f > stoch_d_f and stoch_k_f < 30:
                    signals.append(Signal("stochrsi_crossover", "BUY", 50, "StochRSI bullish crossover in oversold zone", tf_label))
                elif float(prev_k) >= float(prev_d) and stoch_k_f < stoch_d_f and stoch_k_f > 70:
                    signals.append(Signal("stochrsi_crossover", "SELL", -50, "StochRSI bearish crossover in overbought zone", tf_label))
            if stoch_k_f < 10:
                signals.append(Signal("stochrsi_extreme", "BUY", 35, f"StochRSI extreme oversold ({stoch_k_f:.1f})", tf_label))
            elif stoch_k_f > 90:
                signals.append(Signal("stochrsi_extreme", "SELL", -35, f"StochRSI extreme overbought ({stoch_k_f:.1f})", tf_label))

        # ---- Williams %R ------------------------------------------------
        willr = latest.get("Williams_R")
        if willr is not None and pd.notna(willr):
            willr_f = float(willr)
            if willr_f < -80:
                signals.append(Signal("williams_r", "BUY", 30, f"Williams %R oversold ({willr_f:.1f})", tf_label))
            elif willr_f > -20:
                signals.append(Signal("williams_r", "SELL", -30, f"Williams %R overbought ({willr_f:.1f})", tf_label))

        # ---- CCI --------------------------------------------------------
        cci = latest.get("CCI")
        if cci is not None and pd.notna(cci):
            cci_f = float(cci)
            if cci_f < -200:
                signals.append(Signal("cci_extreme", "BUY", 40, f"CCI extremely oversold ({cci_f:.1f})", tf_label))
            elif cci_f < -100:
                signals.append(Signal("cci_oversold", "BUY", 25, f"CCI oversold ({cci_f:.1f})", tf_label))
            elif cci_f > 200:
                signals.append(Signal("cci_extreme", "SELL", -40, f"CCI extremely overbought ({cci_f:.1f})", tf_label))
            elif cci_f > 100:
                signals.append(Signal("cci_overbought", "SELL", -25, f"CCI overbought ({cci_f:.1f})", tf_label))

        # ---- ADX trend strength -----------------------------------------
        adx = latest.get("ADX")
        plus_di = latest.get("PLUS_DI")
        minus_di = latest.get("MINUS_DI")
        if (adx is not None and plus_di is not None and minus_di is not None
                and pd.notna(adx) and pd.notna(plus_di) and pd.notna(minus_di)):
            adx_f = float(adx)
            if adx_f > 25:
                if float(plus_di) > float(minus_di):
                    strength = min(60, 30 + (adx_f - 25))
                    signals.append(Signal("adx_trend", "BUY", strength, f"Strong uptrend (ADX={adx_f:.1f})", tf_label))
                else:
                    strength = max(-60, -(30 + (adx_f - 25)))
                    signals.append(Signal("adx_trend", "SELL", strength, f"Strong downtrend (ADX={adx_f:.1f})", tf_label))

        # ---- Ichimoku signals -------------------------------------------
        tenkan = latest.get("ichimoku_tenkan")
        kijun = latest.get("ichimoku_kijun")
        senkou_a = latest.get("ichimoku_senkou_a")
        senkou_b = latest.get("ichimoku_senkou_b")

        if (tenkan is not None and kijun is not None
                and pd.notna(tenkan) and pd.notna(kijun)):
            prev_tenkan = prev.get("ichimoku_tenkan")
            prev_kijun = prev.get("ichimoku_kijun")
            if (prev_tenkan is not None and prev_kijun is not None
                    and pd.notna(prev_tenkan) and pd.notna(prev_kijun)):
                if float(prev_tenkan) <= float(prev_kijun) and float(tenkan) > float(kijun):
                    signals.append(Signal("ichimoku_tk_cross", "BUY", 50, "Ichimoku TK bullish cross", tf_label))
                elif float(prev_tenkan) >= float(prev_kijun) and float(tenkan) < float(kijun):
                    signals.append(Signal("ichimoku_tk_cross", "SELL", -50, "Ichimoku TK bearish cross", tf_label))

        if (senkou_a is not None and senkou_b is not None
                and pd.notna(senkou_a) and pd.notna(senkou_b)):
            cloud_top = max(float(senkou_a), float(senkou_b))
            cloud_bot = min(float(senkou_a), float(senkou_b))
            if close > cloud_top:
                signals.append(Signal("ichimoku_cloud", "BUY", 40, "Price above Ichimoku cloud", tf_label))
            elif close < cloud_bot:
                signals.append(Signal("ichimoku_cloud", "SELL", -40, "Price below Ichimoku cloud", tf_label))
            else:
                signals.append(Signal("ichimoku_cloud", "HOLD", 0, "Price inside Ichimoku cloud (indecision)", tf_label))

        # ---- VWAP -------------------------------------------------------
        vwap = latest.get("VWAP")
        if vwap is not None and pd.notna(vwap):
            vwap_f = float(vwap)
            pct_diff = (close - vwap_f) / max(abs(vwap_f), 1e-9)
            if pct_diff > 0.02:
                signals.append(Signal("vwap", "BUY", 20, f"Price {pct_diff*100:.1f}% above VWAP", tf_label))
            elif pct_diff < -0.02:
                signals.append(Signal("vwap", "SELL", -20, f"Price {abs(pct_diff)*100:.1f}% below VWAP", tf_label))

        # ---- Pivot Points -----------------------------------------------
        pp = latest.get("PP")
        if pp is not None and pd.notna(pp):
            pp_f = float(pp)
            r1 = float(latest.get("R1", np.nan))
            s1 = float(latest.get("S1", np.nan))
            if not np.isnan(r1) and close > r1:
                signals.append(Signal("pivot_breakout", "BUY", 30, "Price above R1 pivot", tf_label))
            elif not np.isnan(s1) and close < s1:
                signals.append(Signal("pivot_breakdown", "SELL", -30, "Price below S1 pivot", tf_label))

        return [s.to_dict() for s in signals]

    # ------------------------------------------------------------------
    # 6. Signal Scoring
    # ------------------------------------------------------------------
    def compute_composite_score(
        self,
        mtf_results: Dict[str, Dict],
        divergences: List[Divergence],
        patterns: List[PatternMatch],
        volume_analysis: dict,
    ) -> dict:
        """Weighted-average score (0-100) aggregating all signal sources.

        Scoring rules:
        - Each signal's raw strength is in [-100, +100].
        - Recency weighting: daily 1.0, weekly 0.8, monthly 0.6.
        - Confluence multiplier: signal present on multiple timeframes
          gets 1.5x weight.
        - Divergences / patterns treated as strong signals (+-80..100).
        - Final score normalised to 0-100 (50 = neutral).
        """
        recency_weights = {"daily": 1.0, "weekly": 0.8, "monthly": 0.6}

        # Collect all signal strengths with weights
        weighted_items: List[Tuple[float, float]] = []  # (strength, weight)

        # -- Indicator signals per timeframe ---------------------------------
        signal_names_per_tf: Dict[str, set] = {}
        for tf_label, data in mtf_results.items():
            rw = recency_weights.get(tf_label, 1.0)
            names = set()
            for sig in data.get("signals", []):
                name = sig["signal_name"]
                names.add(name)
                weighted_items.append((sig["strength"], rw))
            signal_names_per_tf[tf_label] = names

        # Confluence: find signals present in >=2 timeframes and bump weight
        if len(signal_names_per_tf) >= 2:
            all_names = set()
            for names in signal_names_per_tf.values():
                all_names.update(names)
            for name in all_names:
                tf_count = sum(1 for names in signal_names_per_tf.values() if name in names)
                if tf_count >= 2:
                    # Add a bonus entry for confluence
                    # Find the strongest signal with this name
                    best_strength = 0.0
                    for data in mtf_results.values():
                        for sig in data.get("signals", []):
                            if sig["signal_name"] == name:
                                if abs(sig["strength"]) > abs(best_strength):
                                    best_strength = sig["strength"]
                    weighted_items.append((best_strength * 0.5, 1.5))

        # -- Divergences (strong signals: 80-90) ----------------------------
        for d in divergences:
            if d.divergence_type == "bullish":
                weighted_items.append((85, 1.2))
            elif d.divergence_type == "bearish":
                weighted_items.append((-85, 1.2))

        # -- Pattern matches (strong signals: 80-100) -----------------------
        for p in patterns:
            base = 90 * p.confidence
            if p.direction == "bearish":
                base = -base
            weighted_items.append((base, 1.3))

        # -- Volume breakout bonus ------------------------------------------
        if volume_analysis.get("volume_breakout"):
            # Volume breakout amplifies direction
            ad = volume_analysis.get("accumulation_distribution", 0.0)
            bonus = 30 if ad > 0 else -30
            weighted_items.append((bonus, 1.0))

        # -- Accumulation/distribution signal (weak) -------------------------
        ad = volume_analysis.get("accumulation_distribution", 0.0)
        if abs(ad) > 0.3:
            weighted_items.append((ad * 30, 0.8))

        # Compute weighted average
        if not weighted_items:
            return {"raw_score": 0.0, "score": 50.0, "signal_count": 0, "bias": "neutral"}

        total_w = sum(abs(w) for _, w in weighted_items)
        if total_w < 1e-9:
            return {"raw_score": 0.0, "score": 50.0, "signal_count": 0, "bias": "neutral"}

        raw = sum(s * w for s, w in weighted_items) / total_w
        # raw is in [-100, 100]; map to 0-100
        score = max(0.0, min(100.0, 50.0 + raw / 2.0))

        if score >= 65:
            bias = "bullish"
        elif score >= 55:
            bias = "slightly_bullish"
        elif score <= 35:
            bias = "bearish"
        elif score <= 45:
            bias = "slightly_bearish"
        else:
            bias = "neutral"

        return {
            "raw_score": round(raw, 2),
            "score": round(score, 1),
            "signal_count": len(weighted_items),
            "bias": bias,
        }

    # ------------------------------------------------------------------
    # Confluence scoring helper
    # ------------------------------------------------------------------
    def compute_confluence_score(self, mtf_results: Dict[str, Dict]) -> dict:
        """Return a confluence summary: how many signals agree across
        timeframes and the overall alignment."""
        if not mtf_results:
            return {"confluence_score": 0.0, "aligned_signals": 0, "total_signals": 0}

        direction_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
        total = 0
        for data in mtf_results.values():
            for sig in data.get("signals", []):
                direction_counts[sig["direction"]] = direction_counts.get(sig["direction"], 0) + 1
                total += 1

        if total == 0:
            return {"confluence_score": 0.0, "aligned_signals": 0, "total_signals": 0}

        dominant = max(direction_counts, key=direction_counts.get)
        aligned = direction_counts[dominant]
        confluence = aligned / total

        return {
            "confluence_score": round(confluence, 3),
            "dominant_direction": dominant,
            "aligned_signals": aligned,
            "total_signals": total,
        }

    # ------------------------------------------------------------------
    # Legacy-compatible convenience method
    # ------------------------------------------------------------------
    def get_signals(self, df: pd.DataFrame) -> dict:
        """Generate buy/sell/hold signals from indicators (legacy API).

        Returns a flat dict of signal-name -> {signal, value/reason}
        for backward compatibility, but now powered by the full engine.
        """
        ind = self.compute_indicators(df)
        raw_signals = self._generate_signals_for_timeframe(ind, "daily")

        # Convert to legacy format
        out: dict = {}
        for s in raw_signals:
            out[s["signal_name"]] = {
                "signal": s["direction"],
                "strength": s["strength"],
                "reason": s["reason"],
            }
        return out

    # ------------------------------------------------------------------
    # Full analysis orchestrator
    # ------------------------------------------------------------------
    def full_analysis(self, df: pd.DataFrame) -> dict:
        """Run every analysis module and return a comprehensive result dict."""
        mtf = self.multi_timeframe_analysis(df)
        divergences = self.detect_divergences(df)
        patterns = self.detect_patterns(df)
        sr = self.get_support_resistance(df)
        vol = self.analyze_volume(df)
        trend = self.analyze_trend(df)
        confluence = self.compute_confluence_score(mtf)
        scoring = self.compute_composite_score(mtf, divergences, patterns, vol)

        return {
            "multi_timeframe": mtf,
            "divergences": [d.to_dict() for d in divergences],
            "patterns": [p.to_dict() for p in patterns],
            "support_resistance": sr,
            "volume_analysis": vol,
            "trend": trend,
            "confluence": confluence,
            "scoring": scoring,
            "score": scoring["score"],
        }


# =====================================================================
# Helper: local extrema detection
# =====================================================================
def _local_extrema(
    arr: np.ndarray, mode: str = "peak", order: int = 3,
) -> List[int]:
    """Return indices of local peaks or troughs using a simple rolling
    comparison.  *order* is the number of bars on each side that must be
    lower (peak) or higher (trough)."""
    n = len(arr)
    indices: List[int] = []
    for i in range(order, n - order):
        if np.isnan(arr[i]):
            continue
        if mode == "peak":
            is_ext = all(
                (np.isnan(arr[i - j]) or arr[i] >= arr[i - j]) and
                (np.isnan(arr[i + j]) or arr[i] >= arr[i + j])
                for j in range(1, order + 1)
            )
        else:  # trough
            is_ext = all(
                (np.isnan(arr[i - j]) or arr[i] <= arr[i - j]) and
                (np.isnan(arr[i + j]) or arr[i] <= arr[i + j])
                for j in range(1, order + 1)
            )
        if is_ext:
            indices.append(i)
    return indices


# =====================================================================
# Plugin adapter for pipeline
# =====================================================================
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer  # noqa: E402


class TechnicalAnalyzerPlugin(_BaseAnalyzer):
    """Pipeline-compatible wrapper around TechnicalAnalyzer.

    Attributes:
        name:           ``"technical"``
        default_weight: ``0.20``
    """

    name = "technical"
    default_weight = 0.20

    def __init__(self) -> None:
        self._analyzer = TechnicalAnalyzer()

    def analyze(self, ticker: str, ctx) -> dict:
        """Run full technical analysis and return a dict with ``"score"``
        (0-100) plus all sub-analyses."""
        df = ctx.price_data.get(ticker)
        if df is None or (hasattr(df, "empty") and df.empty):
            return {"error": "No price data", "score": 50}

        try:
            result = self._analyzer.full_analysis(df)
        except Exception as exc:
            logger.warning("Technical analysis failed for %s: %s", ticker, exc)
            # Fallback: try basic signals only
            try:
                signals = self._analyzer.get_signals(df)
                buy_count = sum(
                    1 for s in signals.values() if s.get("signal") == "BUY"
                )
                total = max(len(signals), 1)
                score = round((buy_count / total) * 100, 1)
                return {"signals": signals, "score": score, "fallback": True}
            except Exception as inner:
                logger.error("Fallback also failed for %s: %s", ticker, inner)
                return {"error": str(exc), "score": 50}

        return result
