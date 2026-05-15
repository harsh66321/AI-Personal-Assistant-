from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import pyttsx3
except ImportError:  # pragma: no cover - optional dependency
    pyttsx3 = None

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None

from jarvis_memory import PersonalMemory
from jarvis_screen import ScreenAnalyzer
from jarvis_calendar import CalendarReminder
from jarvis_iot import SmartHomeController



APP_NAME = "JARVIS"
DEFAULT_MODEL = os.getenv("JARVIS_MODEL", "gpt-4o-mini")
BASE_DIR = Path(__file__).resolve().parent
NOTES_FILE = BASE_DIR / "jarvis_notes.json"

VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
KEYEVENTF_KEYUP = 0x0002


@dataclass
class CommandResult:
    message: str
    should_exit: bool = False


class JarvisCore:
    def __init__(self, wake_word: str = "jarvis"):
        self.wake_word = wake_word.lower().strip()
        self.base_dir = BASE_DIR
        self.notes = self._load_notes()
        self.tts_engine = self._create_tts_engine()
        self.tts_enabled = self.tts_engine is not None
        self.client = OpenAI() if OpenAI and os.getenv("OPENAI_API_KEY") else None
        self.last_search_results: list[Path] = []
        self.memory = PersonalMemory()
        self.screen = ScreenAnalyzer()
        self.calendar = CalendarReminder()
        self.smart_home = SmartHomeController()

    def _create_tts_engine(self):
        if pyttsx3 is None:
            return None

        try:
            engine = pyttsx3.init("sapi5" if sys.platform.startswith("win") else None)
            voices = engine.getProperty("voices")
            if voices:
                engine.setProperty("voice", voices[0].id)
            engine.setProperty("rate", 182)
            engine.setProperty("volume", 1.0)
            return engine
        except Exception:
            return None

    def speak(self, text: str) -> None:
        print(f"{APP_NAME}: {text}")
        if self.tts_engine is None:
            return

        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as exc:
            self.tts_enabled = False
            print(f"{APP_NAME}: speech output failed: {exc}")

    def normalize(self, text: str) -> str:
        return re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()

    def _load_notes(self) -> list[dict[str, str]]:
        if not NOTES_FILE.exists():
            return []

        try:
            data = json.loads(NOTES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict) and "text" in item]
        except (OSError, json.JSONDecodeError):
            pass
        return []

    def _save_notes(self) -> None:
        try:
            NOTES_FILE.write_text(json.dumps(self.notes, indent=2), encoding="utf-8")
        except OSError:
            pass

    def process_command(self, command: str) -> CommandResult:
        original = command.strip()
        normalized = self.normalize(original)

        if not normalized:
            return CommandResult("Say a command, sir.")

        if normalized in {"help", "what can you do", "commands"}:
            return CommandResult(self.help_text())

        if normalized in {"time", "what time is it", "tell me the time"}:
            return CommandResult(f"The current time is {datetime.now().strftime('%I:%M %p')}.")

        if normalized in {"date", "what is the date", "tell me the date"}:
            return CommandResult(f"Today is {datetime.now().strftime('%A, %B %d, %Y')}.")

        if normalized in {"weather", "weather now", "forecast"}:
            return self._weather(None)

        weather_match = re.match(r"^(weather|forecast)\s+(in|for)\s+(.+)$", original, flags=re.I)
        if weather_match:
            return self._weather(weather_match.group(3).strip())

        if normalized in {"open browser", "launch browser", "open chrome", "launch chrome"}:
            return self._open_url("https://www.google.com")

        if normalized.startswith("search web for "):
            return self._search_web(original[15:].strip())

        if normalized.startswith("open website "):
            return self._open_website(original[13:].strip())

        if normalized.startswith("open url "):
            return self._open_website(original[9:].strip())

        if normalized.startswith("search files for ") or normalized.startswith("find file ") or normalized.startswith("search file "):
            query = re.sub(r"^(search files for|find file|search file)\s+", "", original, flags=re.I).strip()
            return self._search_files(query)

        if normalized.startswith("open file "):
            query = original[10:].strip()
            return self._open_first_file_match(query)

        remember_match = re.match(r"^(remember|note)\s+(.+)$", original, flags=re.I)
        if remember_match:
            return self._remember_note(remember_match.group(2).strip())

        if normalized in {"list notes", "show notes"}:
            return self._list_notes()

        if normalized in {"clear notes", "delete notes"}:
            return self._clear_notes()

        if normalized in {"open calculator", "launch calculator", "open calc"}:
            return self._run_process(["calc.exe"], "Opening Calculator.")

        if normalized in {"open notepad", "launch notepad"}:
            return self._run_process(["notepad.exe"], "Opening Notepad.")

        if normalized in {"open explorer", "launch explorer", "open files", "open file explorer"}:
            return self._run_process(["explorer.exe"], "Opening File Explorer.")

        if normalized in {"open task manager", "launch task manager"}:
            return self._run_process(["taskmgr.exe"], "Opening Task Manager.")

        if normalized in {"open powershell", "launch powershell", "open terminal", "launch terminal"}:
            return self._run_process(["powershell.exe"], "Opening PowerShell.")

        if normalized in {"open settings", "launch settings"}:
            return self._run_process(["cmd", "/c", "start", "", "ms-settings:"], "Opening Settings.")

        if normalized in {"lock screen", "lock workstation"}:
            return self._run_process(["rundll32.exe", "user32.dll,LockWorkStation"], "Locking the workstation.")

        if normalized in {"restart computer", "restart system"}:
            return self._run_process(["shutdown", "/r", "/t", "0"], "Restarting the computer.")

        if normalized in {"shutdown computer", "shutdown system"}:
            return self._run_process(["shutdown", "/s", "/t", "0"], "Shutting down the computer.")

        if normalized in {"sleep computer", "sleep system"}:
            return self._run_process(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], "Putting the system to sleep.")

        if normalized in {"play music", "resume music", "music play", "music resume"}:
            return self._media_key(VK_MEDIA_PLAY_PAUSE, "Toggling music playback.")

        if normalized in {"pause music", "music pause"}:
            return self._media_key(VK_MEDIA_PLAY_PAUSE, "Pausing music.")

        if normalized in {"next track", "skip track", "next song"}:
            return self._media_key(VK_MEDIA_NEXT_TRACK, "Skipping to the next track.")

        if normalized in {"previous track", "previous song", "back track"}:
            return self._media_key(VK_MEDIA_PREV_TRACK, "Going back one track.")

        if normalized in {"mute volume", "mute sound"}:
            return self._media_key(VK_VOLUME_MUTE, "Muting volume.")

        if normalized in {"volume up", "turn volume up"}:
            return self._media_key(VK_VOLUME_UP, "Increasing volume.")

        if normalized in {"volume down", "turn volume down"}:
            return self._media_key(VK_VOLUME_DOWN, "Lowering volume.")

        if normalized in {"open spotify", "launch spotify", "open music"}:
            return self._open_url("https://open.spotify.com")

        if normalized in {"open youtube music", "launch youtube music"}:
            return self._open_url("https://music.youtube.com")

        # Calendar and reminders
        if normalized in {"calendar", "list events", "show calendar", "upcoming events"}:
            return CommandResult(self.calendar.list_events())

        if normalized.startswith("add event "):
            return CommandResult(self.calendar.add_event(original[10:].strip(), datetime.now().isoformat(), (datetime.now()).isoformat()))

        if normalized in {"reminders", "list reminders", "show reminders"}:
            return CommandResult(self.calendar.list_reminders())

        if normalized.startswith("remind me "):
            parts = original[10:].strip().rsplit(" at ", 1)
            if len(parts) == 2:
                return CommandResult(self.calendar.add_reminder(parts[0], parts[1]))
            return CommandResult(self.calendar.add_reminder(parts[0], "in 1 hour"))

        # Screen and OCR
        if normalized in {"read screen", "what is on screen", "screen text", "ocr"}:
            return CommandResult(self.screen.extract_text())

        if normalized in {"active window", "what window", "current window"}:
            return CommandResult(f"Active window: {self.screen.get_active_window_name()}")

        if normalized.startswith("find text "):
            search_term = original[10:].strip()
            found = self.screen.find_text_on_screen(search_term)
            return CommandResult(f"Text '{search_term}' is {'visible' if found else 'not visible'} on screen.")

        # Memory and personalization
        if normalized.startswith("remember "):
            topic_and_content = original[9:].strip()
            if " as " in topic_and_content:
                topic, content = topic_and_content.split(" as ", 1)
                self.memory.remember(topic.strip(), content.strip())
                return CommandResult(f"Remembered: {content.strip()}")
            self.memory.remember("general", topic_and_content)
            return CommandResult(f"Remembered: {topic_and_content}")

        if normalized in {"recall memory", "what do you remember", "recall"}:
            entries = self.memory.recall()
            if not entries:
                return CommandResult("I have no memories yet.")
            lines = [f"• {e.topic}: {e.content}" for e in entries[:5]]
            return CommandResult("My memories:\n" + "\n".join(lines))

        if normalized.startswith("set preference "):
            parts = original[14:].strip().split("=", 1)
            if len(parts) == 2:
                self.memory.set_preference(parts[0].strip(), parts[1].strip())
                return CommandResult(f"Preference set: {parts[0].strip()} = {parts[1].strip()}")
            return CommandResult("Usage: set preference key = value")

        # Smart home and IoT
        if normalized in {"smart devices", "list devices", "my devices"}:
            return CommandResult(self.smart_home.list_devices())

        if normalized.startswith("turn ") and "on" in normalized:
            device = original[5:].split(" on")[0].strip()
            return CommandResult(self.smart_home.control_device(device, "on"))

        if normalized.startswith("turn ") and "off" in normalized:
            device = original[5:].split(" off")[0].strip()
            return CommandResult(self.smart_home.control_device(device, "off"))

        if normalized.startswith("device status "):
            device = original[13:].strip()
            return CommandResult(self.smart_home.get_device_status(device))

        app_match = re.match(r"^(open|launch)\s+(.+)$", normalized)
        if app_match:
            return self._launch_app(app_match.group(2))

        ai_reply = self._ask_ai(original)
        if ai_reply:
            return CommandResult(ai_reply)

        return CommandResult("I could not handle that request yet.")

    def help_text(self) -> str:
        return (
            "Try commands like: open browser, open calculator, weather, play music, next track, volume up, "
            "search files for <name>, remember <note>, list notes, lock screen, restart computer, "
            "calendar, remind me dinner at 7pm, read screen, turn living room light on, "
            "remember topic as content, set preference key = value, or search web for <topic>."
        )

    def _run_process(self, args: list[str], success_message: str) -> CommandResult:
        try:
            subprocess.Popen(args, shell=False)
            return CommandResult(success_message)
        except Exception as exc:
            return CommandResult(f"I could not complete that action: {exc}")

    def _open_url(self, url: str) -> CommandResult:
        try:
            webbrowser.open(url)
            return CommandResult("Opening your browser now.")
        except Exception as exc:
            return CommandResult(f"I could not open the browser: {exc}")

    def _open_website(self, target: str) -> CommandResult:
        if not target:
            return CommandResult("Tell me which website to open.")

        cleaned = target.strip()
        if not re.match(r"^[a-z]+://", cleaned, flags=re.I):
            if " " in cleaned or "." not in cleaned:
                cleaned = f"https://www.google.com/search?q={urllib.parse.quote_plus(cleaned)}"
            else:
                cleaned = f"https://{cleaned}"

        return self._open_url(cleaned)

    def _search_web(self, query: str) -> CommandResult:
        if not query:
            return CommandResult("Tell me what to search for.")

        return self._open_url(f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}")

    def _launch_app(self, target: str) -> CommandResult:
        normalized = self.normalize(target)
        app_map: dict[str, list[str]] = {
            "calculator": ["calc.exe"],
            "calc": ["calc.exe"],
            "notepad": ["notepad.exe"],
            "explorer": ["explorer.exe"],
            "file explorer": ["explorer.exe"],
            "task manager": ["taskmgr.exe"],
            "powershell": ["powershell.exe"],
            "terminal": ["powershell.exe"],
            "command prompt": ["cmd.exe"],
            "settings": ["cmd", "/c", "start", "", "ms-settings:"],
            "paint": ["mspaint.exe"],
            "camera": ["start", "microsoft.windows.camera:"],
        }

        if normalized in {"browser", "chrome", "edge", "internet"}:
            return self._open_url("https://www.google.com")

        if normalized in {"spotify", "music"}:
            return self._open_url("https://open.spotify.com")

        args = app_map.get(normalized)
        if args is None:
            return CommandResult(f"I do not know how to launch '{target}'.")

        return self._run_process(args, f"Launching {target}.")

    def _search_files(self, query: str) -> CommandResult:
        if not query:
            return CommandResult("Tell me what file name to search for.")

        query_lower = query.lower()
        matches = [path for path in self.base_dir.rglob("*") if path.is_file() and query_lower in path.name.lower()]
        self.last_search_results = matches[:10]

        if not self.last_search_results:
            return CommandResult(f"No files matched '{query}'.")

        lines = [f"{index + 1}. {path.relative_to(self.base_dir)}" for index, path in enumerate(self.last_search_results)]
        return CommandResult("I found these files:\n" + "\n".join(lines))

    def _open_first_file_match(self, query: str) -> CommandResult:
        result = self._search_files(query)
        if not self.last_search_results:
            return result

        try:
            os.startfile(self.last_search_results[0])
            return CommandResult(f"Opening {self.last_search_results[0].name}.")
        except Exception as exc:
            return CommandResult(f"I found the file, but could not open it: {exc}")

    def _weather(self, location: Optional[str]) -> CommandResult:
        try:
            query = urllib.parse.quote(location or "")
            url = f"https://wttr.in/{query}?format=j1"
            with urllib.request.urlopen(url, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))

            current = payload["current_condition"][0]
            area = location or payload.get("nearest_area", [{}])[0].get("areaName", [{"value": "your location"}])[0].get("value", "your location")
            description = current.get("weatherDesc", [{"value": "clear"}])[0]["value"]
            temp_c = current.get("temp_C", "?")
            feels_c = current.get("FeelsLikeC", "?")
            humidity = current.get("humidity", "?")
            return CommandResult(
                f"Weather for {area}: {description}, {temp_c} C, feels like {feels_c} C, humidity {humidity} percent."
            )
        except (urllib.error.URLError, KeyError, json.JSONDecodeError, IndexError) as exc:
            return CommandResult(f"I could not fetch the weather right now: {exc}")

    def _media_key(self, vk_code: int, success_message: str) -> CommandResult:
        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(vk_code, 0, 0, 0)
            user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
            return CommandResult(success_message)
        except Exception as exc:
            return CommandResult(f"I could not send the media key: {exc}")

    def _remember_note(self, note: str) -> CommandResult:
        if not note:
            return CommandResult("Tell me what to remember first.")

        self.notes.append({"text": note, "created_at": datetime.now().isoformat(timespec="seconds")})
        self._save_notes()
        return CommandResult(f"I have stored that note: {note}")

    def _list_notes(self) -> CommandResult:
        if not self.notes:
            return CommandResult("You have no saved notes.")

        formatted = "\n".join(f"{index + 1}. {item['text']}" for index, item in enumerate(self.notes))
        return CommandResult("Your notes are:\n" + formatted)

    def _clear_notes(self) -> CommandResult:
        self.notes.clear()
        self._save_notes()
        return CommandResult("All notes have been cleared.")

    def _ask_ai(self, prompt: str) -> Optional[str]:
        if self.client is None:
            return None

        try:
            response = self.client.responses.create(
                model=DEFAULT_MODEL,
                input=(
                    "You are JARVIS, a concise, helpful desktop assistant. "
                    "Answer clearly and briefly.\n\n"
                    f"User request: {prompt}"
                ),
            )
            return response.output_text.strip() or None
        except Exception:
            return None
