from __future__ import annotations

import argparse
import html
from io import BytesIO
import os
import smtplib
from dataclasses import dataclass
from datetime import date, datetime
from email.message import EmailMessage
from typing import Iterable

import pandas as pd
from matplotlib import pyplot as plt

from app.config import (
    WatchlistEntry,
    load_alert_history,
    load_settings,
    load_watchlist,
    save_alert_history,
)
from app.provider import YFinanceProvider, close_column


ALERT_THRESHOLD = 5.0
AVERAGE_WINDOW_DAYS = 30
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


@dataclass(frozen=True)
class StockSnapshot:
    ticker: str
    company: str
    sector: str
    latest_close: float | None
    average_close: float | None
    change_pct: float | None
    latest_date: date | None
    alert: bool
    direction: str = "info"
    reason: str = ""


def calculate_average_signal(
    frame: pd.DataFrame,
    ticker: str,
    company: str,
    sector: str,
    threshold: float = ALERT_THRESHOLD,
    window: int = AVERAGE_WINDOW_DAYS,
) -> StockSnapshot:
    if frame.empty:
        return StockSnapshot(ticker, company, sector, None, None, None, None, False, "info", "No price history found")

    column = close_column(frame)
    clean = frame.dropna(subset=[column]).copy()
    if "Date" not in clean.columns:
        clean = clean.reset_index().rename(columns={"index": "Date"})
    clean = clean.sort_values("Date")

    if len(clean) < window + 1:
        return StockSnapshot(
            ticker,
            company,
            sector,
            None,
            None,
            None,
            None,
            False,
            "info",
            f"Need at least {window + 1} trading days",
        )

    latest = clean.iloc[-1]
    window_frame = clean.iloc[-(window + 1) : -1]
    latest_close = float(latest[column])
    average_close = float(window_frame[column].mean())

    if average_close == 0:
        return StockSnapshot(
            ticker,
            company,
            sector,
            latest_close,
            average_close,
            None,
            _as_date(latest["Date"]),
            False,
            "info",
            "30-day average is zero",
        )

    change_pct = ((latest_close - average_close) / average_close) * 100
    alert = abs(change_pct) >= threshold
    direction = "rise" if change_pct >= threshold else "fall" if change_pct <= -threshold else "info"
    return StockSnapshot(
        ticker=ticker,
        company=company,
        sector=sector,
        latest_close=latest_close,
        average_close=average_close,
        change_pct=change_pct,
        latest_date=_as_date(latest["Date"]),
        alert=alert,
        direction=direction,
    )


def calculate_five_day_drop(
    frame: pd.DataFrame,
    ticker: str,
    company: str,
    sector: str,
    threshold: float = -5.0,
) -> StockSnapshot:
    return calculate_average_signal(frame, ticker, company, sector, abs(threshold), window=6)


def _as_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def collect_snapshots(
    entries: Iterable[WatchlistEntry],
    provider: YFinanceProvider | None = None,
) -> list[StockSnapshot]:
    provider = provider or YFinanceProvider()
    snapshots: list[StockSnapshot] = []

    for entry in entries:
        if not entry.enabled:
            continue
        try:
            frame = provider.history(entry.ticker, period="1y")
            snapshots.append(calculate_average_signal(frame, entry.ticker, entry.company, entry.sector))
        except Exception as exc:
            snapshots.append(
                StockSnapshot(entry.ticker, entry.company, entry.sector, None, None, None, None, False, "info", str(exc))
            )

    return snapshots


def undelivered_alerts(snapshots: Iterable[StockSnapshot], run_day: date | None = None) -> list[StockSnapshot]:
    run_day = run_day or date.today()
    history = load_alert_history()
    sent = set(history.get(run_day.isoformat(), []))
    return [snapshot for snapshot in snapshots if snapshot.alert and snapshot.ticker not in sent]


def mark_alerts_sent(alerts: Iterable[StockSnapshot], run_day: date | None = None) -> None:
    run_day = run_day or date.today()
    history = load_alert_history()
    day_key = run_day.isoformat()
    sent = set(history.get(day_key, []))
    sent.update(alert.ticker for alert in alerts)
    history[day_key] = sorted(sent)
    save_alert_history(history)


def report_subject(snapshots: list[StockSnapshot]) -> str:
    prefix = "ALERT: " if any(snapshot.alert for snapshot in snapshots) else ""
    return f"{prefix}Daily stock price report"


def render_report_email(snapshots: list[StockSnapshot], generated_at: datetime | None = None) -> tuple[str, str]:
    generated_at = generated_at or datetime.now()
    subject = report_subject(snapshots)
    lines = [
        "Daily price report for watched stocks:",
        "",
    ]
    for snapshot in snapshots:
        change = f"{snapshot.change_pct:.2f}%" if snapshot.change_pct is not None else "n/a"
        latest = f"${snapshot.latest_close:.2f}" if snapshot.latest_close is not None else "n/a"
        average = f"${snapshot.average_close:.2f}" if snapshot.average_close is not None else "n/a"
        status = alert_label(snapshot)
        if snapshot.reason:
            status = snapshot.reason
        lines.append(
            f"- {snapshot.ticker} ({snapshot.company}, {snapshot.sector}): "
            f"latest close {latest}, 30-business-day average {average}, change {change}, status {status}"
        )
    lines.extend(["", f"Generated at: {generated_at:%Y-%m-%d %H:%M:%S}"])
    return subject, "\n".join(lines)


def alert_label(snapshot: StockSnapshot) -> str:
    if snapshot.direction == "rise":
        return "RISE ALERT"
    if snapshot.direction == "fall":
        return "FALL ALERT"
    return "Info"


