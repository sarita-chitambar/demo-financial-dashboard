from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.alerts import collect_snapshots, render_report_email
from app.config import (
    WatchlistEntry,
    add_or_update_stock,
    load_settings,
    load_watchlist,
    remove_stock,
    save_settings,
)
from app.provider import YFinanceProvider, close_column


st.set_page_config(page_title="Stock Price Alerts", layout="wide")


@st.cache_data(ttl=900)
def cached_history(ticker: str, period: str) -> pd.DataFrame:
    return YFinanceProvider().history(ticker, period=period)


@st.cache_data(ttl=1800)
def cached_search(query: str) -> list[dict[str, str]]:
    return [result.__dict__ for result in YFinanceProvider().search(query)]


def snapshot_table(entries: list[WatchlistEntry]) -> pd.DataFrame:
    snapshots = collect_snapshots(entries)
    rows = []
    for item in snapshots:
        status = item.reason or ("Up Alert" if item.direction == "rise" else "Down Alert" if item.direction == "fall" else "OK")
        rows.append(
            {
                "Ticker": item.ticker,
                "Company": item.company,
                "Sector": item.sector,
                "Latest Close": item.latest_close,
                "30-Day Avg": item.average_close,
                "Vs 30-Day Avg %": item.change_pct,
                "Alert": "Yes" if item.alert else "No",
                "Latest Date": item.latest_date,
                "Status": status,
                "Direction": item.direction,
            }
        )
    return pd.DataFrame(rows)


def style_snapshot_table(table: pd.DataFrame):
    display = table.drop(columns=["Direction"], errors="ignore")

    def row_style(row: pd.Series) -> list[str]:
        direction = table.loc[row.name, "Direction"] if "Direction" in table.columns else "info"
        if direction == "rise":
            return [
                "color: #137333; font-weight: 700;" if column in {"Vs 30-Day Avg %", "Status", "Alert"} else ""
                for column in display.columns
            ]
        if direction == "fall":
            return [
                "color: #c5221f; font-weight: 700;" if column in {"Vs 30-Day Avg %", "Status", "Alert"} else ""
                for column in display.columns
            ]
        return ["" for _ in display.columns]

    return display.style.format(
        {
            "Latest Close": "${:.2f}",
            "30-Day Avg": "${:.2f}",
            "Vs 30-Day Avg %": "{:.2f}%",
        },
        na_rep="n/a",
    ).apply(row_style, axis=1)


def render_chart(entry: WatchlistEntry) -> None:
    frame = cached_history(entry.ticker, "1y")
    if frame.empty:
        st.warning(f"No chart data found for {entry.ticker}.")
        return

    column = close_column(frame)
    chart = px.line(frame, x="Date", y=column, title=f"{entry.ticker} 1-year performance")
    chart.update_layout(height=260, margin=dict(l=10, r=10, t=45, b=10), showlegend=False)
    st.plotly_chart(chart, use_container_width=True)


def main() -> None:
    st.title("Stock Price Alerts")

    entries = load_watchlist()
    sectors = ["All"] + sorted({entry.sector for entry in entries})

    with st.sidebar:
        st.header("Watchlist")
        selected_sector = st.selectbox("Sector", sectors)
        show_disabled = st.checkbox("Show disabled stocks", value=False)

        st.divider()
        st.subheader("Email recipients")
        settings = load_settings()
        recipient_text = st.text_area(
            "One email per line",
            value="\n".join(settings.get("email_recipients", [])),
            height=90,
        )
        if st.button("Save recipients"):
            recipients = [line.strip() for line in recipient_text.splitlines() if line.strip()]
            save_settings({"email_recipients": recipients})
            st.success("Recipients saved.")

        st.divider()
        st.subheader("Add stock")
        query = st.text_input("Search ticker or company")
        sector = st.text_input("Sector label", value="Custom")
        if query:
            results = cached_search(query)
            labels = [f"{item['ticker']} - {item['name']}" for item in results]
            choice = st.selectbox("Matches", labels) if labels else None
            if choice and st.button("Add selected stock", type="primary"):
                selected = results[labels.index(choice)]
                add_or_update_stock(
                    WatchlistEntry(
                        ticker=selected["ticker"],
                        company=selected["name"],
                        sector=sector or "Custom",
                        enabled=True,
                        default=False,
                    )
                )
                st.cache_data.clear()
                st.rerun()

        st.divider()
        removable = [entry for entry in entries if not entry.default]
        if removable:
            remove_choice = st.selectbox("Remove custom stock", [entry.ticker for entry in removable])
            if st.button("Remove"):
                remove_stock(remove_choice)
                st.cache_data.clear()
                st.rerun()

    filtered = [
        entry
        for entry in entries
        if (selected_sector == "All" or entry.sector == selected_sector) and (show_disabled or entry.enabled)
    ]

    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Current watchlist")
        table = snapshot_table(filtered)
        st.dataframe(style_snapshot_table(table), use_container_width=True, hide_index=True)

        if st.button("Generate email report now"):
            snapshots = collect_snapshots(filtered)
            subject, body = render_report_email(snapshots)
            st.success(subject)
            st.code(body)

    with right:
        st.subheader("1-year performance")
        for entry in filtered:
            render_chart(entry)


if __name__ == "__main__":
    main()
