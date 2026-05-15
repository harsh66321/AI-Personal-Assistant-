from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

try:
    import pytesseract
except ImportError:
    pytesseract = None


class ScreenAnalyzer:
    def __init__(self, tesseract_path: Optional[str] = None):
        self.tesseract_available = pytesseract is not None
        if tesseract_path:
            try:
                pytesseract.pytesseract.pytesseract_cmd = tesseract_path
            except Exception:
                pass

    @property
    def available(self) -> bool:
        return ImageGrab is not None and self.tesseract_available

    def capture_screen(self, output_path: Optional[str] = None) -> Optional[str]:
        if not ImageGrab:
            return None

        try:
            screenshot = ImageGrab.grab()
            if output_path:
                screenshot.save(output_path)
                return output_path
            return screenshot
        except Exception:
            return None

    def extract_text(self, image_path: Optional[str] = None) -> str:
        if not self.available:
            return "OCR is unavailable. Install Pillow and pytesseract, and tesseract-ocr."

        try:
            if image_path is None:
                image = ImageGrab.grab()
            else:
                image = ImageGrab.open(image_path)

            text = pytesseract.image_to_string(image)
            return text.strip() or "No text found on screen."
        except Exception as exc:
            return f"OCR error: {exc}"

    def analyze_active_window(self) -> dict[str, str]:
        if not ImageGrab:
            return {"error": "Screen capture unavailable"}

        try:
            screenshot = ImageGrab.grab()
            text = pytesseract.image_to_string(screenshot) if self.tesseract_available else ""
            return {
                "screen_content": text[:500] or "Could not read screen content.",
                "size": f"{screenshot.width}x{screenshot.height}",
            }
        except Exception as exc:
            return {"error": str(exc)}

    def find_text_on_screen(self, search_text: str) -> bool:
        if not self.available:
            return False

        try:
            screenshot = ImageGrab.grab()
            screen_text = pytesseract.image_to_string(screenshot)
            return search_text.lower() in screen_text.lower()
        except Exception:
            return False

    def get_active_window_name(self) -> str:
        try:
            result = subprocess.run(
                ['powershell', '-Command', 'Get-Process | Where-Object {$_.MainWindowTitle} | Select-Object -First 1 -ExpandProperty MainWindowTitle'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() or "Unknown window"
        except Exception:
            return "Could not determine active window"
