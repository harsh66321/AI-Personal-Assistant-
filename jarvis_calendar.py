from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None


BASE_DIR = Path(__file__).resolve().parent
CALENDAR_FILE = BASE_DIR / "jarvis_calendar.json"
REMINDERS_FILE = BASE_DIR / "jarvis_reminders.json"


@dataclass
class CalendarEvent:
    title: str
    start_time: str
    end_time: str
    description: str = ""
    location: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class Reminder:
    title: str
    scheduled_time: str
    importance: int = 5
    completed: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class CalendarReminder:
    def __init__(self):
        self.events: list[CalendarEvent] = self._load_events()
        self.reminders: list[Reminder] = self._load_reminders()

    def _load_events(self) -> list[CalendarEvent]:
        if not CALENDAR_FILE.exists():
            return []

        try:
            data = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
            return [CalendarEvent(**item) for item in data if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError):
            return []

    def _save_events(self) -> None:
        try:
            data = [asdict(event) for event in self.events]
            CALENDAR_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load_reminders(self) -> list[Reminder]:
        if not REMINDERS_FILE.exists():
            return []

        try:
            data = json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
            return [Reminder(**item) for item in data if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError):
            return []

    def _save_reminders(self) -> None:
        try:
            data = [asdict(reminder) for reminder in self.reminders]
            REMINDERS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def add_event(self, title: str, start_time: str, end_time: str, description: str = "", location: str = "") -> str:
        try:
            if date_parser:
                start = date_parser.parse(start_time)
                end = date_parser.parse(end_time)
                start_time = start.isoformat()
                end_time = end.isoformat()
        except Exception:
            pass

        event = CalendarEvent(title=title, start_time=start_time, end_time=end_time, description=description, location=location)
        self.events.append(event)
        self._save_events()
        return f"Event '{title}' added to calendar."

    def list_events(self, days_ahead: int = 7) -> str:
        if not self.events:
            return "No events scheduled."

        now = datetime.now()
        upcoming = [
            event for event in self.events
            if datetime.fromisoformat(event.start_time) >= now
            and datetime.fromisoformat(event.start_time) <= now + timedelta(days=days_ahead)
        ]
        upcoming.sort(key=lambda e: e.start_time)

        if not upcoming:
            return f"No events in the next {days_ahead} days."

        lines = [f"{event.title} at {event.start_time[:16]}" for event in upcoming[:10]]
        return "Upcoming events:\n" + "\n".join(lines)

    def add_reminder(self, title: str, when: str, importance: int = 5) -> str:
        try:
            if date_parser:
                scheduled = date_parser.parse(when)
                when = scheduled.isoformat()
        except Exception:
            pass

        reminder = Reminder(title=title, scheduled_time=when, importance=importance)
        self.reminders.append(reminder)
        self._save_reminders()
        return f"Reminder '{title}' set for {when}."

    def list_reminders(self, show_completed: bool = False) -> str:
        if not self.reminders:
            return "No reminders set."

        active = [r for r in self.reminders if not r.completed or show_completed]
        if not active:
            return "No active reminders."

        lines = [f"{'✓' if r.completed else '○'} {r.title} at {r.scheduled_time[:16]}" for r in sorted(active, key=lambda r: r.scheduled_time)[:10]]
        return "Your reminders:\n" + "\n".join(lines)

    def complete_reminder(self, index: int) -> str:
        if 0 <= index < len(self.reminders):
            self.reminders[index].completed = True
            self._save_reminders()
            return f"Reminder marked as complete."
        return "Reminder not found."

    def get_due_reminders(self) -> list[Reminder]:
        now = datetime.now()
        return [r for r in self.reminders if not r.completed and datetime.fromisoformat(r.scheduled_time) <= now]

    def clear_old_events(self, days_back: int = 30) -> int:
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
        before = len(self.events)
        self.events = [event for event in self.events if event.start_time > cutoff]
        if len(self.events) < before:
            self._save_events()
        return before - len(self.events)
