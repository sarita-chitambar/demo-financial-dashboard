from __future__ import annotations

from app.config import (
    WatchlistEntry,
    add_or_update_stock,
    load_settings,
    load_watchlist,
    remove_stock,
    save_settings,
    save_watchlist,
)


def test_save_and_load_watchlist(tmp_path) -> None:
    path = tmp_path / "watchlist.json"
    save_watchlist([WatchlistEntry("NVDA", "NVIDIA Corporation", "Tech", True, True)], path)

    loaded = load_watchlist(path)

    assert loaded == [WatchlistEntry("NVDA", "NVIDIA Corporation", "Tech", True, True)]


def test_add_or_update_stock(tmp_path) -> None:
    path = tmp_path / "watchlist.json"
    save_watchlist([WatchlistEntry("AAPL", "Apple Inc.", "Tech", True, True)], path)

    add_or_update_stock(WatchlistEntry("AMZN", "Amazon.com, Inc.", "Tech"), path)

    tickers = {entry.ticker for entry in load_watchlist(path)}
    assert tickers == {"AAPL", "AMZN"}


def test_remove_stock(tmp_path) -> None:
    path = tmp_path / "watchlist.json"
    save_watchlist(
        [
            WatchlistEntry("AAPL", "Apple Inc.", "Tech", True, True),
            WatchlistEntry("AMZN", "Amazon.com, Inc.", "Tech"),
        ],
        path,
    )

    remove_stock("AMZN", path)

    assert [entry.ticker for entry in load_watchlist(path)] == ["AAPL"]


def test_save_and_load_settings(tmp_path) -> None:
    path = tmp_path / "settings.json"
    save_settings({"email_recipients": ["first@example.com", " ", "second@example.com"]}, path)

    assert load_settings(path) == {"email_recipients": ["first@example.com", "second@example.com"]}
