import logging
import os
from datetime import datetime, timedelta

import polars as pl
import typer
import yfinance as yf
from typing_extensions import Annotated
from utils.signal_utils import send_message

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_close_data(ticker: str) -> tuple[float, float, str]:
    raw = yf.download(
        ticker,
        interval="1d",
        start=(datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
    )
    if raw is None or len(raw) < 2:
        raise ValueError(f"Insufficient data for {ticker}")
    raw.reset_index(inplace=True)
    raw.columns = [col[0] for col in raw.columns]
    df = pl.from_pandas(raw).select(["Date", "Close"]).sort("Date")
    prev_close = df["Close"][-2]
    latest_close = df["Close"][-1]
    latest_date = str(df["Date"][-1])[:10]
    return prev_close, latest_close, latest_date


def daily_close(
    tickers: Annotated[
        list[str], typer.Argument(help="Yahoo Finance tickers to monitor")
    ],
) -> None:
    """
    Monitor a list of tickers for previous close, close, and daily return
    """
    date_str = None
    lines = []

    for ticker in tickers:
        try:
            prev_close, latest_close, date = get_close_data(ticker)
            if date_str is None:
                date_str = date
            daily_return = (latest_close - prev_close) / prev_close * 100
            sign = "+" if daily_return >= 0 else ""
            lines.append(
                f"{ticker}  {prev_close:.2f} → {latest_close:.2f}  {sign}{daily_return:.2f}%"
            )
            logger.info(
                f"{ticker}: prev={prev_close:.2f}, close={latest_close:.2f}, return={daily_return:.2f}%"
            )
        except Exception as e:
            logger.error(f"{ticker}: {e}")
            lines.append(f"{ticker}: error — {e}")

    header = f"📊 Daily close — {date_str or 'unknown date'}"
    message = header + "\n" + "\n".join(lines)

    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise ValueError("Missing TELEGRAM_CHAT_ID env var")
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_bot_token:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN env var")
    send_message(chat_id=chat_id, message=message, token=telegram_bot_token)
