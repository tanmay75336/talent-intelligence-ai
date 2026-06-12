from backend.parsers.jd_analyzer import analyze_job_description
from backend.parsers.resume_parser import build_candidate_profile
from backend.ranking.pipeline import rank_candidate_text
from backend.ranking.scoring_engine import score_candidate_profile


def score_text_profile(resume_text, jd_text, candidate_name="Debug Candidate"):
    try:
        ranked = rank_candidate_text(resume_text, jd_text, source_name=candidate_name)
        job_intelligence = ranked.get("job_intelligence", {})
        return {
            "candidate_name": ranked["candidate_name"],
            "candidate_skills": ranked.get("candidate_skills", []),
            "jd_required_skills": job_intelligence.get("explicit_skills", []),
            "scorecard": ranked["ranking"],
        }
    except Exception:
        profile = build_candidate_profile(resume_text, source_name=candidate_name)
        jd_analysis = analyze_job_description(jd_text)
        scorecard = score_candidate_profile(profile, jd_analysis)

        return {
            "candidate_name": profile.name,
            "candidate_skills": profile.skills,
            "jd_required_skills": jd_analysis.required_skills,
            "scorecard": scorecard,
        }


def build_debug_report(resume_text, jd_text, candidate_name="Debug Candidate"):
    result = score_text_profile(resume_text, jd_text, candidate_name=candidate_name)
    scorecard = result["scorecard"]
    diagnostics = scorecard.get("scoring_diagnostics", {})
    component_scores = diagnostics.get("component_scores", {})
    adjustments = diagnostics.get("adjustments", {})
    semantic_details = diagnostics.get("semantic_details", {})
    retrieval_diagnostics = semantic_details.get("retrieval_diagnostics", {})
    coverage_metrics = diagnostics.get("coverage_metrics", {})

    return {
        "candidate_name": result["candidate_name"],
        "candidate_skills": result["candidate_skills"],
        "jd_required_skills": result["jd_required_skills"],
        "final_score": scorecard.get("final_score"),
        "recommendation": scorecard.get("recommendation"),
        "semantic_score": scorecard.get("semantic_score"),
        "keyword_score": scorecard.get("keyword_score"),
        "project_relevance_score": scorecard.get("project_relevance_score"),
        "deployment_score": scorecard.get("deployment_score"),
        "ai_experience_score": scorecard.get("ai_experience_score"),
        "adjacency_bonus": scorecard.get("adjacency_bonus"),
        "component_scores": component_scores,
        "coverage_metrics": coverage_metrics,
        "semantic_details": semantic_details,
        "retrieval_diagnostics": retrieval_diagnostics,
        "must_have_coverage": retrieval_diagnostics.get("must_have_coverage", {}),
        "must_have_suppression": retrieval_diagnostics.get("must_have_suppression", {}),
        "normalization_adjustments": adjustments,
        "strengths": scorecard.get("strengths", []),
        "weaknesses": scorecard.get("weaknesses", []),
        "recruiter_summary": scorecard.get("recruiter_summary"),
    }


def print_debug_report(report):
    print(f"Candidate: {report['candidate_name']}")
    print(f"Final Score: {report['final_score']} | Recommendation: {report['recommendation']}")
    print(
        "Component Scores:",
        {
            "semantic_score": report["semantic_score"],
            "keyword_score": report["keyword_score"],
            "project_relevance_score": report["project_relevance_score"],
            "deployment_score": report["deployment_score"],
            "ai_experience_score": report["ai_experience_score"],
            "adjacency_bonus": report["adjacency_bonus"],
        },
    )
    print("Normalization Adjustments:", report["normalization_adjustments"])
    print("Coverage Metrics:", report.get("coverage_metrics", {}))
    print("Semantic Details:", report["semantic_details"])
    print("Must-have Coverage:", report.get("must_have_coverage", {}))
    print("Must-have Suppression:", report.get("must_have_suppression", {}))
    retrieval_diagnostics = report.get("retrieval_diagnostics", {})
    pillar_debug = retrieval_diagnostics.get("pillars", {}) if isinstance(retrieval_diagnostics, dict) else {}
    for pillar in ("semantic_fit", "transferability", "execution_maturity"):
        details = pillar_debug.get(pillar, {})
        if not details:
            continue
        print(f"{pillar} Dense Rankings:", details.get("dense_rankings", [])[:3])
        print(f"{pillar} Sparse Rankings:", details.get("sparse_rankings", [])[:3])
        print(f"{pillar} Fused Rankings:", details.get("fused_rankings", [])[:3])
        print(f"{pillar} Suppressed Evidence:", details.get("suppressed_evidence", [])[:3])
    print("Strengths:", report["strengths"])
    print("Weaknesses:", report["weaknesses"])
    print("Summary:", report["recruiter_summary"])


def run_evaluation_suite(test_cases):
    results = []

    for case in test_cases:
        report = build_debug_report(
            case.resume_text,
            case.jd_text,
            candidate_name=case.name,
        )
        score = report["final_score"] or 0
        passed = case.expected_min_score <= score <= case.expected_max_score
        results.append(
            {
                "name": case.name,
                "expected_band": case.expected_band,
                "expected_range": [case.expected_min_score, case.expected_max_score],
                "actual_score": score,
                "recommendation": report["recommendation"],
                "passed": passed,
            }
        )

    return results


if __name__ == "__main__":
    from backend.evaluation_test_cases import EVALUATION_TEST_CASES

    first_case = EVALUATION_TEST_CASES[0]
    debug_report = build_debug_report(
        first_case.resume_text,
        first_case.jd_text,
        candidate_name=first_case.name,
    )
    print_debug_report(debug_report)
    print(run_evaluation_suite(EVALUATION_TEST_CASES))
