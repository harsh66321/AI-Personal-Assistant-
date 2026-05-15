from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - optional dependency
    sd = None

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover - optional dependency
    sr = None


LevelCallback = Callable[[int], None]
TextCallback = Callable[[str], None]
StatusCallback = Callable[[str], None]


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


@dataclass
class VoiceMonitorConfig:
    wake_word: str = "jarvis"
    energy_ceiling: int = 3000
    phrase_time_limit: int = 3
    timeout: int = 1
    sample_rate: int = 16000


class VoiceMonitor:
    def __init__(
        self,
        wake_word: str,
        on_phrase: TextCallback,
        on_level: LevelCallback,
        on_status: StatusCallback,
        on_error: StatusCallback,
        config: Optional[VoiceMonitorConfig] = None,
    ):
        self.config = config or VoiceMonitorConfig(wake_word=wake_word)
        self.on_phrase = on_phrase
        self.on_level = on_level
        self.on_status = on_status
        self.on_error = on_error
        self.recognizer = sr.Recognizer() if sr else None
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def available(self) -> bool:
        return sr is not None and sd is not None and self.recognizer is not None and self._has_microphone_support()

    @property
    def running(self) -> bool:
        return self._running.is_set()

    def start(self) -> None:
        if self.running or not self.available:
            return

        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()

    def _has_microphone_support(self) -> bool:
        if sd is None:
            return False

        try:
            device_info = sd.query_devices(None, "input")
            return device_info is not None
        except Exception:
            return False

    def _measure_level_from_array(self, samples: np.ndarray) -> int:
        if samples.size == 0:
            return 0

        energy = float(np.sqrt(np.mean(np.square(samples.astype(np.float32)))))
        level = int(min(100, (energy / max(self.config.energy_ceiling, 1)) * 100))
        return max(0, level)

    def _process_audio(self, samples: np.ndarray) -> None:
        if self.recognizer is None or sr is None:
            return

        level = self._measure_level_from_array(samples)
        self.on_level(level)

        audio_bytes = samples.astype(np.int16, copy=False).tobytes()
        audio_data = sr.AudioData(audio_bytes, self.config.sample_rate, 2)

        try:
            phrase = normalize(self.recognizer.recognize_google(audio_data))
        except sr.UnknownValueError:
            return
        except sr.RequestError as exc:
            self.on_error(f"Speech engine error: {exc}")
            return

        if phrase:
            self.on_phrase(phrase)
            self.on_level(0)

    def _run(self) -> None:
        if not sr or not sd:
            self.on_error("Voice recognition unavailable. Use text commands instead.")
            return

        if not self._has_microphone_support():
            self.on_error("Microphone input is unavailable. Use text commands instead.")
            return

        self.on_status(f"Voice input active. Say '{self.config.wake_word}' to start.")

        try:
            with sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=1,
                dtype="int16",
            ) as stream:
                while self._running.is_set():
                    frames = int(self.config.sample_rate * self.config.phrase_time_limit)
                    audio, overflowed = stream.read(frames)
                    if overflowed:
                        self.on_status("Audio buffer overflow detected; continuing.")

                    samples = np.asarray(audio, dtype=np.int16).reshape(-1)
                    self._process_audio(samples)
        except Exception as exc:
            self.on_error(f"Microphone unavailable: {exc}")
        finally:
            self.on_level(0)
