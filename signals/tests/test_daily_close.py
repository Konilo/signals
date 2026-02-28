from unittest.mock import patch

import pandas as pd
import pytest

from signals.probes.daily_close.run import (
    daily_close,
    get_close_data,
)


class TestGetCloseData:
    """Test cases for the get_close_data function."""

    @patch("signals.probes.daily_close.run.yf.download")
    def test_success(self, mock_download):
        """Test successful retrieval returns (prev_close, latest_close, date)."""
        mock_data = pd.DataFrame(
            {
                ("Close", "DCAM.PA"): [45.20, 45.80],
                ("Volume", "DCAM.PA"): [100000, 110000],
            }
        )
        mock_data.index = pd.to_datetime(["2024-01-09", "2024-01-10"])
        mock_data.index.name = "Date"
        mock_download.return_value = mock_data

        prev_close, latest_close, latest_date = get_close_data("DCAM.PA")

        assert prev_close == pytest.approx(45.20)
        assert latest_close == pytest.approx(45.80)
        assert latest_date == "2024-01-10"

    @patch("signals.probes.daily_close.run.yf.download")
    def test_download_returns_none_raises(self, mock_download):
        """Test that a None return from yfinance raises ValueError."""
        mock_download.return_value = None

        with pytest.raises(ValueError, match="Insufficient data for DCAM.PA"):
            get_close_data("DCAM.PA")

    @patch("signals.probes.daily_close.run.yf.download")
    def test_fewer_than_two_rows_raises(self, mock_download):
        """Test that fewer than 2 rows raises ValueError."""
        mock_data = pd.DataFrame(
            {
                ("Close", "DCAM.PA"): [45.20],
                ("Volume", "DCAM.PA"): [100000],
            }
        )
        mock_data.index = pd.to_datetime(["2024-01-10"])
        mock_data.index.name = "Date"
        mock_download.return_value = mock_data

        with pytest.raises(ValueError, match="Insufficient data for DCAM.PA"):
            get_close_data("DCAM.PA")


class TestDailyCloseIntegration:
    """Integration tests for the main daily_close function."""

    @patch("signals.probes.daily_close.run.send_message")
    @patch("signals.probes.daily_close.run.os.getenv")
    @patch("signals.probes.daily_close.run.get_close_data")
    def test_sends_correctly_formatted_message(
        self, mock_get_close, mock_getenv, mock_send
    ):
        """Test that a single ticker produces a correctly formatted Telegram message."""
        mock_getenv.side_effect = lambda key: {
            "TELEGRAM_CHAT_ID": "test_chat_id",
            "TELEGRAM_BOT_TOKEN": "test_token",
        }.get(key)
        mock_get_close.return_value = (45.20, 45.80, "2024-01-10")

        daily_close(tickers=["DCAM.PA"])

        mock_send.assert_called_once()
        message = mock_send.call_args.kwargs["message"]
        assert "2024-01-10" in message
        assert "DCAM.PA" in message
        assert "45.20" in message
        assert "45.80" in message
        assert "+1.33%" in message

    @patch("signals.probes.daily_close.run.send_message")
    @patch("signals.probes.daily_close.run.os.getenv")
    @patch("signals.probes.daily_close.run.get_close_data")
    def test_failed_ticker_appears_as_error_line(
        self, mock_get_close, mock_getenv, mock_send
    ):
        """Test that a failing ticker is included as an error line without aborting."""
        mock_getenv.side_effect = lambda key: {
            "TELEGRAM_CHAT_ID": "test_chat_id",
            "TELEGRAM_BOT_TOKEN": "test_token",
        }.get(key)
        mock_get_close.side_effect = [
            (45.20, 45.80, "2024-01-10"),
            ValueError("Insufficient data for BAD"),
        ]

        daily_close(tickers=["DCAM.PA", "BAD"])

        mock_send.assert_called_once()
        message = mock_send.call_args.kwargs["message"]
        assert "DCAM.PA" in message
        assert "BAD" in message
        assert "error" in message

    @patch("signals.probes.daily_close.run.send_message")
    @patch("signals.probes.daily_close.run.os.getenv")
    @patch("signals.probes.daily_close.run.get_close_data")
    def test_missing_chat_id_raises(self, mock_get_close, mock_getenv, mock_send):
        """Test that a missing TELEGRAM_CHAT_ID env var raises ValueError."""
        mock_getenv.return_value = None
        mock_get_close.return_value = (45.20, 45.80, "2024-01-10")

        with pytest.raises(ValueError, match="Missing TELEGRAM_CHAT_ID env var"):
            daily_close(tickers=["DCAM.PA"])
