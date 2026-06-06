import numpy as np
import pandas as pd


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bollinger_bands(
    close: pd.Series, period: int = 20, std_mult: float = 2.0
) -> tuple:
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + std_mult * std
    lower = sma - std_mult * std
    return upper, sma, lower


def _atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    tr = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Adds RSI, MACD, Bollinger Bands, SMA, EMA, ATR and OBV to an OHLCV DataFrame.

    Expects lowercase columns: open, high, low, close, volume.
    Returns a new DataFrame (original is not modified).
    """
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    df["rsi"] = _rsi(close)

    df["macd"], df["macd_signal"], df["macd_hist"] = _macd(close)

    df["bb_upper"], df["bb_mid"], df["bb_lower"] = _bollinger_bands(close)
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]
    df["bb_pct"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    df["sma_20"] = close.rolling(20).mean()
    df["sma_50"] = close.rolling(50).mean()
    df["sma_200"] = close.rolling(200).mean()

    df["ema_9"] = close.ewm(span=9, adjust=False).mean()
    df["ema_21"] = close.ewm(span=21, adjust=False).mean()

    df["atr"] = _atr(high, low, close)
    df["obv"] = _obv(close, volume)

    return df


def get_signals(df: pd.DataFrame) -> dict:
    """Interprets the last bar's indicators into directional signals.

    Returns a dict mapping indicator name → {signal, reason, value?}.
    signal is one of: 'alta', 'baixa', 'neutro'.
    """
    if len(df) < 2:
        return {}

    last = df.iloc[-1]
    prev = df.iloc[-2]
    signals: dict = {}

    # RSI
    rsi = last.get("rsi")
    if pd.notna(rsi):
        if rsi < 30:
            sig, reason = "alta", "Sobrevendido (RSI < 30)"
        elif rsi > 70:
            sig, reason = "baixa", "Sobrecomprado (RSI > 70)"
        else:
            sig, reason = "neutro", f"RSI neutro em {rsi:.1f}"
        signals["rsi"] = {"value": round(float(rsi), 2), "signal": sig, "reason": reason}

    # MACD
    macd_hist = last.get("macd_hist")
    prev_hist = prev.get("macd_hist")
    macd_val = last.get("macd")
    if pd.notna(macd_hist) and pd.notna(macd_val):
        growing = pd.notna(prev_hist) and macd_hist > prev_hist
        shrinking = pd.notna(prev_hist) and macd_hist < prev_hist
        if macd_hist > 0 and growing:
            sig, reason = "alta", "Histograma MACD positivo e crescendo"
        elif macd_hist < 0 and shrinking:
            sig, reason = "baixa", "Histograma MACD negativo e caindo"
        elif macd_hist > 0:
            sig, reason = "neutro", "MACD positivo mas perdendo força"
        elif macd_hist < 0:
            sig, reason = "neutro", "MACD negativo mas reduzindo"
        else:
            sig, reason = "neutro", "MACD sem direção definida"
        signals["macd"] = {"value": round(float(macd_val), 4), "signal": sig, "reason": reason}

    # Bollinger Bands
    bb_pct = last.get("bb_pct")
    if pd.notna(bb_pct):
        if bb_pct < 0.2:
            sig, reason = "alta", "Preço próximo à banda inferior (possível suporte)"
        elif bb_pct > 0.8:
            sig, reason = "baixa", "Preço próximo à banda superior (possível resistência)"
        else:
            sig, reason = "neutro", f"Preço dentro das bandas ({bb_pct:.0%})"
        signals["bollinger"] = {"value": round(float(bb_pct), 4), "signal": sig, "reason": reason}

    # Moving averages trend
    close_val = last.get("close")
    sma_20 = last.get("sma_20")
    sma_50 = last.get("sma_50")
    if pd.notna(close_val) and pd.notna(sma_20) and pd.notna(sma_50):
        if close_val > sma_20 > sma_50:
            sig, reason = "alta", "Preço > SMA20 > SMA50 — tendência de alta"
        elif close_val < sma_20 < sma_50:
            sig, reason = "baixa", "Preço < SMA20 < SMA50 — tendência de baixa"
        elif close_val > sma_20:
            sig, reason = "neutro", "Preço acima da SMA20 mas médias sem alinhamento"
        else:
            sig, reason = "neutro", "Médias sem alinhamento claro"
        signals["medias_moveis"] = {"signal": sig, "reason": reason}

    # EMA crossover (9 x 21)
    ema_9 = last.get("ema_9")
    ema_21 = last.get("ema_21")
    prev_ema_9 = prev.get("ema_9")
    prev_ema_21 = prev.get("ema_21")
    if pd.notna(ema_9) and pd.notna(ema_21) and pd.notna(prev_ema_9) and pd.notna(prev_ema_21):
        golden = ema_9 > ema_21 and prev_ema_9 <= prev_ema_21
        death = ema_9 < ema_21 and prev_ema_9 >= prev_ema_21
        if golden:
            sig, reason = "alta", "Golden Cross EMA9/EMA21 recente"
        elif death:
            sig, reason = "baixa", "Death Cross EMA9/EMA21 recente"
        elif ema_9 > ema_21:
            sig, reason = "alta", "EMA9 acima da EMA21"
        else:
            sig, reason = "baixa", "EMA9 abaixo da EMA21"
        signals["ema_cruzamento"] = {"signal": sig, "reason": reason}

    # Volatility (ATR%)
    atr = last.get("atr")
    if pd.notna(atr) and pd.notna(close_val) and close_val > 0:
        atr_pct = (atr / close_val) * 100
        signals["volatilidade"] = {
            "value": round(float(atr_pct), 2),
            "signal": "neutro",
            "reason": f"ATR representa {atr_pct:.2f}% do preço atual",
        }

    return signals
