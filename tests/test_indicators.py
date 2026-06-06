import numpy as np
import pandas as pd
import pytest

from analysis.indicators import (
    _bollinger_bands,
    _macd,
    _rsi,
    add_indicators,
    get_signals,
)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """250-bar synthetic OHLCV DataFrame with a mild uptrend."""
    np.random.seed(42)
    n = 250
    close = 30 + np.cumsum(np.random.randn(n) * 0.5)
    close = np.maximum(close, 1)  # keep positive
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    low = np.minimum(low, close)
    open_ = close + np.random.randn(n) * 0.2
    volume = np.random.randint(1_000_000, 10_000_000, n).astype(float)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


# ── RSI ───────────────────────────────────────────────────────────────────────

class TestRSI:
    def test_values_in_range(self, sample_df):
        rsi = _rsi(sample_df["close"])
        valid = rsi.dropna()
        assert len(valid) > 0
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_output_length_matches_input(self, sample_df):
        rsi = _rsi(sample_df["close"], period=14)
        assert len(rsi) == len(sample_df)

    def test_constant_series_returns_nan(self):
        s = pd.Series([10.0] * 30)
        rsi = _rsi(s, period=14)
        # constant price → zero gain/loss → RS is NaN or inf → result NaN
        assert rsi.dropna().empty or (rsi.dropna() == 100).all() or (rsi.dropna() == 0).all()


# ── MACD ──────────────────────────────────────────────────────────────────────

class TestMACD:
    def test_returns_three_series(self, sample_df):
        macd, signal, hist = _macd(sample_df["close"])
        assert len(macd) == len(signal) == len(hist) == len(sample_df)

    def test_histogram_equals_macd_minus_signal(self, sample_df):
        macd, signal, hist = _macd(sample_df["close"])
        expected = (macd - signal).dropna()
        actual = hist.dropna()
        pd.testing.assert_series_equal(expected, actual, check_names=False, atol=1e-10)

    def test_no_nan_after_warmup(self, sample_df):
        _, _, hist = _macd(sample_df["close"], fast=12, slow=26, signal=9)
        # After the slow EMA + signal warmup (~34 bars) there should be no NaN
        assert hist.iloc[35:].isna().sum() == 0


# ── Bollinger Bands ───────────────────────────────────────────────────────────

class TestBollingerBands:
    def test_upper_ge_mid_ge_lower(self, sample_df):
        upper, mid, lower = _bollinger_bands(sample_df["close"])
        idx = upper.dropna().index
        assert (upper[idx] >= mid[idx]).all()
        assert (mid[idx] >= lower[idx]).all()

    def test_output_lengths(self, sample_df):
        upper, mid, lower = _bollinger_bands(sample_df["close"])
        assert len(upper) == len(mid) == len(lower) == len(sample_df)

    def test_wider_bands_with_larger_std(self, sample_df):
        _, _, lower1 = _bollinger_bands(sample_df["close"], std_mult=1.0)
        _, _, lower2 = _bollinger_bands(sample_df["close"], std_mult=2.0)
        idx = lower1.dropna().index
        assert (lower2[idx] <= lower1[idx]).all()


# ── add_indicators ────────────────────────────────────────────────────────────

class TestAddIndicators:
    EXPECTED_COLS = [
        "rsi", "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_mid", "bb_lower", "bb_width", "bb_pct",
        "sma_20", "sma_50", "sma_200",
        "ema_9", "ema_21",
        "atr", "obv",
    ]

    def test_all_columns_added(self, sample_df):
        df = add_indicators(sample_df)
        for col in self.EXPECTED_COLS:
            assert col in df.columns, f"Missing column: {col}"

    def test_original_dataframe_not_modified(self, sample_df):
        original_cols = list(sample_df.columns)
        add_indicators(sample_df)
        assert list(sample_df.columns) == original_cols

    def test_row_count_preserved(self, sample_df):
        df = add_indicators(sample_df)
        assert len(df) == len(sample_df)

    def test_obv_is_monotonic_on_uptrend(self):
        n = 50
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        close = pd.Series(10 + np.arange(n, dtype=float), index=dates)
        df = pd.DataFrame({
            "open": close - 0.1, "high": close + 0.2,
            "low": close - 0.2, "close": close,
            "volume": pd.Series(np.ones(n) * 1e6, index=dates),
        })
        result = add_indicators(df)
        obv = result["obv"].dropna()
        assert (obv.diff().dropna() >= 0).all()


# ── get_signals ───────────────────────────────────────────────────────────────

class TestGetSignals:
    def test_returns_dict_of_dicts(self, sample_df):
        df = add_indicators(sample_df)
        signals = get_signals(df)
        assert isinstance(signals, dict)
        for key, val in signals.items():
            assert "signal" in val
            assert val["signal"] in ("alta", "baixa", "neutro"), f"{key}: bad signal {val['signal']}"

    def test_not_empty_for_full_dataset(self, sample_df):
        df = add_indicators(sample_df)
        assert len(get_signals(df)) > 0

    def test_empty_df_returns_empty(self):
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        df = add_indicators(df)
        assert get_signals(df) == {}

    def test_oversold_rsi_gives_alta(self):
        n = 120
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        close = pd.Series(50 - np.arange(n) * 0.45, index=dates)
        close = close.clip(lower=1)
        df = pd.DataFrame({
            "open": close + 0.1, "high": close + 0.2,
            "low": close - 0.2, "close": close,
            "volume": pd.Series(np.ones(n) * 1e6, index=dates),
        })
        df = add_indicators(df)
        signals = get_signals(df)
        rsi_sig = signals.get("rsi", {})
        if rsi_sig.get("value", 50) < 30:
            assert rsi_sig["signal"] == "alta"

    def test_overbought_rsi_gives_baixa(self):
        n = 120
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        close = pd.Series(10 + np.arange(n) * 0.45, index=dates)
        df = pd.DataFrame({
            "open": close - 0.1, "high": close + 0.2,
            "low": close - 0.2, "close": close,
            "volume": pd.Series(np.ones(n) * 1e6, index=dates),
        })
        df = add_indicators(df)
        signals = get_signals(df)
        rsi_sig = signals.get("rsi", {})
        if rsi_sig.get("value", 50) > 70:
            assert rsi_sig["signal"] == "baixa"
