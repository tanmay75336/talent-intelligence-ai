from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

import pandas as pd

from backend.dataset_intelligence.models import FieldProfile, ProposedSignal, SignalInventoryItem


SIGNAL_KEYWORDS = {
    "skills": {"skill", "skills", "technology", "technologies", "stack", "tools", "competenc"},
    "titles": {"title", "headline", "role", "position", "designation", "current_job"},
    "experience": {"experience", "years", "employment", "work_history", "job_history", "company", "tenure"},
    "education": {"education", "degree", "university", "college", "school", "gpa"},
    "certifications": {"certification", "certificate", "license", "credential"},
    "endorsements": {"endorsement", "recommendation", "rating", "review", "referral"},
    "platform_activity": {"activity", "active", "login", "post", "comment", "contribution", "commit", "event"},
    "projects": {"project", "portfolio", "repository", "github", "demo", "case_study"},
    "achievements": {"achievement", "award", "impact", "outcome", "metric", "accomplishment"},
    "profile_completeness": {"completion", "completeness", "filled", "verified", "profile_quality"},
    "engagement_metrics": {"view", "click", "reply", "response", "engagement", "message", "application"},
    "behavioral_signals": {"collaboration", "leadership", "ownership", "initiative", "communication"},
    "career_progression": {"promotion", "progression", "seniority", "level", "manager", "lead", "principal"},
}


STRONG_SIGNAL_CATEGORIES = {
    "skills",
    "titles",
    "experience",
    "projects",
    "achievements",
    "career_progression",
}


def categorize_field(name: str, sample_values: Iterable[str] = ()) -> list[str]:
    text = f"{name} {' '.join(str(value) for value in sample_values)}".lower()
    categories = []
    for category, keywords in SIGNAL_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            categories.append(category)
    return categories


def build_signal_inventory(fields: list[FieldProfile]) -> list[SignalInventoryItem]:
    grouped: dict[str, list[FieldProfile]] = defaultdict(list)
    for field in fields:
        for category in field.signal_categories:
            grouped[category].append(field)

    inventory = []
    for category, category_fields in sorted(grouped.items()):
        coverage = _average([field.coverage_pct for field in category_fields])
        strong_fields = [
            field.name
            for field in category_fields
            if field.coverage_pct >= 60 and field.usefulness in {"strong", "moderate"}
        ]
        if strong_fields and category in STRONG_SIGNAL_CATEGORIES:
            strength = "strong"
        elif coverage >= 45:
            strength = "moderate"
        else:
            strength = "weak"
        inventory.append(
            SignalInventoryItem(
                category=category,
                fields=[field.name for field in category_fields],
                coverage_pct=round(coverage, 2),
                strength=strength,
                rationale=_inventory_rationale(category, strength, category_fields),
            )
        )
    return inventory


def propose_candidate_signals(fields: list[FieldProfile], inventory: list[SignalInventoryItem]) -> list[ProposedSignal]:
    by_category = {item.category: item for item in inventory}
    proposals = []

    if {"titles", "experience"} <= set(by_category):
        proposals.append(
            ProposedSignal(
                name="career_progression",
                source_fields=_fields_for_categories(fields, {"titles", "experience", "career_progression"}),
                description="Estimate whether titles and experience history show seniority growth over time.",
                readiness=_readiness(by_category, {"titles", "experience"}),
                caveat="Requires temporal ordering or role history to avoid over-interpreting title strings.",
            )
        )
    if "platform_activity" in by_category or "engagement_metrics" in by_category:
        proposals.append(
            ProposedSignal(
                name="activity_consistency",
                source_fields=_fields_for_categories(fields, {"platform_activity", "engagement_metrics"}),
                description="Measure consistency and recency of platform activity as a lightweight engagement signal.",
                readiness=_readiness(by_category, {"platform_activity", "engagement_metrics"}),
                caveat="Activity can reflect platform usage bias rather than candidate quality.",
            )
        )
    if "profile_completeness" in by_category or len([field for field in fields if field.coverage_pct >= 80]) >= 4:
        proposals.append(
            ProposedSignal(
                name="profile_quality",
                source_fields=_fields_for_categories(fields, {"profile_completeness", "skills", "projects", "experience"}),
                description="Use completeness across core candidate fields to flag richer profiles versus sparse records.",
                readiness="ready" if any("profile_completeness" in field.signal_categories for field in fields) else "partial",
                caveat="Completeness should affect confidence, not become a proxy for candidate merit.",
            )
        )
    if "skills" in by_category and ("projects" in by_category or "experience" in by_category):
        proposals.append(
            ProposedSignal(
                name="specialization_depth",
                source_fields=_fields_for_categories(fields, {"skills", "projects", "experience"}),
                description="Detect whether skills are reinforced by project or experience evidence instead of appearing only as tags.",
                readiness=_readiness(by_category, {"skills", "projects", "experience"}),
                caveat="Requires linking skill mentions to evidence-bearing text fields.",
            )
        )
    if "skills" in by_category:
        proposals.append(
            ProposedSignal(
                name="breadth_vs_depth",
                source_fields=_fields_for_categories(fields, {"skills", "projects", "certifications"}),
                description="Distinguish broad skill inventories from focused skill clusters with supporting evidence.",
                readiness="partial",
                caveat="Broad profiles can be valuable; do not penalize breadth without role context.",
            )
        )
    return _dedupe_proposals(proposals)


def _fields_for_categories(fields: list[FieldProfile], categories: set[str]) -> list[str]:
    selected = []
    for field in fields:
        if categories & set(field.signal_categories):
            selected.append(field.name)
    return selected[:8]


def _readiness(inventory: dict[str, SignalInventoryItem], categories: set[str]) -> str:
    strengths = [inventory[category].strength for category in categories if category in inventory]
    if strengths and all(strength in {"strong", "moderate"} for strength in strengths):
        return "ready"
    if strengths:
        return "partial"
    return "not_ready"


def _inventory_rationale(category: str, strength: str, fields: list[FieldProfile]) -> str:
    field_names = ", ".join(field.name for field in fields[:3])
    if strength == "strong":
        return f"{category.replace('_', ' ')} appears usable because {field_names} have meaningful coverage and signal-like content."
    if strength == "moderate":
        return f"{category.replace('_', ' ')} may be useful, but coverage or field quality should be checked before ranking use."
    return f"{category.replace('_', ' ')} is present but currently too sparse or noisy for direct ranking use."


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _dedupe_proposals(proposals: list[ProposedSignal]) -> list[ProposedSignal]:
    seen = set()
    deduped = []
    for proposal in proposals:
        key = re.sub(r"[^a-z0-9]+", "_", proposal.name.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(proposal)
    return deduped

