# JARVIS

An Iron Man inspired desktop cockpit assistant built in Python.

## Features

- Modular architecture with `jarvis.py`, `jarvis_core.py`, `jarvis_ui.py`, and `jarvis_voice.py`
- Cockpit-style Tkinter UI
- Always-on offline hotword monitoring using `SpeechRecognition` + `pocketsphinx`
- Live voice meter in the UI
- Wake-word arming with `jarvis`
- App launch commands for Calculator, Notepad, Explorer, Task Manager, PowerShell, Paint, and Settings
- File search and file opening inside the project folder
- Weather lookup using `wttr.in`
- Music control with media keys plus Spotify and YouTube Music shortcuts
- System actions like lock, restart, shutdown, and sleep
- Saved notes in `jarvis_notes.json`
- Optional OpenAI fallback when `OPENAI_API_KEY` is set

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. If microphone input does not work on Windows, install `PyAudio` separately.

3. Set your API key if you want AI responses:

```bash
set OPENAI_API_KEY=your_key_here
```

## Run

```bash
python jarvis.py
```

Useful options:

```bash
python jarvis.py --no-voice
python jarvis.py --cli
python jarvis.py --wake-word friday
```

## Example Commands

- `jarvis open browser`
- `jarvis open calculator`
- `jarvis search files for jarvis`
- `jarvis remember buy milk at 5 pm`
- `jarvis list notes`
- `jarvis lock screen`