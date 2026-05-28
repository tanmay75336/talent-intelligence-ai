from backend.utils.skill_taxonomy import get_group_matches


TESTING_TERMS = {
    "test",
    "testing",
    "unit test",
    "integration test",
    "pytest",
    "jest",
    "cypress",
    "qa",
}

CI_CD_TERMS = {
    "ci/cd",
    "ci cd",
    "pipeline",
    "github actions",
    "gitlab ci",
    "deployment pipeline",
    "release",
}

SCALE_TERMS = {
    "scale",
    "scalable",
    "distributed",
    "high traffic",
    "multi-service",
    "microservice",
    "performance",
    "reliability",
    "observability",
    "load",
}

OWNERSHIP_TERMS = {
    "owned",
    "led",
    "lead",
    "architected",
    "designed",
    "end-to-end",
    "mentored",
    "managed",
    "responsible",
}

CLOUD_ARCHITECTURE_TERMS = {
    "aws",
    "azure",
    "gcp",
    "kubernetes",
    "terraform",
    "cloud",
    "infrastructure",
    "architecture",
}


def _combined_profile_text(profile):
    sections = [
        profile.summary,
        profile.raw_text,
        "\n".join(profile.projects),
        "\n".join(profile.experience),
        "\n".join(profile.certifications),
    ]
    return "\n".join(section for section in sections if section).lower()


def _has_any(text, terms):
    return any(term in text for term in terms)


def _append_unique(items, value):
    if value and value not in items:
        items.append(value)


def _concern_limit(final_score):
    if final_score >= 85:
        return 2
    if final_score >= 70:
        return 3
    return 4


def _resume_evidence_is_thin(profile):
    evidence_sections = len(profile.projects) + len(profile.experience)
    return evidence_sections <= 1 or len((profile.raw_text or "").split()) < 120


def _soft_missing_skill_concern(missing_skills):
    if not missing_skills:
        return None

    if len(missing_skills) <= 3:
        return (
            "Some required technologies are implied contextually but not explicitly demonstrated: "
            + ", ".join(missing_skills)
            + "."
        )

    return "Some required technologies need explicit validation: " + ", ".join(missing_skills[:6]) + "."


def _build_nuanced_concerns(profile, jd_analysis, scorecard):
    text = _combined_profile_text(profile)
    final_score = scorecard.get("final_score", 0)
    keyword_score = scorecard.get("keyword_score", 0)
    semantic_score = scorecard.get("semantic_score", 0)
    project_score = scorecard.get("project_relevance_score", 0)
    deployment_score = scorecard.get("deployment_score", 0)
    ai_score = scorecard.get("ai_experience_score", 0)
    confidence_score = scorecard.get("confidence_score", 0)
    recruiter_confidence = scorecard.get("recruiter_confidence", "")
    missing_skills = scorecard.get("missing_skills", [])
    adjacent_matches = scorecard.get("adjacent_matches", [])
    ecosystem_matches = scorecard.get("ecosystem_matches", [])
    frontend_skills = get_group_matches(profile.skills, "frontend")
    backend_skills = get_group_matches(profile.skills, "backend")
    deployment_required = bool(jd_analysis.deployment_keywords)
    ai_required = bool(jd_analysis.ai_keywords)
    api_required = bool(jd_analysis.api_keywords)
    backend_expected = bool(get_group_matches(jd_analysis.all_skills, "backend") or api_required)
    concerns = []

    if jd_analysis.seniority_indicators and profile.seniority_band in {"student", "entry"}:
        if "senior" in jd_analysis.seniority_indicators:
            _append_unique(
                concerns,
                "Resume suggests an earlier-career profile than the role's seniority target.",
            )

    if missing_skills:
        if final_score >= 80:
            _append_unique(concerns, _soft_missing_skill_concern(missing_skills))
        elif final_score >= 75 and (adjacent_matches or ecosystem_matches):
            _append_unique(concerns, _soft_missing_skill_concern(missing_skills))
        elif final_score >= 70:
            _append_unique(
                concerns,
                "A few required technologies need explicit confirmation: "
                + ", ".join(missing_skills[:4])
                + ".",
            )
        else:
            _append_unique(
                concerns,
                "Direct requirement coverage is incomplete: " + ", ".join(missing_skills[:6]) + ".",
            )

    if (
        confidence_score < 55
        or recruiter_confidence == "Low"
        or (_resume_evidence_is_thin(profile) and final_score < 70)
    ):
        _append_unique(
            concerns,
            "Resume evidence quality limits full confidence in the technical assessment.",
        )

    if not _has_any(text, TESTING_TERMS):
        _append_unique(
            concerns,
            "Testing practices are not strongly demonstrated in the resume.",
        )

    if deployment_required and not _has_any(text, CI_CD_TERMS):
        _append_unique(
            concerns,
            "CI/CD ownership depth could not be fully verified.",
        )

    if backend_expected and not _has_any(text, SCALE_TERMS):
        _append_unique(
            concerns,
            "Large-scale distributed systems exposure is unclear.",
        )

    if backend_expected and frontend_skills and len(backend_skills) < 2:
        _append_unique(
            concerns,
            "Backend infrastructure ownership appears lighter than top-tier candidates.",
        )

    if deployment_required and deployment_score < 55:
        _append_unique(
            concerns,
            "Deployment and cloud evidence is limited for a role that calls for production delivery.",
        )
    elif deployment_required and not _has_any(text, CLOUD_ARCHITECTURE_TERMS):
        _append_unique(
            concerns,
            "Cloud architecture depth may require further interview validation.",
        )

    if ai_required and ai_score < 55:
        _append_unique(
            concerns,
            "AI-specific implementation evidence is lighter than the job description expects.",
        )

    if project_score < 60 and semantic_score >= 65:
        _append_unique(
            concerns,
            "Relevant experience appears plausible, but project-level depth is not strongly evidenced.",
        )

    if keyword_score < 50 and final_score < 70:
        _append_unique(
            concerns,
            "Direct keyword overlap is lighter than the strongest benchmark candidates.",
        )

    if not _has_any(text, OWNERSHIP_TERMS):
        _append_unique(
            concerns,
            "Ownership scope is not strongly represented in the resume.",
        )

    if "senior" in jd_analysis.seniority_indicators and "mentored" not in text and "mentor" not in text:
        _append_unique(
            concerns,
            "Leadership or mentoring scope is not strongly represented.",
        )

    if final_score >= 85:
        soft_concerns = [
            concern
            for concern in concerns
            if not concern.startswith("Direct requirement coverage is incomplete")
            and not concern.startswith("Several required technologies")
        ]
        concerns = soft_concerns or concerns

    if not concerns:
        concerns.append("Production scalability experience is not deeply evidenced.")

    return concerns[: _concern_limit(final_score)]


