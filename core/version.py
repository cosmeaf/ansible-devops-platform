"""Single source of truth for the platform version.

The canonical value lives in the top-level ``VERSION`` file so that build
tooling, container labels and the API can all agree without duplication.
"""

from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"

try:
    __version__ = _VERSION_FILE.read_text(encoding="utf-8").strip()
except OSError:  # pragma: no cover - only hit if VERSION is missing from a build
    __version__ = "0.0.0-unknown"

VERSION = __version__
