import os
from typing import Optional

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

BRAPI_TOKEN: str = os.getenv("BRAPI_TOKEN", "")
BRAPI_BASE_URL = "https://brapi.dev/api"


def _normalize_ticker(ticker: str) -> tuple:
    """Returns (yfinance_ticker, brapi_ticker)."""
    ticker = ticker.upper().strip()
    yf_ticker = ticker if ticker.endswith(".SA") else f"{ticker}.SA"
    brapi_ticker = ticker.replace(".SA", "")
    return yf_ticker, brapi_ticker


def fetch_ohlcv(ticker: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    """Fetches OHLCV historical data via yfinance.

    Args:
        ticker: Brazilian stock ticker (e.g., 'PETR4' or 'PETR4.SA')
        period: Data period ('1mo', '3mo', '6mo', '1y', '2y', '5y')
        interval: Bar interval ('1d', '1wk', '1mo')

    Returns:
        DataFrame with columns: open, high, low, close, volume
    """
    yf_ticker, _ = _normalize_ticker(ticker)
    t = yf.Ticker(yf_ticker)
    df = t.history(period=period, interval=interval, auto_adjust=True)
    if df.empty:
        raise ValueError(f"Nenhum dado encontrado para {ticker}. Verifique o ticker.")
    df.columns = [c.lower() for c in df.columns]
    keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    df = df[keep].copy()
    df.index.name = "Date"
    return df


def fetch_quote(ticker: str) -> dict:
    """Fetches the current quote with Brapi as primary and yfinance as fallback.

    Returns dict with keys: ticker, price, change, change_pct, volume, market_cap, name, source
    """
    yf_ticker, brapi_ticker = _normalize_ticker(ticker)

    # Try Brapi first
    try:
        params = {"token": BRAPI_TOKEN} if BRAPI_TOKEN else {}
        resp = requests.get(
            f"{BRAPI_BASE_URL}/quote/{brapi_ticker}", params=params, timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                r = results[0]
                return {
                    "ticker": brapi_ticker,
                    "price": r.get("regularMarketPrice"),
                    "change": r.get("regularMarketChange"),
                    "change_pct": r.get("regularMarketChangePercent"),
                    "volume": r.get("regularMarketVolume"),
                    "market_cap": r.get("marketCap"),
                    "name": r.get("longName") or brapi_ticker,
                    "source": "brapi",
                }
    except Exception:
        pass

    # Fallback to yfinance
    try:
        t = yf.Ticker(yf_ticker)
        hist = t.history(period="2d", auto_adjust=True)
        if hist.empty:
            raise ValueError("Histórico vazio")
        hist.columns = [c.lower() for c in hist.columns]
        price = float(hist["close"].iloc[-1])
        prev = float(hist["close"].iloc[-2]) if len(hist) >= 2 else price
        change = price - prev
        change_pct = (change / prev * 100) if prev else 0.0
        volume = int(hist["volume"].iloc[-1]) if "volume" in hist.columns else None
        return {
            "ticker": brapi_ticker,
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "volume": volume,
            "market_cap": None,
            "name": brapi_ticker,
            "source": "yfinance",
        }
    except Exception as exc:
        raise RuntimeError(f"Falha ao buscar cotação para {ticker}: {exc}") from exc
