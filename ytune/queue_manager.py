"""Queue manager for ytune — manages the playback queue."""

from __future__ import annotations

import random
import logging
from typing import Optional

from ytune.models import Track, RepeatMode

log = logging.getLogger(__name__)


class QueueManager:
    """Manages the queue of tracks to play."""

    def __init__(self) -> None:
        self._tracks: list[Track] = []
        self._current_index: int = -1
        self._repeat = RepeatMode.OFF
        self._shuffle = False
        self._shuffle_order: list[int] = []
        self._shuffle_pos: int = -1

    @property
    def tracks(self) -> list[Track]:
        """All tracks in the queue."""
        return list(self._tracks)

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def current_track(self) -> Optional[Track]:
        if 0 <= self._current_index < len(self._tracks):
            return self._tracks[self._current_index]
        return None

    @property
    def repeat(self) -> RepeatMode:
        return self._repeat

    @repeat.setter
    def repeat(self, mode: RepeatMode) -> None:
        self._repeat = mode

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    @shuffle.setter
    def shuffle(self, enabled: bool) -> None:
        self._shuffle = enabled
        if enabled:
            self._build_shuffle_order()
        else:
            self._shuffle_order = []
            self._shuffle_pos = -1

    @property
    def length(self) -> int:
        return len(self._tracks)

    @property
    def is_empty(self) -> bool:
        return len(self._tracks) == 0

    def add(self, track: Track) -> None:
        """Add a track to the end of the queue."""
        self._tracks.append(track)
        if self._shuffle:
            self._shuffle_order.append(len(self._tracks) - 1)

    def add_next(self, track: Track) -> None:
        """Add a track to play next (after current)."""
        insert_pos = self._current_index + 1 if self._current_index >= 0 else 0
        self._tracks.insert(insert_pos, track)
        if self._shuffle:
            self._build_shuffle_order()

    def add_many(self, tracks: list[Track]) -> None:
        """Add multiple tracks to the queue."""
        self._tracks.extend(tracks)
        if self._shuffle:
            self._build_shuffle_order()

    def remove(self, index: int) -> Optional[Track]:
        """Remove a track by index. Returns the removed track."""
        if 0 <= index < len(self._tracks):
            track = self._tracks.pop(index)
            if index < self._current_index:
                self._current_index -= 1
            elif index == self._current_index:
                # Current track removed — stay at same index (will be next track)
                if self._current_index >= len(self._tracks):
                    self._current_index = len(self._tracks) - 1
            if self._shuffle:
                self._build_shuffle_order()
            return track
        return None

    def clear(self) -> None:
        """Clear the entire queue."""
        self._tracks.clear()
        self._current_index = -1
        self._shuffle_order.clear()
        self._shuffle_pos = -1

    def set_current(self, index: int) -> Optional[Track]:
        """Set the current track by index."""
        if 0 <= index < len(self._tracks):
            self._current_index = index
            return self._tracks[index]
        return None

    def next(self) -> Optional[Track]:
        """Advance to the next track. Returns None if at end."""
        if self.is_empty:
            return None

        if self._repeat == RepeatMode.ONE:
            return self.current_track

        if self._shuffle:
            return self._next_shuffle()

        next_index = self._current_index + 1

        if next_index >= len(self._tracks):
            if self._repeat == RepeatMode.ALL:
                next_index = 0
            else:
                return None

        self._current_index = next_index
        return self._tracks[self._current_index]

    def previous(self) -> Optional[Track]:
        """Go to the previous track."""
        if self.is_empty:
            return None

        if self._shuffle:
            return self._prev_shuffle()

        prev_index = self._current_index - 1

        if prev_index < 0:
            if self._repeat == RepeatMode.ALL:
                prev_index = len(self._tracks) - 1
            else:
                prev_index = 0

        self._current_index = prev_index
        return self._tracks[self._current_index]

    def move(self, from_index: int, to_index: int) -> None:
        """Move a track from one position to another."""
        if (0 <= from_index < len(self._tracks) and
                0 <= to_index < len(self._tracks) and
                from_index != to_index):
            track = self._tracks.pop(from_index)
            self._tracks.insert(to_index, track)
            # Update current index
            if from_index == self._current_index:
                self._current_index = to_index
            elif from_index < self._current_index <= to_index:
                self._current_index -= 1
            elif to_index <= self._current_index < from_index:
                self._current_index += 1

    def cycle_repeat(self) -> RepeatMode:
        """Cycle through repeat modes: OFF → ALL → ONE → OFF."""
        if self._repeat == RepeatMode.OFF:
            self._repeat = RepeatMode.ALL
        elif self._repeat == RepeatMode.ALL:
            self._repeat = RepeatMode.ONE
        else:
            self._repeat = RepeatMode.OFF
        return self._repeat

    def toggle_shuffle(self) -> bool:
        """Toggle shuffle on/off."""
        self.shuffle = not self._shuffle
        return self._shuffle

    # --- Shuffle internals ---

    def _build_shuffle_order(self) -> None:
        """Build a shuffled order of indices."""
        indices = list(range(len(self._tracks)))
        # Remove current track from shuffle
        if 0 <= self._current_index < len(self._tracks):
            indices.remove(self._current_index)
        random.shuffle(indices)
        # Put current track at the beginning
        if 0 <= self._current_index < len(self._tracks):
            indices.insert(0, self._current_index)
        self._shuffle_order = indices
        # Find current position in shuffle order
        if self._current_index >= 0:
            self._shuffle_pos = 0
        else:
            self._shuffle_pos = -1

    def _next_shuffle(self) -> Optional[Track]:
        if not self._shuffle_order:
            return None

        self._shuffle_pos += 1
        if self._shuffle_pos >= len(self._shuffle_order):
            if self._repeat == RepeatMode.ALL:
                self._build_shuffle_order()
                self._shuffle_pos = 0
            else:
                return None

        self._current_index = self._shuffle_order[self._shuffle_pos]
        return self._tracks[self._current_index]

    def _prev_shuffle(self) -> Optional[Track]:
        if not self._shuffle_order:
            return None

        self._shuffle_pos -= 1
        if self._shuffle_pos < 0:
            self._shuffle_pos = 0

        self._current_index = self._shuffle_order[self._shuffle_pos]
        return self._tracks[self._current_index]
