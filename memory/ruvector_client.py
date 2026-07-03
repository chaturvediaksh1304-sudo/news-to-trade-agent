"""Thin wrapper over Ruflo memory calls, with a local JSON fallback.

Namespaces (per CLAUDE.md): fundamentals (7-day TTL), headline-cache,
sentiment-history, trade-reasoning, token-spend.
"""
from __future__ import annotations

import datetime
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

LOCAL_STORE = Path(__file__).parent / ".local"


def _ruflo_available() -> bool:
    return shutil.which("npx") is not None and (Path.cwd() / ".ruflo").exists()


class MemoryClient:
    def __init__(self, use_ruflo: bool | None = None) -> None:
        self.use_ruflo = _ruflo_available() if use_ruflo is None else use_ruflo

    def store(self, namespace: str, key: str, value: Any, ttl_days: int | None = None) -> None:
        if self.use_ruflo:
            subprocess.run(
                ["npx", "ruflo", "memory", "store", "--namespace", namespace,
                 "--key", key, "--value", json.dumps(value)],
                check=False, capture_output=True, timeout=30,
            )
            return
        path = LOCAL_STORE / namespace
        path.mkdir(parents=True, exist_ok=True)
        expires = (
            (datetime.date.today() + datetime.timedelta(days=ttl_days)).isoformat()
            if ttl_days
            else None
        )
        (path / f"{_safe(key)}.json").write_text(
            json.dumps({"value": value, "expires": expires})
        )

    def retrieve(self, namespace: str, key: str) -> Any | None:
        if self.use_ruflo:
            result = subprocess.run(
                ["npx", "ruflo", "memory", "retrieve", "--namespace", namespace, "--key", key],
                check=False, capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return None
            return None
        path = LOCAL_STORE / namespace / f"{_safe(key)}.json"
        if not path.exists():
            return None
        entry = json.loads(path.read_text())
        if entry["expires"] and datetime.date.fromisoformat(entry["expires"]) < datetime.date.today():
            path.unlink()
            return None
        return entry["value"]


def _safe(key: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
