"""
data.py
-------
Descarga de precios históricos vía yfinance y cálculo de estadísticas
(retornos anuales, volatilidad, correlaciones) para las carteras.
"""
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

PERIOD_LABELS = {
    "10 años": "10y",
    "15 años": "15y",
    "20 años": "20y",
    "30 años": "30y",
    "Máximo disponible": "max",
}


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_single_ticker(ticker: str, period: str) -> pd.Series | None:
    """Descarga el precio de cierre ajustado de un único ticker. Devuelve None si falla."""
    try:
        hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        if hist is None or hist.empty or "Close" not in hist.columns:
            return None
        s = hist["Close"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        s.name = ticker
        s = s[~s.index.duplicated(keep="last")]
        return s
    except Exception:
        return None


def fetch_prices(tickers: List[str], period: str) -> Tuple[pd.DataFrame, List[str]]:
    """
    Descarga precios para una lista de tickers.
    Devuelve (DataFrame de precios [fecha x ticker], lista de tickers que fallaron).
    """
    tickers = [t.strip().upper() for t in tickers if t and t.strip()]
    series_list = []
    failed = []
    for t in tickers:
        s = _fetch_single_ticker(t, period)
        if s is None or s.dropna().empty:
            failed.append(t)
        else:
            series_list.append(s)
    if not series_list:
        return pd.DataFrame(), failed
    prices = pd.concat(series_list, axis=1).sort_index()
    prices = prices.dropna(how="all")
    return prices, failed


def compute_annual_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte precios diarios en retornos anuales (año natural).
    Solo conserva años en los que TODOS los activos tienen dato, para preservar
    la estructura de correlación al hacer bootstrap por vector de año.
    """
    if prices.empty:
        return pd.DataFrame()
    yearly = prices.resample("YE").last()
    annual_returns = yearly.pct_change().dropna(how="any")
    return annual_returns


def portfolio_expected_stats(annual_returns: pd.DataFrame, weights: Dict[str, float]) -> Dict[str, float]:
    """Retorno y volatilidad esperados de la cartera (media-varianza, en base anual)."""
    tickers = [t for t in weights.keys() if t in annual_returns.columns]
    if not tickers or annual_returns.empty:
        return {"expected_return": float("nan"), "volatility": float("nan")}
    w = np.array([weights[t] for t in tickers])
    if w.sum() == 0:
        return {"expected_return": float("nan"), "volatility": float("nan")}
    w = w / w.sum()
    mean_vec = annual_returns[tickers].mean().values
    cov_mat = annual_returns[tickers].cov().values
    exp_ret = float(w @ mean_vec)
    vol = float(np.sqrt(w @ cov_mat @ w))
    return {"expected_return": exp_ret, "volatility": vol}


def correlation_matrix(annual_returns: pd.DataFrame, tickers: List[str]) -> pd.DataFrame:
    cols = [t for t in tickers if t in annual_returns.columns]
    if len(cols) < 2:
        return pd.DataFrame()
    return annual_returns[cols].corr()
