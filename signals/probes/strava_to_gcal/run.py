import json
import logging
import os
from datetime import datetime, timedelta

import requests
import typer
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from typing_extensions import Annotated

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
GCAL_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def refresh_strava_token(
    client_id: str, client_secret: str, refresh_token: str
) -> tuple[str, str]:
    """Exchange a refresh token for a new access token.

    Returns (access_token, refresh_token). The refresh token may be unchanged
    or rotated; callers should always persist the returned value.
    """
    response = requests.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    response.raise_for_status()
    data = response.json()
    return data["access_token"], data["refresh_token"]


def get_new_runs(access_token: str, last_activity_id: int) -> list[dict]:
    """Return Strava runs recorded after last_activity_id, oldest first."""
    response = requests.get(
        STRAVA_ACTIVITIES_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params={"per_page": 30},
    )
    response.raise_for_status()
    activities = response.json()
    runs = [
        a
        for a in activities
        if a["sport_type"] == "Run" and a["id"] > last_activity_id
    ]
    return sorted(runs, key=lambda a: a["id"])


def format_description(distance_m: float, moving_time_s: int) -> str:
    """Format run metrics to match the user's existing manual GCal entry style."""
    distance_km = distance_m / 1000
    pace_s_per_km = moving_time_s / distance_km
    pace_min = int(pace_s_per_km // 60)
    pace_sec = int(pace_s_per_km % 60)
    total_min = moving_time_s // 60
    remaining_sec = moving_time_s % 60
    return (
        f"Distance\n    {distance_km:.2f} km\n"
        f"Pace\n    {pace_min}:{pace_sec:02d} /km\n"
        f"Time\n    {total_min}m {remaining_sec:02d}s"
    )


def build_gcal_service(service_account_json: str):
    """Build an authenticated Google Calendar API service."""
    credentials = Credentials.from_service_account_info(
        json.loads(service_account_json), scopes=GCAL_SCOPES
    )
    return build("calendar", "v3", credentials=credentials)


def create_gcal_event(service, calendar_id: str, activity: dict) -> None:
    """Create a Google Calendar event for a Strava run activity."""
    # start_date_local carries the Z suffix but represents local time — treat as naive
    start_dt = datetime.fromisoformat(activity["start_date_local"].replace("Z", ""))
    end_dt = start_dt + timedelta(seconds=activity["elapsed_time"])
    timezone_str = activity.get("timezone", "UTC").split(" ")[-1]

    event = {
        "summary": "Endu",
        "description": format_description(activity["distance"], activity["moving_time"]),
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone_str},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone_str},
    }
    service.events().insert(calendarId=calendar_id, body=event).execute()
    logger.info(
        f"Created GCal event for activity {activity['id']} "
        f"({activity['distance'] / 1000:.2f} km on {start_dt.date()})"
    )


def strava_to_gcal(
    last_activity_id: Annotated[
        int,
        typer.Argument(help="Last processed Strava activity ID (0 to process all recent)"),
    ],
    calendar_id: Annotated[
        str,
        typer.Argument(help="Google Calendar ID to create events in"),
    ],
) -> None:
    """
    Probe Strava for new runs and create a Google Calendar event for each one
    """
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

    if not all([client_id, client_secret, refresh_token, service_account_json]):
        raise ValueError("Missing one or more required environment variables")

    access_token, new_refresh_token = refresh_strava_token(
        client_id, client_secret, refresh_token
    )
    logger.info("Strava token refreshed")

    new_runs = get_new_runs(access_token, last_activity_id)
    logger.info(f"Found {len(new_runs)} new run(s) since activity ID {last_activity_id}")

    if new_runs:
        gcal_service = build_gcal_service(service_account_json)
        for run in new_runs:
            create_gcal_event(gcal_service, calendar_id, run)

    new_last_activity_id = new_runs[-1]["id"] if new_runs else last_activity_id

    # Print to stdout so the workflow can capture and persist both values
    # Line 1: (possibly rotated) Strava refresh token
    # Line 2: new last activity ID
    print(new_refresh_token)
    print(new_last_activity_id)
