from unittest.mock import MagicMock, patch

import pytest

from signals.probes.strava_to_gcal.run import (
    create_gcal_event,
    format_description,
    get_new_runs,
    refresh_strava_token,
    strava_to_gcal,
)

SAMPLE_RUN = {
    "id": 17532107224,
    "name": "Afternoon Run",
    "sport_type": "Run",
    "distance": 7428.3,
    "moving_time": 2011,
    "elapsed_time": 2050,
    "start_date_local": "2026-02-26T17:28:19Z",
    "timezone": "(GMT+01:00) Europe/Paris",
}

SAMPLE_ACTIVITIES = [
    SAMPLE_RUN,
    {**SAMPLE_RUN, "id": 100, "sport_type": "Ride"},  # non-run, should be filtered out
    {**SAMPLE_RUN, "id": 17507357013},  # older run, below last_activity_id threshold
    {**SAMPLE_RUN, "id": 17532107225},  # newer run, should be included
]


class TestFormatDescription:
    def test_matches_expected_output(self):
        """Verify format against a real activity (7.43 km, 4:30/km, 33m 31s)."""
        result = format_description(distance_m=7428.3, moving_time_s=2011)
        assert "7.43 km" in result
        assert "4:30 /km" in result
        assert "33m 31s" in result

    def test_structure(self):
        result = format_description(distance_m=5000.0, moving_time_s=1500)
        assert "Distance" in result
        assert "Pace" in result
        assert "Time" in result

    def test_zero_seconds_in_pace(self):
        """Pace seconds component should be zero-padded."""
        # 10 km in 50 min = 5:00/km exactly
        result = format_description(distance_m=10000.0, moving_time_s=3000)
        assert "5:00 /km" in result


class TestRefreshStravaToken:
    @patch("signals.probes.strava_to_gcal.run.requests.post")
    def test_returns_access_and_refresh_token(self, mock_post):
        mock_post.return_value.json.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
        }
        mock_post.return_value.raise_for_status = MagicMock()

        access_token, refresh_token = refresh_strava_token("id", "secret", "old_refresh")

        assert access_token == "new_access"
        assert refresh_token == "new_refresh"

    @patch("signals.probes.strava_to_gcal.run.requests.post")
    def test_raises_on_http_error(self, mock_post):
        from requests.exceptions import HTTPError
        mock_post.return_value.raise_for_status.side_effect = HTTPError("401")

        with pytest.raises(HTTPError):
            refresh_strava_token("id", "secret", "bad_token")


class TestGetNewRuns:
    @patch("signals.probes.strava_to_gcal.run.requests.get")
    def test_filters_non_runs_and_old_activities(self, mock_get):
        mock_get.return_value.json.return_value = SAMPLE_ACTIVITIES
        mock_get.return_value.raise_for_status = MagicMock()

        result = get_new_runs("access_token", last_activity_id=17507357013)

        ids = [r["id"] for r in result]
        assert 17532107224 in ids   # new run — included
        assert 17532107225 in ids   # new run — included
        assert 100 not in ids       # Ride — excluded
        assert 17507357013 not in ids  # at or below threshold — excluded

    @patch("signals.probes.strava_to_gcal.run.requests.get")
    def test_returns_sorted_oldest_first(self, mock_get):
        mock_get.return_value.json.return_value = SAMPLE_ACTIVITIES
        mock_get.return_value.raise_for_status = MagicMock()

        result = get_new_runs("access_token", last_activity_id=0)
        run_ids = [r["id"] for r in result if r["sport_type"] == "Run"]
        assert run_ids == sorted(run_ids)


class TestCreateGcalEvent:
    def test_event_structure(self):
        mock_service = MagicMock()

        create_gcal_event(mock_service, "calendar_id", SAMPLE_RUN)

        call_kwargs = mock_service.events.return_value.insert.call_args.kwargs
        event = call_kwargs["body"]
        assert event["summary"] == "Endu"
        assert "7.43 km" in event["description"]
        assert event["start"]["dateTime"] == "2026-02-26T17:28:19"
        assert event["start"]["timeZone"] == "Europe/Paris"
        # end = start + elapsed_time (2050s = 34m 10s)
        assert event["end"]["dateTime"] == "2026-02-26T18:02:29"
        assert event["end"]["timeZone"] == "Europe/Paris"
        assert call_kwargs["calendarId"] == "calendar_id"


class TestStravaToGcalIntegration:
    @patch("signals.probes.strava_to_gcal.run.build_gcal_service")
    @patch("signals.probes.strava_to_gcal.run.get_new_runs")
    @patch("signals.probes.strava_to_gcal.run.refresh_strava_token")
    @patch("signals.probes.strava_to_gcal.run.os.getenv")
    def test_creates_events_and_prints_outputs(
        self, mock_getenv, mock_refresh, mock_get_runs, mock_build_gcal, capsys
    ):
        mock_getenv.side_effect = lambda k: {
            "STRAVA_CLIENT_ID": "id",
            "STRAVA_CLIENT_SECRET": "secret",
            "STRAVA_REFRESH_TOKEN": "old_refresh",
            "GOOGLE_SERVICE_ACCOUNT_JSON": '{"type": "service_account"}',
        }.get(k)
        mock_refresh.return_value = ("access_token", "new_refresh")
        mock_get_runs.return_value = [SAMPLE_RUN]

        strava_to_gcal(last_activity_id=0, calendar_id="cal_id")

        mock_build_gcal.return_value.events.return_value.insert.return_value.execute.assert_called_once()
        out = capsys.readouterr().out.splitlines()
        assert out[0] == "new_refresh"
        assert out[1] == str(SAMPLE_RUN["id"])

    @patch("signals.probes.strava_to_gcal.run.build_gcal_service")
    @patch("signals.probes.strava_to_gcal.run.get_new_runs")
    @patch("signals.probes.strava_to_gcal.run.refresh_strava_token")
    @patch("signals.probes.strava_to_gcal.run.os.getenv")
    def test_no_new_runs_preserves_last_activity_id(
        self, mock_getenv, mock_refresh, mock_get_runs, mock_build_gcal, capsys
    ):
        mock_getenv.side_effect = lambda k: {
            "STRAVA_CLIENT_ID": "id",
            "STRAVA_CLIENT_SECRET": "secret",
            "STRAVA_REFRESH_TOKEN": "old_refresh",
            "GOOGLE_SERVICE_ACCOUNT_JSON": '{"type": "service_account"}',
        }.get(k)
        mock_refresh.return_value = ("access_token", "new_refresh")
        mock_get_runs.return_value = []

        strava_to_gcal(last_activity_id=12345, calendar_id="cal_id")

        mock_build_gcal.assert_not_called()
        out = capsys.readouterr().out.splitlines()
        assert out[0] == "new_refresh"
        assert out[1] == "12345"

    @patch("signals.probes.strava_to_gcal.run.os.getenv")
    def test_missing_env_vars_raises(self, mock_getenv):
        mock_getenv.return_value = None

        with pytest.raises(ValueError, match="Missing one or more required environment variables"):
            strava_to_gcal(last_activity_id=0, calendar_id="cal_id")
