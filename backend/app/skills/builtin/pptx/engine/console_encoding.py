#!/usr/bin/env python3
"""Console encoding helpers for PPT Master CLI scripts."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import TextIO

from attribution_guard import require_skill_integrity
from workflow_transcript import install_auto_transcript


def _reconfigure_stream(stream: TextIO) -> TextIO:
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
        return stream
    except AttributeError:
        buffer = getattr(stream, "buffer", None)
        if buffer is None:
            return stream
        return io.TextIOWrapper(buffer, encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return stream


def configure_utf8_stdio() -> None:
    """Configure CLI streams and enable project-scoped output recording."""
    require_skill_integrity()
    sys.stdout = _reconfigure_stream(sys.stdout)
    sys.stderr = _reconfigure_stream(sys.stderr)
    install_auto_transcript()
