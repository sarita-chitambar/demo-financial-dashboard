from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
ALERT_HISTORY_PATH = DATA_DIR / "alert_history.json"
SETTINGS_PATH = DATA_DIR / "settings.json"


DEFAULT_WATCHLIST = [
    {"ticker": "NVDA", "company": "NVIDIA Corporation", "sector": "Tech", "enabled": True, "default": True},
    {"ticker": "AAPL", "company": "Apple Inc.", "sector": "Tech", "enabled": True, "default": True},
    {"ticker": "MSFT", "company": "Microsoft Corporation", "sector": "Tech", "enabled": True, "default": True},
    {"ticker": "GOOGL", "company": "Alphabet Inc.", "sector": "Tech", "enabled": True, "default": True},
    {"ticker": "AMZN", "company": "Amazon.com, Inc.", "sector": "Tech", "enabled": True, "default": True},
    {"ticker": "LLY", "company": "Eli Lilly and Company", "sector": "Healthcare", "enabled": True, "default": True},
    {"ticker": "JNJ", "company": "Johnson & Johnson", "sector": "Healthcare", "enabled": True, "default": True},
    {"ticker": "ABBV", "company": "AbbVie Inc.", "sector": "Healthcare", "enabled": True, "default": True},
    {"ticker": "UNH", "company": "UnitedHealth Group Incorporated", "sector": "Healthcare", "enabled": True, "default": True},
    {"ticker": "MRK", "company": "Merck & Co., Inc.", "sector": "Healthcare", "enabled": True, "default": True},
]


@dataclass(frozen=True)
class WatchlistEntry:
    ticker: str
    company: str
    sector: str = "Custom"
    enabled: bool = True
    default: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WatchlistEntry":
        return cls(
            ticker=str(raw["ticker"]).upper().strip(),
            company=str(raw.get("company") or raw["ticker"]).strip(),
            sector=str(raw.get("sector") or "Custom").strip(),
            enabled=bool(raw.get("enabled", True)),
            default=bool(raw.get("default", False)),
        )


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_watchlist(path: Path = WATCHLIST_PATH) -> list[WatchlistEntry]:
    if not path.exists():
        save_watchlist([WatchlistEntry.from_dict(item) for item in DEFAULT_WATCHLIST], path)

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    stocks = data.get("stocks", data if isinstance(data, list) else [])
    return [WatchlistEntry.from_dict(item) for item in stocks]


def save_watchlist(entries: list[WatchlistEntry], path: Path = WATCHLIST_PATH) -> None:
    _ensure_data_dir()
    payload = {"stocks": [asdict(entry) for entry in entries]}
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def add_or_update_stock(entry: WatchlistEntry, path: Path = WATCHLIST_PATH) -> list[WatchlistEntry]:
    entries = load_watchlist(path)
    by_ticker = {item.ticker: item for item in entries}
    by_ticker[entry.ticker] = entry
    updated = list(by_ticker.values())
    save_watchlist(updated, path)
    return updated


def remove_stock(ticker: str, path: Path = WATCHLIST_PATH) -> list[WatchlistEntry]:
    normalized = ticker.upper().strip()
    entries = [entry for entry in load_watchlist(path) if entry.ticker != normalized]
    save_watchlist(entries, path)
    return entries


def load_alert_history(path: Path = ALERT_HISTORY_PATH) -> dict[str, list[str]]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    return {str(day): [str(ticker) for ticker in tickers] for day, tickers in data.items()}


def save_alert_history(history: dict[str, list[str]], path: Path = ALERT_HISTORY_PATH) -> None:
    _ensure_data_dir()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2, sort_keys=True)


def load_settings(path: Path = SETTINGS_PATH) -> dict[str, Any]:
    if not path.exists():
        settings = {"email_recipients": []}
        save_settings(settings, path)
        return settings

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    recipients = data.get("email_recipients", [])
    return {"email_recipients": [str(item).strip() for item in recipients if str(item).strip()]}


def save_settings(settings: dict[str, Any], path: Path = SETTINGS_PATH) -> None:
    _ensure_data_dir()
    recipients = settings.get("email_recipients", [])
    payload = {"email_recipients": [str(item).strip() for item in recipients if str(item).strip()]}
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
