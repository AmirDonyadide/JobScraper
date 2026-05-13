"""Compatibility exports for the stable LinkedIn provider."""

from __future__ import annotations

from jobfinder.scraper.providers.linkedin import (
    build_actor_input,
    build_batch_actor_input,
    build_search_url,
)

__all__ = [
    "build_actor_input",
    "build_batch_actor_input",
    "build_search_url",
]
