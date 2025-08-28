import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import polars as pl
import typer
import yfinance as yf
from typing_extensions import Annotated

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_raw_ohlcv(ticker, lookback, timezone):
    ohlcv_raw = yf.download(
        ticker,
        interval="1d",
        start=(
            # Multiplying lookback by 2 to ensure that the period contains enough trading days
            datetime.now(tz=ZoneInfo(timezone)) - timedelta(days=lookback * 2)
        ).strftime("%Y-%m-%d"),
    )
    if ohlcv_raw is None:
        raise ValueError("Ticker download from Yahoo Finance failed")
    ohlcv_raw.reset_index(inplace=True)
    ohlcv_raw.columns = [col[0] for col in ohlcv_raw.columns]
    return ohlcv_raw


def get_is_market_open(market_open, market_close, tz) -> bool:
    current_time = datetime.now(tz=ZoneInfo(tz)).strftime("%H:%M")
    is_market_open = market_open <= current_time <= market_close
    if is_market_open:
        logger.info("Market is currently open")
    else:
        logger.info("Market is currently closed")
    return is_market_open


def get_latest_price_and_sma(
    ohlcv_raw,
    lookback,
    trading_hours_open,
    trading_hours_close,
    timezone,
):
    ohlcv = pl.DataFrame(ohlcv_raw)
    ohlcv = ohlcv.sort("Date", descending=False)

    is_market_open = get_is_market_open(
        trading_hours_open,
        trading_hours_close,
        timezone,
    )

    if is_market_open:
        logger.info("Excluding the current trading day as the market is open")
        ohlcv = ohlcv.filter(
            pl.col("Date") < datetime.now(tz=ZoneInfo(timezone)).date(),
        )
    if ohlcv.height < lookback:
        raise ValueError(
            f"Not enough data to compute the {lookback}-day SMA",
        )

    ohlcv = ohlcv.with_columns(
        [pl.col("Close").rolling_mean(window_size=lookback).alias("SMA")]
    )
    latest_sma = ohlcv["SMA"][-1]
    if latest_sma is None:
        raise ValueError("Failed to compute the latest SMA")

    latest_close = ohlcv["Close"][-1]

    return latest_close, latest_sma


def get_state(
    latest_price,
    latest_price_sma,
    upward_tolerance,
    downard_tolerance,
    previous_state,
):
    if previous_state is None or previous_state == "neutral":
        if latest_price > latest_price_sma * (1 + upward_tolerance / 100):
            return "above"
        if latest_price < latest_price_sma * (1 - downard_tolerance / 100):
            return "below"
        else:
            return "neutral"
    elif previous_state == "above":
        if latest_price > latest_price_sma * (1 - downard_tolerance / 100):
            return "above"
        else:
            return "below"
    elif previous_state == "below":
        if latest_price > latest_price_sma * (1 + upward_tolerance / 100):
            return "above"
        else:
            return "below"
    else:
        raise ValueError(f"Invalid previous_state: {previous_state}")


def sma_crossover(
    ticker: Annotated[str, typer.Argument(help="Yahoo Finance ticker to probe")],
    lookback: Annotated[
        int,
        typer.Argument(help="Lookback window (in days) over which the SMA is computed"),
    ],
    trading_hours_open: Annotated[
        str,
        typer.Argument(
            help="Opening hour of the ticker's exchange (HH:MM, ISO 8601, local time)"
        ),
    ],
    trading_hours_close: Annotated[
        str,
        typer.Argument(
            help="Closing hour of the ticker's exchange (HH:MM, ISO 8601, local time)"
        ),
    ],
    timezone: Annotated[
        str,
        typer.Argument(
            help="Timezone of the ticker's exchange (e.g., America/New_York)"
        ),
    ],
    upward_tolerance: Annotated[
        float,
        typer.Option(
            help="Starting from a 'Null', 'neutral', or 'below' state, the price must exceed 100 + <upward_tolerance>% of the SMA to trigger a signal"
        ),
    ] = 0,
    downard_tolerance: Annotated[
        float,
        typer.Option(
            help="Starting from a 'Null', 'neutral', or 'above' state, the price must fall below 100 - <downard_tolerance>% of the SMA to trigger a signal"
        ),
    ] = 0,
    previous_state: Annotated[
        str | None,
        typer.Option(help="Last state: 'Null', 'neutral', 'below', or 'above'"),
    ] = None,
) -> None:
    """
    Monitor a ticker for crossovers of its close price and close price SMA
    """

    ohlcv_raw = get_raw_ohlcv(ticker, lookback, timezone)

    latest_price, latest_price_sma = get_latest_price_and_sma(
        ohlcv_raw,
        lookback,
        trading_hours_open,
        trading_hours_close,
        timezone,
    )
    logger.info(f"latest_price = {latest_price}, latest_price_sma = {latest_price_sma}")

    state = get_state(
        latest_price,
        latest_price_sma,
        upward_tolerance,
        downard_tolerance,
        previous_state,
    )

    did_signal_change = state != previous_state
    price_sma_diff = (latest_price / latest_price_sma - 1) * 100
    logger.info(
        f"state = {state}, did_signal_change = {did_signal_change}, price_sma_diff = {price_sma_diff}"
    )
