"""Loads the local agent configuration from config.json."""

from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"config.json not found at {_CONFIG_PATH}. "
            "Copy config.json.example, rename it to config.json, and set your repo path."
        )
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
