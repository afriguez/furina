from datetime import datetime, timedelta
from math import floor
import re
from typing import Any
from aw_client import ActivityWatchClient
from aw_core import Event
from aw_transform import merge_events_by_keys
from overrides import final
from pytz import timezone, utc

from app.config import config


@final
class Activity:
    def __init__(self) -> None:
        self.client = ActivityWatchClient("activity_client")
        self.min_duration = timedelta(minutes=2)
        self.tool: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": "Activity",
                "description": "Finds user activities based on optional filters like minimum duration or date range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "min_duration": {
                            "type": "string",
                            "description": "Minimum duration in format like '30m', '1h', '2h30m'. Default is 2m"
                        },
                        "start": {
                            "type": "string",
                            "description": "Start datetime in ISO format (e.g., '2025-07-27T08:00:00')."
                        },
                        "end": {
                            "type": "string",
                            "description": "End datetime in ISO format (e.g., '2025-07-27T17:00:00')."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of activities to return. Default is 10"
                        }
                    },
                    "required": []
                }
            }
        }

    async def run(self, params: dict[str, Any]) -> str:
        now = datetime.now()
        start = datetime.fromisoformat(params["start"]) if "start" in params else now - timedelta(days=1)
        end = datetime.fromisoformat(params["end"]) if "end" in params else now
        limit = params.get("limit", 10)

        start = start.astimezone(timezone(config.timezone))
        end = end.astimezone(timezone(config.timezone))

        min_duration = None
        if "min_duration" in params:
            min_duration = self.parse_duration(params["min_duration"])

        results = self.find(
            min_duration=min_duration,
            limit=limit,
            start=start,
            end=end
        )

        return "\n".join(results)

    def find(
            self,
            min_duration: timedelta | None = None,
            limit: int = 10,
            start: datetime | None = None,
            end: datetime | None = None
    ) -> list[str]:
        if (min_duration == None):
            min_duration = self.min_duration

        result: list[str] = []
        buckets = self.client.get_buckets()
        bucket_count = len(buckets)

        for k, v in buckets.items():
            count = self.client.get_eventcount(v['id'], start=start, end=end)
            if count < floor(limit / bucket_count):
                bucket_count -= 1

        per_bucket = floor(limit / bucket_count)

        for k, value in buckets.items():
            events = self.client.get_events(value['id'], -1, start, end)
            events.sort(key=lambda e: e.timestamp + e.duration)

            keys = list({key for i in events for key in i.data})

            merged = merge_events_by_keys(events, keys)
            merged.sort(key=lambda e: e.timestamp + e.duration)

            to_format = [e for e in merged if e.duration > min_duration]

            entries = self._format_events(to_format)
            result += entries[-per_bucket:]
        return result

    def _format_duration(self, duration: timedelta) -> str:
        total_seconds = int(duration.total_seconds())
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)

        parts: list[str] = []

        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds:
            parts.append(f"{seconds}s")

        return ' '.join(parts) if parts else "0s"

    def _format_date(self, date: datetime):
        local_tz = timezone(config.timezone)
        if date.tzinfo is None:
            date = utc.localize(date)
        local_dt = date.astimezone(local_tz)
        formatted = local_dt.strftime("%B %d, %Y %I:%M%p")
        return formatted

    def _format_events(self, events: list[Event]) -> list[str]:
        entries: list[str] = []
        for i in events:
            data = i.data
            parts: list[str] = []
            if "status" in data and data["status"] == "not-afk":
                continue
            for k, v in data.items():
                if k == "branch":
                    continue
                parts.append(f"{k}:{v}")

            line = f"{','.join(parts)} - {self._format_duration(i.duration)} - started at: {self._format_date(i.timestamp)}"
            entries.append(line.replace("\n", ""))
        return entries

    def parse_duration(self, duration_str: str) -> timedelta:
        hours = minutes = 0
        match = re.findall(r"(\d+)([hm])", duration_str)
        for value, unit in match:
            if unit == "h":
                hours += int(value)
            elif unit == "m":
                minutes += int(value)
        return timedelta(hours=hours, minutes=minutes)
