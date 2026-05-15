from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _bootstrap_venv() -> None:
    project_dir = Path(__file__).resolve().parent
    venv_python = project_dir / ".venv" / "Scripts" / "python.exe"

    if not venv_python.exists():
        return

    current_executable = Path(sys.executable).resolve()
    if current_executable == venv_python.resolve():
        return

    os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])


_bootstrap_venv()

from jarvis_core import JarvisCore
from jarvis_ui import JarvisApp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JARVIS cockpit assistant")
    parser.add_argument("--wake-word", default="jarvis", help="Wake word to listen for")
    parser.add_argument("--no-voice", action="store_true", help="Start with voice disabled")
    parser.add_argument("--cli", action="store_true", help="Run in terminal mode instead of the UI")
    return parser.parse_args()


def run_cli(core: JarvisCore) -> None:
    core.speak("System initializing. JARVIS is online. Type 'help' for commands.")
    while True:
        try:
            raw = input("You: ").strip()
        except EOFError:
            break

        if not raw:
            continue

        result = core.process_command(raw)
        core.speak(result.message)
        if result.should_exit:
            break


def main() -> None:
    args = parse_args()
    core = JarvisCore(wake_word=args.wake_word)

    if args.cli:
        run_cli(core)
        return

    try:
        app = JarvisApp(core, start_voice=not args.no_voice)
        app.run()
    except Exception:
        run_cli(core)


if __name__ == "__main__":
    main()
