"""Album art widget — renders thumbnail as Unicode block art."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Optional

from rich.text import Text
from textual.widget import Widget
from textual.reactive import reactive

log = logging.getLogger(__name__)

# Block characters for rendering (each char = 2 vertical pixels)
UPPER_HALF = "▀"
LOWER_HALF = "▄"
FULL_BLOCK = "█"


class AlbumArt(Widget):
    """Displays album art as colored Unicode block characters."""

    DEFAULT_CSS = """
    AlbumArt {
        width: 100%;
        height: 100%;
        content-align: center middle;
    }
    """

    thumbnail_url: reactive[str] = reactive("", layout=True)
    _rendered_lines: reactive[list] = reactive(list, layout=True)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._pixel_data: Optional[list[list[tuple]]] = None
        self._art_width = 30
        self._art_height = 30

    def render(self) -> Text:
        """Render the album art."""
        if not self._rendered_lines:
            return self._render_placeholder()
        text = Text()
        for i, line in enumerate(self._rendered_lines):
            text.append_text(line)
            if i < len(self._rendered_lines) - 1:
                text.append("\n")
        return text

    def _render_placeholder(self) -> Text:
        """Render a placeholder when no art is loaded."""
        lines = [
            "┌────────────────────┐",
            "│                    │",
            "│    ♫  ♪  ♫  ♪     │",
            "│                    │",
            "│     y t u n e      │",
            "│                    │",
            "│    ♪  ♫  ♪  ♫     │",
            "│                    │",
            "└────────────────────┘",
        ]
        text = Text()
        for i, line in enumerate(lines):
            text.append(line, style="dim #a855f7")
            if i < len(lines) - 1:
                text.append("\n")
        return text

    async def watch_thumbnail_url(self, url: str) -> None:
        """React to thumbnail URL changes."""
        if not url:
            self._rendered_lines = []
            self.refresh()
            return
        # Load and render in background
        self.run_worker(self._load_and_render(url), exclusive=True)

    async def _load_and_render(self, url: str) -> None:
        """Load thumbnail from URL and convert to block art."""
        try:
            pixel_data = await asyncio.to_thread(self._fetch_image, url)
            if pixel_data:
                self._pixel_data = pixel_data
                lines = self._pixels_to_blocks(pixel_data)
                self._rendered_lines = lines
                self.refresh()
        except Exception as e:
            log.debug("Failed to load album art: %s", e)

    @staticmethod
    def _fetch_image(url: str) -> Optional[list[list[tuple]]]:
        """Fetch and resize image, return pixel grid."""
        try:
            import urllib.request
            from PIL import Image

            # Download
            req = urllib.request.Request(url, headers={"User-Agent": "ytune/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()

            img = Image.open(io.BytesIO(data)).convert("RGB")

            # Resize to fit terminal (each char = ~2 pixels height)
            target_w, target_h = 24, 24
            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

            pixels = []
            for y in range(img.height):
                row = []
                for x in range(img.width):
                    row.append(img.getpixel((x, y)))
                pixels.append(row)
            return pixels
        except Exception as e:
            log.debug("Image fetch error: %s", e)
            return None

    @staticmethod
    def _pixels_to_blocks(pixels: list[list[tuple]]) -> list[Text]:
        """Convert pixel grid to colored block characters.

        Uses ▄ where top pixel = background, bottom pixel = foreground.
        This gives us 2 vertical pixels per character cell.
        """
        lines = []
        height = len(pixels)
        width = len(pixels[0]) if pixels else 0

        for y in range(0, height - 1, 2):
            line = Text()
            for x in range(width):
                top_r, top_g, top_b = pixels[y][x]
                bot_r, bot_g, bot_b = pixels[y + 1][x]
                top_color = f"#{top_r:02x}{top_g:02x}{top_b:02x}"
                bot_color = f"#{bot_r:02x}{bot_g:02x}{bot_b:02x}"
                # ▄ char: foreground = bottom pixel, background = top pixel
                line.append(LOWER_HALF, style=f"{bot_color} on {top_color}")
            lines.append(line)

        return lines
