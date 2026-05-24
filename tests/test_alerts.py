from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.alerts import calculate_average_signal, render_report_email, render_report_html


def frame_from_closes(closes: list[float]) -> pd.DataFrame:
    start = date(2026, 1, 1)
    return pd.DataFrame(
        {
            "Date": [start + timedelta(days=index) for index in range(len(closes))],
            "Close": closes,
        }
    )


def test_exactly_five_percent_rise_alerts() -> None:
    snapshot = calculate_average_signal(frame_from_closes([100] * 30 + [105]), "TST", "Test Co", "Tech")

    assert snapshot.alert is True
    assert snapshot.direction == "rise"
    assert round(snapshot.change_pct, 2) == 5.0


def test_larger_than_five_percent_drop_alerts() -> None:
    snapshot = calculate_average_signal(frame_from_closes([100] * 30 + [90]), "TST", "Test Co", "Tech")

    assert snapshot.alert is True
    assert snapshot.direction == "fall"
    assert round(snapshot.change_pct, 2) == -10.0


def test_smaller_drop_does_not_alert() -> None:
    snapshot = calculate_average_signal(frame_from_closes([100] * 30 + [96]), "TST", "Test Co", "Tech")

    assert snapshot.alert is False
    assert snapshot.direction == "info"
    assert round(snapshot.change_pct, 2) == -4.0


def test_insufficient_history_does_not_alert() -> None:
    snapshot = calculate_average_signal(frame_from_closes([100, 95]), "TST", "Test Co", "Tech")

    assert snapshot.alert is False
    assert snapshot.reason == "Need at least 31 trading days"


def test_render_report_email_is_informational_and_includes_prices() -> None:
    snapshot = calculate_average_signal(frame_from_closes([100] * 30 + [90]), "TST", "Test Co", "Tech")

    subject, body = render_report_email([snapshot])

    assert subject == "ALERT: Daily stock price report"
    assert "TST" in body
    assert "$90.00" in body
    assert "-10.00%" in body


def test_render_report_html_colors_rise_and_fall() -> None:
    rise = calculate_average_signal(frame_from_closes([100] * 30 + [105]), "UP", "Up Co", "Tech")
    fall = calculate_average_signal(frame_from_closes([100] * 30 + [90]), "DOWN", "Down Co", "Tech")

    html = render_report_html([rise, fall])

    assert "#137333" in html
    assert "#c5221f" in html
    assert "cid:chart-UP" in html
    assert "cid:chart-DOWN" in html
