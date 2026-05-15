from __future__ import annotations

import queue
import re
import threading
from datetime import datetime
from typing import Optional

import tkinter as tk
from tkinter import scrolledtext, ttk

from jarvis_core import JarvisCore
from jarvis_voice import VoiceMonitor, normalize


class JarvisApp:
    def __init__(self, core: JarvisCore, start_voice: bool = True):
        self.core = core
        self.start_voice = start_voice
        self.root = tk.Tk()
        self.root.title("JARVIS Cockpit")
        self.root.geometry("1240x780")
        self.root.minsize(1000, 660)
        self.root.configure(bg="#07111d")
        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.voice_monitor = VoiceMonitor(
            wake_word=self.core.wake_word,
            on_phrase=self._on_voice_phrase,
            on_level=self._on_voice_level,
            on_status=self._on_voice_status,
            on_error=self._on_voice_error,
        )

        self._build_style()
        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(60, self._drain_events)

        self.append_system("JARVIS cockpit online. Use the command box or voice hotword.")
        self._update_voice_capability()
        if self.start_voice:
            self.start_voice_monitor()

    def _build_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        bg = "#07111d"
        panel = "#0c1a29"
        accent = "#2fd7ff"
        accent_dark = "#163244"
        text = "#d9f3ff"

        style.configure("TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("Header.TFrame", background="#091521")
        style.configure("TLabel", background=bg, foreground=text, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#091521", foreground=accent, font=("Segoe UI", 22, "bold"))
        style.configure("Sub.TLabel", background="#091521", foreground=text, font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=panel, foreground=accent, font=("Segoe UI", 11, "bold"))
        style.configure("Accent.TButton", background=accent_dark, foreground=text, padding=(12, 8))
        style.map(
            "Accent.TButton",
            background=[("active", accent), ("pressed", accent_dark)],
            foreground=[("active", "#001018")],
        )

        self.colors = {
            "bg": bg,
            "panel": panel,
            "accent": accent,
            "text": text,
            "log_bg": "#051018",
            "log_fg": "#dff7ff",
            "muted": "#547084",
            "warn": "#f5c96a",
            "voice_idle": "#173246",
            "voice_hot": "#2fd7ff",
            "voice_peak": "#7bffb8",
        }

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=3)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, style="Header.TFrame", padding=18)
        header.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)

        ttk.Label(header, text="JARVIS", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="A modular cockpit assistant with always-on offline hotword detection and a live voice meter.",
            style="Sub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        self.status_var = tk.StringVar(value="Booting...")
        ttk.Label(header, textvariable=self.status_var, style="Sub.TLabel").grid(row=0, column=1, rowspan=2, sticky="e")

        main_panel = ttk.Frame(self.root, style="Panel.TFrame", padding=14)
        main_panel.grid(row=1, column=0, sticky="nsew", padx=(14, 8), pady=(12, 12))
        main_panel.rowconfigure(1, weight=1)
        main_panel.columnconfigure(0, weight=1)

        ttk.Label(main_panel, text="Mission Log", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.log = scrolledtext.ScrolledText(
            main_panel,
            wrap=tk.WORD,
            height=24,
            bg=self.colors["log_bg"],
            fg=self.colors["log_fg"],
            insertbackground=self.colors["accent"],
            relief=tk.FLAT,
            font=("Consolas", 11),
            padx=12,
            pady=12,
        )
        self.log.grid(row=1, column=0, sticky="nsew", pady=(10, 12))
        self.log.configure(state=tk.DISABLED)

        command_bar = ttk.Frame(main_panel, style="Panel.TFrame")
        command_bar.grid(row=2, column=0, sticky="ew")
        command_bar.columnconfigure(0, weight=1)

        self.command_var = tk.StringVar()
        self.command_entry = tk.Entry(
            command_bar,
            textvariable=self.command_var,
            bg="#091724",
            fg=self.colors["text"],
            insertbackground=self.colors["accent"],
            relief=tk.FLAT,
            font=("Segoe UI", 11),
        )
        self.command_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.command_entry.bind("<Return>", self._submit_command_event)

        ttk.Button(command_bar, text="Send", style="Accent.TButton", command=self.submit_command).grid(row=0, column=1, padx=(0, 10))
        self.voice_button = ttk.Button(command_bar, text="Voice On", style="Accent.TButton", command=self.start_voice_monitor)
        self.voice_button.grid(row=0, column=2, padx=(0, 10))
        ttk.Button(command_bar, text="Voice Off", style="Accent.TButton", command=self.stop_voice_monitor).grid(row=0, column=3)

        meter_panel = ttk.Frame(main_panel, style="Panel.TFrame")
        meter_panel.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        meter_panel.columnconfigure(0, weight=1)

        ttk.Label(meter_panel, text="Voice Meter", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.voice_canvas = tk.Canvas(
            meter_panel,
            height=54,
            bg="#051018",
            highlightthickness=0,
            bd=0,
        )
        self.voice_canvas.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.voice_bars: list[int] = []
        self._build_voice_meter()

        sidebar = ttk.Frame(self.root, style="Panel.TFrame", padding=14)
        sidebar.grid(row=1, column=1, sticky="nsew", padx=(8, 14), pady=(12, 12))
        sidebar.columnconfigure(0, weight=1)

        ttk.Label(sidebar, text="Quick Controls", style="Section.TLabel").grid(row=0, column=0, sticky="w")

        quick_actions = [
            ("Help", lambda: self.submit_command("help")),
            ("Calendar", lambda: self.submit_command("calendar")),
            ("Read Screen", lambda: self.submit_command("read screen")),
            ("Smart Devices", lambda: self.submit_command("smart devices")),
            ("Reminders", lambda: self.submit_command("reminders")),
            ("My Memory", lambda: self.submit_command("recall memory")),
        ]

        for row_index, (label, action) in enumerate(quick_actions, start=1):
            ttk.Button(sidebar, text=label, style="Accent.TButton", command=action).grid(row=row_index, column=0, sticky="ew", pady=(10, 0))

        ttk.Label(sidebar, text="Available Skills", style="Section.TLabel").grid(row=7, column=0, sticky="w", pady=(20, 8))
        skills = (
            "calendar / reminders\n"
            "remind me dinner at 7pm\n"
            "remember <note>\n"
            "read screen / OCR\n"
            "active window\n"
            "smart devices\n"
            "turn light on/off\n"
            "search files\n"
            "weather\n"
            "lock screen"
        )
        ttk.Label(sidebar, text=skills, style="TLabel", justify="left").grid(row=8, column=0, sticky="nw")

        footer = ttk.Frame(self.root, style="Header.TFrame", padding=(16, 10))
        footer.grid(row=2, column=0, columnspan=2, sticky="ew")
        footer.columnconfigure(0, weight=1)

        self.footer_var = tk.StringVar(value=f"Wake word: {self.core.wake_word}")
        ttk.Label(footer, textvariable=self.footer_var, style="Sub.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="Clear Log", style="Accent.TButton", command=self.clear_log).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(footer, text="Quit", style="Accent.TButton", command=self.close).grid(row=0, column=2, padx=(8, 0))

        self.command_entry.focus_set()

    def _build_voice_meter(self) -> None:
        self.voice_canvas.delete("all")
        self.voice_bars.clear()

        width = 920
        height = 54
        padding = 8
        bar_count = 24
        gap = 5
        bar_width = max(18, (width - padding * 2 - gap * (bar_count - 1)) // bar_count)
        for index in range(bar_count):
            x1 = padding + index * (bar_width + gap)
            y1 = 11
            x2 = x1 + bar_width
            y2 = height - 10
            bar_id = self.voice_canvas.create_rectangle(x1, y1, x2, y2, fill=self.colors["voice_idle"], outline="")
            self.voice_bars.append(bar_id)

        self.voice_canvas.configure(scrollregion=(0, 0, width, height))

    def _set_voice_level(self, level: int) -> None:
        level = max(0, min(100, level))
        active_bars = int(round((level / 100) * len(self.voice_bars)))

        for index, bar_id in enumerate(self.voice_bars):
            if index < active_bars:
                color = self.colors["voice_hot"] if level < 35 else self.colors["voice_peak"]
            else:
                color = self.colors["voice_idle"]
            self.voice_canvas.itemconfigure(bar_id, fill=color)

    def _update_voice_capability(self) -> None:
        if self.voice_monitor.available:
            self.voice_button.configure(text="Voice On", state=tk.NORMAL)
            self.set_status("Offline hotword ready.")
        else:
            self.voice_button.configure(text="Text-Only Mode", state=tk.DISABLED)
            self.set_status("Text-only mode active. Microphone backend unavailable.")

    def append_system(self, message: str) -> None:
        self._append_log("SYSTEM", message)
        self.set_status(message)

    def append_user(self, message: str) -> None:
        self._append_log("YOU", message)

    def append_jarvis(self, message: str) -> None:
        self._append_log("JARVIS", message)

    def _append_log(self, speaker: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, f"[{timestamp}] {speaker}: {message}\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def set_status(self, message: str) -> None:
        self.status_var.set(message)
        self.footer_var.set(f"Wake word: {self.core.wake_word} | {message}")

    def clear_log(self) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

    def _submit_command_event(self, event: object) -> str:
        self.submit_command()
        return "break"

    def submit_command(self, command: Optional[str] = None) -> None:
        text = command if command is not None else self.command_var.get()
        cleaned = text.strip()
        if not cleaned:
            return

        if command is None:
            self.command_var.set("")

        self.append_user(cleaned)
        threading.Thread(target=self._process_command_worker, args=(cleaned,), daemon=True).start()

    def _process_command_worker(self, command: str) -> None:
        result = self.core.process_command(command)
        self.core.speak(result.message)
        self.event_queue.put(("assistant", result.message))
        if result.should_exit:
            self.event_queue.put(("exit", ""))

    def start_voice_monitor(self) -> None:
        if self.voice_monitor.running:
            self.set_status("Voice hotword already running.")
            return

        if not self.voice_monitor.available:
            message = "Voice input is unavailable in the current environment. Text commands still work."
            self.set_status(message)
            self.append_system(message)
            return

        self.voice_monitor.start()
        self.set_status("Offline hotword monitoring active.")
        self.append_system("Voice monitoring started.")

    def stop_voice_monitor(self) -> None:
        self.voice_monitor.stop()
        self._set_voice_level(0)
        self.set_status("Voice monitoring stopped.")
        self.append_system("Voice monitoring stopped.")

    def _on_voice_phrase(self, phrase: str) -> None:
        self.event_queue.put(("voice_phrase", phrase))

    def _on_voice_level(self, level: int) -> None:
        self.event_queue.put(("voice_level", level))

    def _on_voice_status(self, message: str) -> None:
        self.event_queue.put(("status", message))

    def _on_voice_error(self, message: str) -> None:
        self.event_queue.put(("error", message))

    def _handle_voice_phrase(self, phrase: str) -> None:
        normalized = normalize(phrase)
        if not normalized:
            return

        if self.core.wake_word and self.core.wake_word in normalized:
            command = normalized.replace(self.core.wake_word, "", 1).strip()
            self.append_system("Wake word detected.")
            self.core.speak("Yes, sir?")

            if command:
                self.append_user(f"[voice] {command}")
                threading.Thread(target=self._process_command_worker, args=(command,), daemon=True).start()

    def _drain_events(self) -> None:
        while True:
            try:
                event_type, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break

            if event_type == "assistant":
                self.append_jarvis(str(payload))
            elif event_type == "voice_phrase":
                self._handle_voice_phrase(str(payload))
            elif event_type == "voice_level":
                self._set_voice_level(int(payload))
            elif event_type == "status":
                self.set_status(str(payload))
            elif event_type == "error":
                self.set_status(str(payload))
            elif event_type == "exit":
                self.close()

        self.root.after(60, self._drain_events)

    def close(self) -> None:
        self.voice_monitor.stop()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self) -> None:
        self.root.mainloop()