def render_report_html(snapshots: list[StockSnapshot], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now()
    rows = []
    for snapshot in snapshots:
        color = "#137333" if snapshot.direction == "rise" else "#c5221f" if snapshot.direction == "fall" else "#3c4043"
        latest = f"${snapshot.latest_close:.2f}" if snapshot.latest_close is not None else "n/a"
        average = f"${snapshot.average_close:.2f}" if snapshot.average_close is not None else "n/a"
        change = f"{snapshot.change_pct:.2f}%" if snapshot.change_pct is not None else "n/a"
        status = html.escape(snapshot.reason or alert_label(snapshot))
        rows.append(
            "<tr>"
            f"<td>{html.escape(snapshot.ticker)}</td>"
            f"<td>{html.escape(snapshot.company)}</td>"
            f"<td>{html.escape(snapshot.sector)}</td>"
            f"<td>{latest}</td>"
            f"<td>{average}</td>"
            f"<td style=\"color:{color};font-weight:700;\">{change}</td>"
            f"<td style=\"color:{color};font-weight:700;\">{status}</td>"
            f"<td><img src=\"cid:chart-{html.escape(snapshot.ticker)}\" alt=\"{html.escape(snapshot.ticker)} 1-year chart\" width=\"320\"></td>"
            "</tr>"
        )

    return f"""\
<!doctype html>
<html>
  <body style="font-family:Arial,sans-serif;color:#202124;">
    <h2>Daily stock price report</h2>
    <p>Latest close compared with the average close over the last 30 business days.</p>
    <table cellpadding="8" cellspacing="0" style="border-collapse:collapse;border:1px solid #dadce0;font-size:13px;">
      <thead>
        <tr style="background:#f1f3f4;">
          <th align="left">Ticker</th>
          <th align="left">Company</th>
          <th align="left">Sector</th>
          <th align="right">Latest Close</th>
          <th align="right">30-Day Avg</th>
          <th align="right">Change</th>
          <th align="left">Status</th>
          <th align="left">1-Year Plot</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
    <p style="color:#5f6368;font-size:12px;">Generated at: {generated_at:%Y-%m-%d %H:%M:%S}</p>
  </body>
</html>
"""


def render_email(snapshots: list[StockSnapshot], generated_at: datetime | None = None) -> tuple[str, str]:
    return render_report_email(snapshots, generated_at)


def chart_png(frame: pd.DataFrame, ticker: str) -> bytes:
    column = close_column(frame)
    clean = frame.dropna(subset=[column]).copy()
    fig, ax = plt.subplots(figsize=(5.2, 2.6), dpi=120)
    if not clean.empty:
        ax.plot(pd.to_datetime(clean["Date"]), clean[column], color="#1a73e8", linewidth=1.8)
    ax.set_title(f"{ticker} 1-year performance", fontsize=10)
    ax.set_xlabel("")
    ax.set_ylabel("Price", fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.tick_params(axis="x", labelrotation=25, labelsize=7)
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    output = BytesIO()
    fig.savefig(output, format="png")
    plt.close(fig)
    return output.getvalue()


def build_chart_images(
    snapshots: list[StockSnapshot],
    provider: YFinanceProvider | None = None,
) -> dict[str, bytes]:
    provider = provider or YFinanceProvider()
    images: dict[str, bytes] = {}
    for snapshot in snapshots:
        try:
            history = provider.history(snapshot.ticker, period="1y")
            images[snapshot.ticker] = chart_png(history, snapshot.ticker)
        except Exception:
            images[snapshot.ticker] = chart_png(pd.DataFrame(columns=["Date", "Close"]), snapshot.ticker)
    return images


def send_email(recipients: list[str], subject: str, body: str, html_body: str | None = None, images: dict[str, bytes] | None = None) -> None:
    load_env_file()
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing SMTP environment variables: {', '.join(missing)}")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = ", ".join(recipients)
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
        html_part = message.get_payload()[-1]
        for ticker, image in (images or {}).items():
            html_part.add_related(image, maintype="image", subtype="png", cid=f"<chart-{ticker}>")

    host = os.environ["SMTP_HOST"]
    port = int(os.environ["SMTP_PORT"])
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]

    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes"}
    smtp_client = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP

    with smtp_client(host, port) as smtp:
        if not use_ssl:
            smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(message)


def load_env_file(path: str = ENV_PATH) -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            os.environ.setdefault(key, value)


def run_once(recipients: list[str], dry_run: bool = False) -> list[StockSnapshot]:
    recipients = recipients or load_settings().get("email_recipients", [])
    snapshots = collect_snapshots(load_watchlist())
    alerts = undelivered_alerts(snapshots)
    subject, body = render_report_email(snapshots)
    html_body = render_report_html(snapshots)
    print(subject)
    print(body)

    if not dry_run:
        if not recipients:
            raise RuntimeError("At least one recipient email is required unless --dry-run is used.")
        send_email(recipients, subject, body, html_body, build_chart_images(snapshots))
        if alerts:
            mark_alerts_sent(alerts)

    return snapshots


def main() -> None:
    parser = argparse.ArgumentParser(description="Run stock price report checks.")
    parser.add_argument("command", choices=["run-once"], help="Run the stock price report once")
    parser.add_argument("--recipient", action="append", default=[], help="Recipient email address. Repeat as needed.")
    parser.add_argument("--dry-run", action="store_true", help="Print the report email without sending it.")
    args = parser.parse_args()

    if args.command == "run-once":
        run_once(args.recipient, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
