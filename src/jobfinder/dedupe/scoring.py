"""Deterministic similarity scoring for job duplicate detection."""

from __future__ import annotations

from difflib import SequenceMatcher

from jobfinder.dedupe.models import NormalizedJob, SalaryRange

SENIORITY_TOKENS = {
    "intern",
    "junior",
    "jr",
    "senior",
    "sr",
    "lead",
    "principal",
    "staff",
    "head",
    "director",
    "manager",
}
ROLE_FAMILY_TOKENS = {
    "administrator",
    "analyst",
    "analytics",
    "architect",
    "consultant",
    "developer",
    "engineer",
    "manager",
    "scientist",
    "specialist",
}


def sequence_similarity(left: str, right: str) -> float:
    """Return a deterministic normalized string similarity."""
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def token_overlap(left: frozenset[str], right: frozenset[str]) -> float:
    """Return Jaccard token overlap."""
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def blended_text_similarity(
    left_text: str,
    right_text: str,
    left_tokens: frozenset[str],
    right_tokens: frozenset[str],
) -> float:
    """Blend sequence and token similarity for explainable matching."""
    if left_text == right_text and left_text:
        return 1.0
    return max(
        sequence_similarity(left_text, right_text),
        (0.65 * token_overlap(left_tokens, right_tokens))
        + (0.35 * sequence_similarity(left_text, right_text)),
    )


def company_similarity(left: NormalizedJob, right: NormalizedJob) -> float:
    """Score normalized company similarity."""
    return blended_text_similarity(
        left.normalized_company,
        right.normalized_company,
        left.company_tokens,
        right.company_tokens,
    )


def title_similarity(left: NormalizedJob, right: NormalizedJob) -> float:
    """Score normalized title similarity."""
    return blended_text_similarity(
        left.normalized_title,
        right.normalized_title,
        left.title_tokens,
        right.title_tokens,
    )


def location_similarity(left: NormalizedJob, right: NormalizedJob) -> float:
    """Score normalized location compatibility."""
    if not left.normalized_location or not right.normalized_location:
        return 0.35
    if left.normalized_location == right.normalized_location:
        return 1.0
    if left.location_tokens and right.location_tokens:
        if (
            left.location_tokens <= right.location_tokens
            or right.location_tokens <= left.location_tokens
        ):
            return 0.92
    if left.remote_mode and right.remote_mode and left.remote_mode == right.remote_mode:
        return 0.82
    return blended_text_similarity(
        left.normalized_location,
        right.normalized_location,
        left.location_tokens,
        right.location_tokens,
    )


def description_similarity(left: NormalizedJob, right: NormalizedJob) -> float:
    """Score description overlap cheaply from already-normalized tokens."""
    if not left.description or not right.description:
        return 0.0
    left_tokens = frozenset(left.description.casefold().split())
    right_tokens = frozenset(right.description.casefold().split())
    return token_overlap(left_tokens, right_tokens)


def salary_overlap(left: SalaryRange, right: SalaryRange) -> bool:
    """Return true when two parsed salary ranges overlap."""
    if left.minimum is None and left.maximum is None:
        return False
    if right.minimum is None and right.maximum is None:
        return False
    left_min = left.minimum if left.minimum is not None else left.maximum
    left_max = left.maximum if left.maximum is not None else left.minimum
    right_min = right.minimum if right.minimum is not None else right.maximum
    right_max = right.maximum if right.maximum is not None else right.minimum
    if left_min is None or left_max is None or right_min is None or right_max is None:
        return False
    return max(left_min, right_min) <= min(left_max, right_max)


def salary_similarity(left: NormalizedJob, right: NormalizedJob) -> float:
    """Score salary proximity when both sides expose comparable salary data."""
    left_salary = left.salary
    right_salary = right.salary
    if left_salary.midpoint is None or right_salary.midpoint is None:
        return 0.0
    if (
        left_salary.currency
        and right_salary.currency
        and left_salary.currency != right_salary.currency
    ):
        return 0.0
    if (
        left_salary.period
        and right_salary.period
        and left_salary.period != right_salary.period
    ):
        return 0.0
    if salary_overlap(left_salary, right_salary):
        return 1.0

    midpoint = max(left_salary.midpoint, right_salary.midpoint)
    if midpoint <= 0:
        return 0.0
    distance = abs(left_salary.midpoint - right_salary.midpoint) / midpoint
    if distance <= 0.10:
        return 0.9
    if distance <= 0.20:
        return 0.7
    if distance <= 0.35:
        return 0.45
    return 0.0


def posting_date_similarity(left: NormalizedJob, right: NormalizedJob) -> float:
    """Score posting dates; stale mismatches are weak evidence, not identity."""
    if left.posted_at is None or right.posted_at is None:
        return 0.0
    days = abs((left.posted_at - right.posted_at).total_seconds()) / 86_400
    if days <= 3:
        return 1.0
    if days <= 14:
        return 0.75
    if days <= 45:
        return 0.35
    return 0.0


def conflicting_seniority(left: NormalizedJob, right: NormalizedJob) -> bool:
    """Return true when role seniority clearly differs."""
    left_tokens = left.title_tokens & SENIORITY_TOKENS
    right_tokens = right.title_tokens & SENIORITY_TOKENS
    if not left_tokens or not right_tokens:
        return False
    junior = {"intern", "junior", "jr"}
    senior = {"senior", "sr", "lead", "principal", "staff", "head", "director"}
    return bool(
        (left_tokens & junior and right_tokens & senior)
        or (right_tokens & junior and left_tokens & senior)
    )


def conflicting_role_family(left: NormalizedJob, right: NormalizedJob) -> bool:
    """Return true for titles that share weak words but name different roles."""
    left_family = left.title_tokens & ROLE_FAMILY_TOKENS
    right_family = right.title_tokens & ROLE_FAMILY_TOKENS
    if not left_family or not right_family:
        return False
    return left_family.isdisjoint(right_family)


def significant_salary_conflict(left: NormalizedJob, right: NormalizedJob) -> bool:
    """Return true when comparable salaries are too far apart for a safe merge."""
    if left.salary.midpoint is None or right.salary.midpoint is None:
        return False
    if (
        left.salary.currency
        and right.salary.currency
        and left.salary.currency != right.salary.currency
    ):
        return True
    if (
        left.salary.period
        and right.salary.period
        and left.salary.period != right.salary.period
    ):
        return True
    if salary_overlap(left.salary, right.salary):
        return False
    midpoint = max(left.salary.midpoint, right.salary.midpoint)
    if midpoint <= 0:
        return False
    return abs(left.salary.midpoint - right.salary.midpoint) / midpoint > 0.35


def weighted_confidence(
    left: NormalizedJob, right: NormalizedJob
) -> tuple[float, dict[str, float]]:
    """Return the weighted deterministic match confidence and component scores."""
    components = {
        "company": company_similarity(left, right),
        "title": title_similarity(left, right),
        "location": location_similarity(left, right),
        "description": description_similarity(left, right),
        "salary": salary_similarity(left, right),
        "posted": posting_date_similarity(left, right),
    }
    confidence = (
        (0.32 * components["company"])
        + (0.36 * components["title"])
        + (0.16 * components["location"])
        + (0.06 * components["description"])
        + (0.06 * components["salary"])
        + (0.04 * components["posted"])
    )
    if left.company_url_key and left.company_url_key == right.company_url_key:
        confidence += 0.03
    if left.apply_url_key and left.apply_url_key == right.apply_url_key:
        confidence += 0.05
    return min(confidence, 1.0), components
