"""Timestamped logging (IST + UTC on every line) with an in-memory ring buffer
that the UI polls, plus optional per-run file output.

Engineering convention: every action is logged with both timezones.
"""
from __future__ import annotations

import sys
import threading
from collections import deque
from typing import Optional, TextIO

from tz import iso_ist, iso_utc, now_utc


class LogBus:
    """Thread-safe log sink.

    - Keeps the last `capacity` records in memory (for the UI /api/logs poll).
    - Optionally mirrors every line to a file handle (per-run log).
    - Always echoes to stderr so console/journald captures it too.
    """

    def __init__(self, capacity: int = 5000):
        self._lock = threading.Lock()
        self._buf: deque[dict] = deque(maxlen=capacity)
        self._seq = 0
        self._file: Optional[TextIO] = None

    def attach_file(self, fh: TextIO) -> None:
        with self._lock:
            self._file = fh

    def detach_file(self) -> None:
        with self._lock:
            if self._file:
                try:
                    self._file.flush()
                except Exception:
                    pass
            self._file = None

    def log(self, message: str, level: str = "INFO", **fields) -> dict:
        dt = now_utc()
        with self._lock:
            self._seq += 1
            rec = {
                "seq": self._seq,
                "level": level,
                "utc": iso_utc(dt),
                "ist": iso_ist(dt),
                "msg": message,
                **fields,
            }
            self._buf.append(rec)
            line = f"[{rec['ist']} IST | {rec['utc']} UTC] {level:5s} {message}"
            print(line, file=sys.stderr, flush=True)
            if self._file:
                try:
                    self._file.write(line + "\n")
                    self._file.flush()
                except Exception:
                    pass
        return rec

    def info(self, msg: str, **f):
        return self.log(msg, "INFO", **f)

    def warn(self, msg: str, **f):
        return self.log(msg, "WARN", **f)

    def error(self, msg: str, **f):
        return self.log(msg, "ERROR", **f)

    def since(self, seq: int) -> list[dict]:
        with self._lock:
            return [r for r in self._buf if r["seq"] > seq]

    def tail(self, n: int = 200) -> list[dict]:
        with self._lock:
            return list(self._buf)[-n:]


# Process-wide bus used by the app and background runs.
BUS = LogBus()