def build_recruiter_reasoning(profile, jd_analysis, scorecard):
    strengths = []

    matched_skills = scorecard.get("matched_skills", [])
    adjacent_matches = scorecard.get("adjacent_matches", [])
    ecosystem_matches = scorecard.get("ecosystem_matches", [])
    project_names = []

    for project in profile.projects[:2]:
        first_line = project.splitlines()[0].strip()
        if first_line:
            project_names.append(first_line)

    if matched_skills:
        strengths.append(
            "Strong direct overlap with required technologies: "
            + ", ".join(matched_skills[:6])
        )

    if scorecard["project_relevance_score"] >= 75:
        strengths.append(
            "Projects show strong role alignment with production-grade delivery and relevant technical scope"
            + (f", including {', '.join(project_names[:2])}." if project_names else ".")
        )

    if scorecard["semantic_score"] >= 72:
        strengths.append(
            "Candidate demonstrates strong contextual alignment with the role's responsibilities and delivery expectations."
        )

    if scorecard["deployment_score"] >= 65 and profile.deployment_signals:
        strengths.append(
            "Demonstrates deployment experience using "
            + ", ".join(profile.deployment_signals[:4])
            + "."
        )

    if scorecard["ai_experience_score"] >= 65 and profile.ai_signals:
        strengths.append(
            "Shows relevant AI-integrated product work across "
            + ", ".join(profile.ai_signals[:4])
            + "."
        )

    for match in adjacent_matches[:3]:
        strengths.append(
            f"Transferable expertise suggests ramp-up potential from {match['related_skill']} to {match['missing_skill']}."
        )

    for match in ecosystem_matches[:2]:
        strengths.append(
            f"Ecosystem overlap supports {match['missing_skill']} readiness through related experience in "
            + ", ".join(match["related_skills"][:3])
            + "."
        )

    if scorecard["hidden_gem_flag"]:
        recruiter_summary = (
            "Hidden gem profile with stronger project evidence and semantic alignment than the direct keyword match initially suggests."
        )
    elif scorecard["final_score"] >= 85:
        recruiter_summary = (
            "Candidate demonstrates strong AI-integrated full-stack alignment with credible delivery evidence and recruiter-ready role fit."
        )
    elif scorecard["final_score"] >= 70:
        recruiter_summary = (
            "Candidate shows believable alignment across core stack, shipped project work, and relevant implementation signals."
        )
    elif scorecard["final_score"] >= 50:
        recruiter_summary = (
            "Candidate looks like a credible adjacent fit with enough delivery evidence to justify recruiter review."
        )
    elif scorecard["project_relevance_score"] >= 70 or scorecard["semantic_score"] >= 70:
        recruiter_summary = (
            "Promising adjacent fit with solid contextual relevance, though some direct requirement coverage remains lighter."
        )
    else:
        recruiter_summary = (
            "Limited overall alignment against the current role requirements."
        )

    frontend_skills = get_group_matches(profile.skills, "frontend")
    backend_skills = get_group_matches(profile.skills, "backend")
    if len(frontend_skills) >= 2 and len(backend_skills) >= 2:
        strengths.append(
            "Demonstrates full-stack capability spanning both frontend and backend execution."
        )

    weaknesses = _build_nuanced_concerns(profile, jd_analysis, scorecard)

    return {
        "strengths": strengths[:6],
        "weaknesses": weaknesses,
        "recruiter_summary": recruiter_summary,
    }
