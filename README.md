# Stock Drop Dashboard

A local Streamlit dashboard and daily email report system for watching large-cap tech and healthcare stocks. It emails the latest price for each watched stock, flags any stock that rises or falls by 5% or more versus its average close over the prior 30 business days, and shows a 1-year performance chart for each company.

Default watchlist:

- Tech: `NVDA`, `AAPL`, `MSFT`, `GOOGL`, `AMZN`
- Healthcare: `LLY`, `JNJ`, `ABBV`, `UNH`, `MRK`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run The Dashboard

```bash
streamlit run app/dashboard.py
```

The dashboard lets you filter by sector, review 30-business-day average performance, inspect 1-year charts, search for more tickers, and add custom stocks to the watchlist.

## Email Reports

Daily reports use free SMTP. For Gmail, enable 2-step verification and create an App Password, then use that password as `SMTP_PASSWORD`.

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USERNAME=your-email@gmail.com
export SMTP_PASSWORD=your-app-password
export SMTP_FROM=your-email@gmail.com
```

For SSL-based SMTP providers that use port 465, also set:

```bash
export SMTP_USE_SSL=true
```

Email recipients can be saved in the dashboard sidebar or passed on the command line.

For scheduled cron runs, put SMTP settings in a local `.env` file at the project root. This file is ignored by git:

```bash
cp .env.example .env
```

Then edit `.env` with your Gmail address and Google App Password. The alert CLI loads `.env` automatically before sending email.

Preview the report without sending email:

```bash
python -m app.alerts run-once --dry-run
```

Send the report:

```bash
python -m app.alerts run-once --recipient recipient@example.com
```

## Scheduling

For a weekday morning cron job, run `crontab -e` and add a line like this, adjusting paths and recipient:

```cron
30 6 * * 1-5 cd /path/to/demo-financial-dashboard && /path/to/demo-financial-dashboard/.venv/bin/python -m app.alerts run-once --recipient recipient@example.com
```

The email subject is `Daily stock price report` when no stock crosses the threshold and `ALERT: Daily stock price report` when any watched stock rises or falls by at least 5% versus its prior 30-business-day average. The HTML body lists the current price, 30-day average, percentage change, colored rise/fall status, and inline 1-year plot for each watched company. The watchlist is stored locally in `data/watchlist.json`; SMTP secrets are read from environment variables or a local `.env` file that is ignored by git.

## Private Local Files

Do not commit real credentials or local runtime data. The repo intentionally ignores:

- `.env` and other local env files
- `data/*.json`, including saved recipients, watchlists, and alert history
- log files and private key files

Use `.env.example` only as a placeholder template.

## Tests

```bash
pytest
```

## Notes

This v1 uses `yfinance`, which is convenient and free for prototypes but unofficial. The stock provider is isolated in `app/provider.py` so another API provider can be added later.
