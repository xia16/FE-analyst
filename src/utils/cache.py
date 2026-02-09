"""Simple file-based caching for API responses."""

import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from src.config import Paths, SETTINGS


class DataCache:
    """File-based cache with TTL support."""

    def __init__(self, category: str = "general"):
        self.cache_dir = Paths.DATA_CACHE / category
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        ttl_config = SETTINGS.get("cache", {}).get("ttl_hours", {})
        self.ttl_seconds = ttl_config.get(category, 24) * 3600

    def _key_path(self, key: str, ext: str = "json") -> Path:
        hashed = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hashed}.{ext}"

    def get(self, key: str) -> dict | None:
        """Retrieve cached JSON data if not expired."""
        path = self._key_path(key)
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > self.ttl_seconds:
            path.unlink()
            return None
        with open(path) as f:
            return json.load(f)

    def set(self, key: str, data: dict) -> None:
        """Store JSON data in cache."""
        path = self._key_path(key)
        with open(path, "w") as f:
            json.dump(data, f)

    def get_df(self, key: str) -> pd.DataFrame | None:
        """Retrieve cached DataFrame (parquet)."""
        path = self._key_path(key, ext="parquet")
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > self.ttl_seconds:
            path.unlink()
            return None
        return pd.read_parquet(path)

    def set_df(self, key: str, df: pd.DataFrame) -> None:
        """Store DataFrame as parquet."""
        path = self._key_path(key, ext="parquet")
        df.to_parquet(path)
