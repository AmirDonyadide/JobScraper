"""Compatibility wrapper for the Indeed provider."""

from __future__ import annotations

from jobfinder.providers.indeed import (
    INDEED_DOMAIN_BY_COUNTRY,
    INDEED_MAX_LIMIT,
    IndeedActorInput,
    IndeedMetadata,
    base_url,
    build_actor_input,
    build_metadata,
    clamp_actor_limit,
    date_posted_filter,
    description_with_metadata,
    indeed_job_key,
    normalize_actor_item,
    normalize_actor_output,
    run_actor_search,
)

__all__ = [
    "INDEED_DOMAIN_BY_COUNTRY",
    "INDEED_MAX_LIMIT",
    "IndeedActorInput",
    "IndeedMetadata",
    "base_url",
    "build_actor_input",
    "build_metadata",
    "clamp_actor_limit",
    "date_posted_filter",
    "description_with_metadata",
    "indeed_job_key",
    "normalize_actor_item",
    "normalize_actor_output",
    "run_actor_search",
]
