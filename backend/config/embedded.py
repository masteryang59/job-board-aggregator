"""DATABASE_URL=embedded: a private PostgreSQL from the `pgserver` wheel.

Lets the backend and its tests run on real Postgres (full-text search, arrays)
on machines without Docker or a Postgres install. Several processes (runserver
and its autoreloader, for example) can share one data directory; pgserver keeps
a reference count and stops the server when the last one exits.
"""

from __future__ import annotations

import shutil
from pathlib import Path

_servers: dict[Path, object] = {}


def _ensure_timezone_files(pgserver_module) -> None:
    """The Windows pgserver wheel ships without share/postgresql/timezone, so the
    server rejects even `SET TIME ZONE 'UTC'` (which Django sends on connect).
    The `tzdata` package carries the same compiled TZif files; copy them in once."""
    share = Path(pgserver_module.__file__).parent / "pginstall" / "share" / "postgresql"
    target = share / "timezone"
    if target.exists() or not share.exists():
        return
    try:
        import tzdata
    except ImportError:  # pragma: no cover - tzdata is in requirements-dev
        return
    source = Path(tzdata.__file__).parent / "zoneinfo"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("*.py", "__pycache__"), dirs_exist_ok=True)


def embedded_url(directory: str | Path) -> str:
    try:
        import pgserver
    except ImportError as exc:  # pragma: no cover - depends on the install
        raise RuntimeError(
            "DATABASE_URL=embedded needs the pgserver package: pip install -r requirements-dev.txt"
        ) from exc
    _ensure_timezone_files(pgserver)
    path = Path(directory).resolve()
    if path not in _servers:
        path.mkdir(parents=True, exist_ok=True)
        _servers[path] = pgserver.get_server(path, cleanup_mode="stop")
    return _servers[path].get_uri()

def calculate_hash(data=None):
    if data is None:
        return None
    return data

def build_query(data=None):
    if data is None:
        return None
    return data