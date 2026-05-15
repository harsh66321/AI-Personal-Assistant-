from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


BASE_DIR = Path(__file__).resolve().parent
MEMORY_FILE = BASE_DIR / "jarvis_memory.json"
USER_PREFS_FILE = BASE_DIR / "jarvis_prefs.json"
CONVERSATION_FILE = BASE_DIR / "jarvis_conversation.json"


@dataclass
class UserPreference:
    key: str
    value: Any
    created_at: str
    updated_at: str


@dataclass
class MemoryEntry:
    topic: str
    content: str
    importance: int = 5
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class PersonalMemory:
    def __init__(self):
        self.preferences: dict[str, Any] = self._load_preferences()
        self.memory_entries: list[MemoryEntry] = self._load_memory()
        self.conversation_history: list[dict[str, str]] = self._load_conversation()

    def _load_preferences(self) -> dict[str, Any]:
        if not USER_PREFS_FILE.exists():
            return {}

        try:
            return json.loads(USER_PREFS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_preferences(self) -> None:
        try:
            USER_PREFS_FILE.write_text(json.dumps(self.preferences, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load_memory(self) -> list[MemoryEntry]:
        if not MEMORY_FILE.exists():
            return []

        try:
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            return [MemoryEntry(**item) for item in data if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError):
            return []

    def _save_memory(self) -> None:
        try:
            data = [asdict(entry) for entry in self.memory_entries]
            MEMORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load_conversation(self) -> list[dict[str, str]]:
        if not CONVERSATION_FILE.exists():
            return []

        try:
            data = json.loads(CONVERSATION_FILE.read_text(encoding="utf-8"))
            return data[-10:] if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save_conversation(self) -> None:
        try:
            CONVERSATION_FILE.write_text(json.dumps(self.conversation_history[-50:], indent=2), encoding="utf-8")
        except OSError:
            pass

    def set_preference(self, key: str, value: Any) -> None:
        self.preferences[key] = value
        self._save_preferences()

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self.preferences.get(key, default)

    def remember(self, topic: str, content: str, importance: int = 5) -> None:
        entry = MemoryEntry(topic=topic, content=content, importance=importance)
        self.memory_entries.append(entry)
        self._save_memory()

    def recall(self, topic: Optional[str] = None) -> list[MemoryEntry]:
        if topic is None:
            return sorted(self.memory_entries, key=lambda x: x.importance, reverse=True)[:5]

        return [entry for entry in self.memory_entries if topic.lower() in entry.topic.lower()]

    def forget(self, topic: str) -> int:
        before = len(self.memory_entries)
        self.memory_entries = [entry for entry in self.memory_entries if topic.lower() not in entry.topic.lower()]
        if len(self.memory_entries) < before:
            self._save_memory()
        return before - len(self.memory_entries)

    def add_conversation(self, speaker: str, message: str) -> None:
        self.conversation_history.append({
            "speaker": speaker,
            "message": message,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self._save_conversation()

    def get_context(self) -> str:
        prefs = json.dumps(self.preferences, default=str)
        recent_memory = " | ".join(f"{e.topic}: {e.content}" for e in self.memory_entries[-3:])
        return f"User preferences: {prefs}. Recent memory: {recent_memory or 'None'}."

    def clear_old_entries(self, days: int = 30) -> int:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        before = len(self.memory_entries)
        self.memory_entries = [entry for entry in self.memory_entries if entry.created_at > cutoff]
        if len(self.memory_entries) < before:
            self._save_memory()
        return before - len(self.memory_entries)
