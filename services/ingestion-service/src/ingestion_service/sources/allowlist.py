"""Source allowlist configuration loader and validator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ingestion_service.config import settings


@dataclass(frozen=True)
class AllowedSource:
    """Specification of an authorized external data provider."""

    id: str
    name: str
    host: str
    path_prefix: str
    license: str
    terms_note: str
    max_size_bytes: int
    allowed_drivers: list[str] = field(default_factory=lambda: ["GTiff", "GeoTIFF"])


class SourceAllowlist:
    """Manages verified external data sources."""

    def __init__(self, sources_path: str | Path | None = None) -> None:
        self.path = Path(sources_path or settings.allowed_sources_path)
        self._sources: dict[str, AllowedSource] = {}
        self.load()

    def load(self) -> None:
        """Load sources from YAML configuration file."""
        if not self.path.exists():
            self._sources = {}
            return

        with self.path.open("r", encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}

        sources_raw = data.get("sources", [])
        loaded: dict[str, AllowedSource] = {}
        for s in sources_raw:
            source = AllowedSource(
                id=str(s["id"]),
                name=str(s["name"]),
                host=str(s["host"]).lower(),
                path_prefix=str(s.get("path_prefix", "/")),
                license=str(s.get("license", "")),
                terms_note=str(s.get("terms_note", "")),
                max_size_bytes=int(s.get("max_size_bytes", 524_288_000)),
                allowed_drivers=list(s.get("allowed_drivers", ["GTiff", "GeoTIFF"])),
            )
            loaded[source.id] = source
        self._sources = loaded

    def get(self, source_id: str) -> AllowedSource | None:
        """Retrieve allowed source by ID."""
        return self._sources.get(source_id)

    def list_sources(self) -> list[AllowedSource]:
        """Return all configured allowed sources."""
        return list(self._sources.values())


_allowlist_instance: SourceAllowlist | None = None


def get_allowlist() -> SourceAllowlist:
    """Singleton getter for SourceAllowlist."""
    global _allowlist_instance
    if _allowlist_instance is None:
        _allowlist_instance = SourceAllowlist()
    return _allowlist_instance
