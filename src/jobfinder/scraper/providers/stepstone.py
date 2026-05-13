"""Compatibility wrapper for the Stepstone provider."""

from __future__ import annotations

from jobfinder.providers.stepstone import (
    STEPSTONE_BASE_URL,
    StepstoneActorInput,
    StepstoneMetadata,
    absolute_stepstone_url,
    build_actor_input,
    build_direct_actor_input,
    build_metadata,
    normalize_actor_item,
    normalize_actor_output,
    posted_within_filter,
    run_actor_search,
    slugify_segment,
)

__all__ = [
    "STEPSTONE_BASE_URL",
    "StepstoneActorInput",
    "StepstoneMetadata",
    "absolute_stepstone_url",
    "build_actor_input",
    "build_direct_actor_input",
    "build_metadata",
    "normalize_actor_item",
    "normalize_actor_output",
    "posted_within_filter",
    "run_actor_search",
    "slugify_segment",
]
