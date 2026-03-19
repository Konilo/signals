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

SPORT_SUMMARIES = {
    "Run": "Endu",
    "WeightTraining": "Musc",
    "RockClimbing": "Climb",
}


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


def get_new_activities(access_token: str, last_activity_id: int) -> list[dict]:
    """Return supported Strava activities recorded after last_activity_id, oldest first."""
    response = requests.get(
        STRAVA_ACTIVITIES_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params={"per_page": 30},
    )
    response.raise_for_status()
    activities = response.json()
    new = [
        a
        for a in activities
        if a["sport_type"] in SPORT_SUMMARIES and a["id"] > last_activity_id
    ]
    return sorted(new, key=lambda a: a["id"])


def format_run_description(distance_m: float, moving_time_s: int) -> str:
    """Format run metrics (distance, pace, time)."""
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


def format_duration_description(moving_time_s: int) -> str:
    """Format duration-only metrics for non-distance sports."""
    total_min = moving_time_s // 60
    remaining_sec = moving_time_s % 60
    return f"Time\n    {total_min}m {remaining_sec:02d}s"


def build_gcal_service(service_account_json: str):
    """Build an authenticated Google Calendar API service."""
    credentials = Credentials.from_service_account_info(
        json.loads(service_account_json), scopes=GCAL_SCOPES
    )
    return build("calendar", "v3", credentials=credentials)


def create_gcal_event(service, calendar_map: dict[str, str], activity: dict) -> None:
    """Create a Google Calendar event for a supported Strava activity."""
    sport_type = activity["sport_type"]
    summary = SPORT_SUMMARIES[sport_type]
    calendar_id = calendar_map[sport_type]

    if sport_type == "Run" and activity["distance"] > 0:
        description = format_run_description(activity["distance"], activity["moving_time"])
    else:
        description = format_duration_description(activity["elapsed_time"])

    # start_date_local carries the Z suffix but represents local time — treat as naive
    start_dt = datetime.fromisoformat(activity["start_date_local"].replace("Z", ""))
    end_dt = start_dt + timedelta(seconds=activity["elapsed_time"])
    timezone_str = activity.get("timezone", "UTC").split(" ")[-1]

    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone_str},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone_str},
    }
    service.events().insert(calendarId=calendar_id, body=event).execute()
    logger.info(
        f"Created '{summary}' event for {sport_type} activity "
        f"{activity['id']} on {start_dt.date()}"
    )


def strava_to_gcal(
    last_activity_id: Annotated[
        int,
        typer.Argument(help="Last processed Strava activity ID (0 to process all recent)"),
    ],
    endu_calendar_id: Annotated[
        str,
        typer.Argument(help="Google Calendar ID for Run activities"),
    ],
    musc_calendar_id: Annotated[
        str,
        typer.Argument(help="Google Calendar ID for WeightTraining activities"),
    ],
    climb_calendar_id: Annotated[
        str,
        typer.Argument(help="Google Calendar ID for RockClimbing activities"),
    ],
) -> None:
    """
    Probe Strava for new activities and create a Google Calendar event for each one
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

    calendar_map = {
        "Run": endu_calendar_id,
        "WeightTraining": musc_calendar_id,
        "RockClimbing": climb_calendar_id,
    }

    new_activities = get_new_activities(access_token, last_activity_id)
    logger.info(f"Found {len(new_activities)} new activity/ies since ID {last_activity_id}")

    if new_activities:
        gcal_service = build_gcal_service(service_account_json)
        for activity in new_activities:
            create_gcal_event(gcal_service, calendar_map, activity)

    new_last_activity_id = new_activities[-1]["id"] if new_activities else last_activity_id

    # Print to stdout so the workflow can capture and persist both values
    # Line 1: (possibly rotated) Strava refresh token
    # Line 2: new last activity ID
    print(new_refresh_token)
    print(new_last_activity_id)
