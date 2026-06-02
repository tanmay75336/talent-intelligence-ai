from __future__ import annotations

from typing import Any

from backend.models.candidate_profile import CandidateProfile
from backend.utils.skill_taxonomy import get_group_matches, normalize_whitespace, unique_preserve_order


def adapt_redrob_candidate(candidate: dict[str, Any]) -> CandidateProfile:
    candidate_id = str(candidate.get("candidate_id") or "").strip()
    profile = _dict(candidate.get("profile"))
    career_history = _list_of_dicts(candidate.get("career_history"))
    education_records = _list_of_dicts(candidate.get("education"))
    skill_records = _list_of_dicts(candidate.get("skills"))
    certification_records = _list_of_dicts(candidate.get("certifications"))
    redrob_signals = _dict(candidate.get("redrob_signals"))

    skill_names = unique_preserve_order(
        str(skill.get("name") or "").strip()
        for skill in skill_records
        if str(skill.get("name") or "").strip()
    )
    experience = [_format_career_item(item) for item in career_history]
    education = [_format_education_item(item) for item in education_records]
    certifications = [_format_certification_item(item) for item in certification_records]
    searchable_profile_text = build_searchable_profile_text(
        profile=profile,
        career_history=career_history,
        skills=skill_records,
        certifications=certification_records,
    )

    sections = {
        "profile": _join_clean(
            [
                profile.get("headline"),
                profile.get("summary"),
                profile.get("current_title"),
                profile.get("current_company"),
                profile.get("current_industry"),
                profile.get("location"),
                profile.get("country"),
            ]
        ),
        "experience": "\n".join(experience),
        "education": "\n".join(education),
        "skills": ", ".join(_format_skill_item(item) for item in skill_records if item.get("name")),
        "certifications": "\n".join(certifications),
    }

    years_of_experience = _float(profile.get("years_of_experience"))
    return CandidateProfile(
        candidate_id=candidate_id,
        name=str(profile.get("anonymized_name") or candidate_id or "Unknown Candidate"),
        raw_text=searchable_profile_text,
        source_name=candidate_id,
        summary=_join_clean([profile.get("headline"), profile.get("summary")]),
        skills=skill_names,
        skill_records=skill_records,
        projects=[],
        experience=experience,
        career_history=career_history,
        education=education,
        education_records=education_records,
        certifications=certifications,
        certification_records=certification_records,
        sections={key: value for key, value in sections.items() if value},
        deployment_signals=get_group_matches(skill_names, "deployment"),
        ai_signals=get_group_matches(skill_names, "ai"),
        api_signals=get_group_matches(skill_names, "api"),
        years_of_experience=years_of_experience,
        seniority_band=_infer_seniority(profile.get("current_title"), years_of_experience),
        searchable_profile_text=searchable_profile_text,
        redrob_signals=redrob_signals,
        raw_candidate=candidate,
        structured_profile=profile,
    )


def build_searchable_profile_text(
    profile: dict[str, Any],
    career_history: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    certifications: list[dict[str, Any]],
) -> str:
    parts: list[str] = []
    parts.extend([profile.get("headline"), profile.get("summary")])
    parts.extend(item.get("description") for item in career_history)
    parts.extend(_format_skill_item(item) for item in skills if item.get("name"))
    parts.extend(_format_certification_item(item) for item in certifications)
    return _join_clean(parts)


def _format_career_item(item: dict[str, Any]) -> str:
    header = _join_clean(
        [
            item.get("title"),
            item.get("company"),
            item.get("industry"),
            item.get("company_size"),
            _duration_text(item.get("duration_months")),
        ],
        separator=" | ",
    )
    description = normalize_whitespace(str(item.get("description") or ""))
    return _join_clean([header, description])


def _format_education_item(item: dict[str, Any]) -> str:
    years = _join_clean([item.get("start_year"), item.get("end_year")], separator="-")
    return _join_clean(
        [
            item.get("degree"),
            item.get("field_of_study"),
            item.get("institution"),
            years,
            item.get("grade"),
            item.get("tier"),
        ],
        separator=" | ",
    )


def _format_skill_item(item: dict[str, Any]) -> str:
    return _join_clean(
        [
            item.get("name"),
            item.get("proficiency"),
            _endorsement_text(item.get("endorsements")),
            _duration_text(item.get("duration_months")),
        ],
        separator=" | ",
    )


def _format_certification_item(item: dict[str, Any]) -> str:
    return _join_clean([item.get("name"), item.get("issuer"), item.get("year")], separator=" | ")


def _join_clean(parts, separator: str = " ") -> str:
    cleaned = [normalize_whitespace(str(part)) for part in parts if part not in (None, "")]
    return separator.join(part for part in cleaned if part)


def _duration_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    return f"{value} months"


def _endorsement_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    return f"{value} endorsements"


def _infer_seniority(title: Any, years_of_experience: float) -> str:
    lowered = str(title or "").lower()
    if years_of_experience >= 6 or any(term in lowered for term in ("senior", "lead", "staff", "principal")):
        return "senior"
    if years_of_experience >= 3 or "mid" in lowered:
        return "mid"
    if any(term in lowered for term in ("junior", "intern", "associate")):
        return "entry"
    if years_of_experience > 0:
        return "entry"
    return "unknown"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
