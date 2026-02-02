from __future__ import annotations

import os


def get_env(key: str, default: str) -> str:
    value = os.getenv(key)
    if value is None:
        return default
    return value


def get_bool_env(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
