"""Deterministic cross-provider duplicate matching pipeline."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from jobfinder.dedupe.merge import merge_cluster
from jobfinder.dedupe.models import DedupeResult, MatchDecision, NormalizedJob
from jobfinder.dedupe.normalize import normalize_job
from jobfinder.dedupe.scoring import (
    company_similarity,
    conflicting_role_family,
    conflicting_seniority,
    location_similarity,
    significant_salary_conflict,
    title_similarity,
    weighted_confidence,
)

LOGGER = logging.getLogger("jobfinder.dedupe")
MATCH_THRESHOLD = 0.90
PROFILE_MATCH_CONFIDENCE = 0.96


def hard_blockers(left: NormalizedJob, right: NormalizedJob) -> list[str]:
    """Return deterministic reasons that prevent a heuristic merge."""
    blockers: list[str] = []
    if conflicting_seniority(left, right):
        blockers.append("conflicting title seniority")
    if conflicting_role_family(left, right):
        blockers.append("conflicting role family")
    if significant_salary_conflict(left, right):
        blockers.append("salary ranges differ significantly")
    if company_similarity(left, right) < 0.82:
        blockers.append("company similarity below threshold")
    if title_similarity(left, right) < 0.72:
        blockers.append("title similarity below threshold")
    if location_similarity(left, right) < 0.55:
        blockers.append("location similarity below threshold")
    if (
        left.source == right.source
        and left.job_id
        and right.job_id
        and left.job_id.casefold() != right.job_id.casefold()
        and not (left.apply_url_key and left.apply_url_key == right.apply_url_key)
    ):
        blockers.append("same provider has different source-native ids")
    return blockers


def strong_identity_match(
    left: NormalizedJob, right: NormalizedJob
) -> MatchDecision | None:
    """Return a stage-1 decision when high-confidence identifiers match."""
    soft_blockers = [
        blocker
        for blocker in hard_blockers(left, right)
        if blocker
        not in {
            "company similarity below threshold",
            "title similarity below threshold",
            "location similarity below threshold",
        }
    ]
    if (
        left.source == right.source
        and left.job_id
        and left.job_id.casefold() == right.job_id.casefold()
    ):
        return MatchDecision(
            left.index,
            right.index,
            True,
            1.0,
            "strong_identity",
            (f"same {left.source} job id",),
        )

    if (
        left.source == right.source
        and left.job_url_key
        and left.job_url_key == right.job_url_key
    ):
        return MatchDecision(
            left.index,
            right.index,
            True,
            1.0,
            "strong_identity",
            (f"same {left.source} canonical job URL",),
        )

    if left.apply_url_key and left.apply_url_key == right.apply_url_key:
        return MatchDecision(
            left.index,
            right.index,
            True,
            0.99,
            "strong_identity",
            ("same canonical external apply URL",),
        )

    if soft_blockers:
        return MatchDecision(
            left.index,
            right.index,
            False,
            0.0,
            "blocked",
            (),
            tuple(soft_blockers),
        )

    if (
        left.company_url_key
        and left.company_url_key == right.company_url_key
        and left.normalized_title
        and left.normalized_title == right.normalized_title
        and location_similarity(left, right) >= 0.82
    ):
        return MatchDecision(
            left.index,
            right.index,
            True,
            0.98,
            "strong_identity",
            ("same company URL, title, and compatible location",),
        )

    return None


def canonical_profile_match(
    left: NormalizedJob, right: NormalizedJob
) -> MatchDecision | None:
    """Return a stage-2 exact canonical-profile decision when safe."""
    if not left.profile_key or left.profile_key != right.profile_key:
        return None

    blockers = hard_blockers(left, right)
    if blockers:
        return MatchDecision(
            left.index,
            right.index,
            False,
            0.0,
            "blocked",
            (),
            tuple(blockers),
        )
    return MatchDecision(
        left.index,
        right.index,
        True,
        PROFILE_MATCH_CONFIDENCE,
        "canonical_profile",
        ("same normalized company, title, and location",),
    )


def heuristic_match(left: NormalizedJob, right: NormalizedJob) -> MatchDecision:
    """Score a possible duplicate using deterministic weighted components."""
    blockers = hard_blockers(left, right)
    confidence, components = weighted_confidence(left, right)
    reasons = tuple(
        f"{name}={score:.2f}" for name, score in components.items() if score > 0
    )
    if blockers:
        return MatchDecision(
            left.index,
            right.index,
            False,
            confidence,
            "heuristic",
            reasons,
            tuple(blockers),
        )
    return MatchDecision(
        left.index,
        right.index,
        confidence >= MATCH_THRESHOLD,
        confidence,
        "heuristic",
        reasons,
        (),
    )


def evaluate_match(left: NormalizedJob, right: NormalizedJob) -> MatchDecision:
    """Run all deterministic matching stages for a pair."""
    strong = strong_identity_match(left, right)
    if strong is not None:
        return strong
    profile = canonical_profile_match(left, right)
    if profile is not None:
        return profile
    return heuristic_match(left, right)


def best_cluster_match(
    job: NormalizedJob,
    cluster: list[NormalizedJob],
) -> MatchDecision:
    """Return the best pairwise decision between a job and a cluster."""
    decisions = [evaluate_match(job, existing) for existing in cluster]
    matched = [decision for decision in decisions if decision.matched]
    if matched:
        return max(matched, key=lambda decision: decision.confidence)
    return max(decisions, key=lambda decision: decision.confidence)


def flatten_search_results(
    all_results: list[tuple[str, list[dict[str, Any]]]],
) -> list[NormalizedJob]:
    """Flatten keyword search output and precompute matching features."""
    normalized: list[NormalizedJob] = []
    index = 0
    for keyword, jobs in all_results:
        for job in jobs:
            normalized.append(normalize_job(job, keyword=keyword, index=index))
            index += 1
    return normalized


def deduplicate_search_results(
    all_results: list[tuple[str, list[dict[str, Any]]]],
    *,
    include_debug: bool = False,
) -> DedupeResult:
    """Deduplicate scraped jobs using indexed deterministic matching."""
    clusters: list[list[NormalizedJob]] = []
    blocking_index: dict[str, set[int]] = defaultdict(set)
    decisions: list[MatchDecision] = []

    for job in flatten_search_results(all_results):
        candidate_cluster_ids: set[int] = set()
        for key in job.blocking_keys:
            candidate_cluster_ids.update(blocking_index.get(key, set()))

        best_decision: MatchDecision | None = None
        best_cluster_id: int | None = None
        for cluster_id in sorted(candidate_cluster_ids):
            decision = best_cluster_match(job, clusters[cluster_id])
            decisions.append(decision)
            if include_debug and not decision.matched:
                LOGGER.debug(
                    "Not merging job %s with cluster %s: confidence=%.2f "
                    "stage=%s blockers=%s reasons=%s",
                    job.index,
                    cluster_id,
                    decision.confidence,
                    decision.stage,
                    "; ".join(decision.blockers),
                    "; ".join(decision.reasons),
                )
            if not decision.matched:
                continue
            if best_decision is None or decision.confidence > best_decision.confidence:
                best_decision = decision
                best_cluster_id = cluster_id

        if best_cluster_id is None:
            cluster_id = len(clusters)
            clusters.append([job])
        else:
            cluster_id = best_cluster_id
            clusters[cluster_id].append(job)
            if best_decision is not None:
                LOGGER.debug(
                    "Merged job %s into cluster %s: confidence=%.2f "
                    "stage=%s reasons=%s",
                    job.index,
                    cluster_id,
                    best_decision.confidence,
                    best_decision.stage,
                    "; ".join(best_decision.reasons),
                )

        for key in job.blocking_keys:
            blocking_index[key].add(cluster_id)

    jobs = [merge_cluster(cluster) for cluster in clusters]
    return DedupeResult(
        jobs=jobs,
        decisions=decisions,
        input_count=sum(len(jobs) for _, jobs in all_results),
        output_count=len(jobs),
    )
