"""
core/fsutil.py — Filesystem helpers shared by Layer 5 (atomic writes, inter-process lock).

Config/registry files (ui_event_map.json, ui_query_stubs.json, logs/token_report.json) are
read-modify-written by agents that the frontend can start concurrently, so writes go through a
temp file + os.replace (readers never see a torn file) under an exclusive lock.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Iterator

try:  # POSIX
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows
    _fcntl = None
try:  # Windows
    import msvcrt as _msvcrt
except ImportError:
    _msvcrt = None

_LOCK_DIR = Path(tempfile.gettempdir()) / "vba_brain_layer5_locks"


def atomic_write_text(path: str | Path, text: str, encoding: str = "utf-8") -> None:
    """Write `text` to `path` via a temp file in the same directory, then os.replace()."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def file_lock(path: str | Path) -> Iterator[None]:
    """Blocking exclusive lock for `path`; the lock file lives in the temp dir, not the repo."""
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(str(Path(path).resolve()).encode("utf-8")).hexdigest()[:16]
    with open(_LOCK_DIR / f"{digest}.lock", "a+") as fh:
        if _fcntl is not None:
            _fcntl.flock(fh.fileno(), _fcntl.LOCK_EX)
        elif _msvcrt is not None:  # pragma: no cover - Windows
            fh.seek(0)
            _msvcrt.locking(fh.fileno(), _msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if _fcntl is not None:
                _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)
            elif _msvcrt is not None:  # pragma: no cover - Windows
                fh.seek(0)
                _msvcrt.locking(fh.fileno(), _msvcrt.LK_UNLCK, 1)
