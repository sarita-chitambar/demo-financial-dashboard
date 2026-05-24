from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class SearchResult:
    ticker: str
    name: str
    exchange: str = ""


class YFinanceProvider:
    def history(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        frame = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)
        if frame.empty:
            return frame

        frame = frame.reset_index()
        if "Date" in frame.columns:
            frame["Date"] = pd.to_datetime(frame["Date"]).dt.date
        return frame

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        try:
            results = yf.Search(query, max_results=limit).quotes
        except Exception:
            results = []

        parsed: list[SearchResult] = []
        for item in results[:limit]:
            symbol = item.get("symbol")
            if not symbol:
                continue
            name = item.get("shortname") or item.get("longname") or symbol
            exchange = item.get("exchange") or item.get("exchDisp") or ""
            parsed.append(SearchResult(ticker=symbol.upper(), name=name, exchange=exchange))

        if not parsed and query.isalpha():
            parsed.append(SearchResult(ticker=query.upper(), name=query.upper()))

        return parsed


def close_column(frame: pd.DataFrame) -> str:
    if "Adj Close" in frame.columns and not frame["Adj Close"].isna().all():
        return "Adj Close"
    return "Close"
