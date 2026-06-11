from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
DEFAULT_USER_AGENT = "TalentIntelligenceAI/1.0 (+https://localhost)"


@dataclass(frozen=True)
class GroqSynthesisStatus:
    enabled: bool
    status: str
    reason: str
    model: str

    def diagnostics(self) -> dict:
        return {
            "enabled": self.enabled,
            "status": self.status,
            "reason": self.reason,
            "model": self.model,
        }


def groq_synthesis_enabled() -> bool:
    return get_groq_synthesis_status().enabled


def get_groq_synthesis_status() -> GroqSynthesisStatus:
    enabled_raw = _env_value("ENABLE_GROQ_SYNTHESIS", "")
    explicit_enabled = enabled_raw.lower() in {"1", "true", "yes", "on"}
    explicit_disabled = enabled_raw.lower() in {"0", "false", "no", "off"}
    model = _env_value("GROQ_SYNTHESIS_MODEL", DEFAULT_GROQ_MODEL)
    api_key = _env_value("GROQ_API_KEY", "")
    if explicit_disabled:
        return GroqSynthesisStatus(False, "disabled", "ENABLE_GROQ_SYNTHESIS is false.", model)
    if not api_key:
        if explicit_enabled:
            return GroqSynthesisStatus(False, "misconfigured", "GROQ_API_KEY is not configured.", model)
        return GroqSynthesisStatus(False, "disabled", "GROQ_API_KEY is not configured; synthesis disabled.", model)
    if not model:
        return GroqSynthesisStatus(False, "misconfigured", "GROQ_SYNTHESIS_MODEL is empty.", model)
    return GroqSynthesisStatus(True, "configured", "Groq synthesis is configured.", model)


def log_groq_synthesis_startup_status() -> None:
    status = get_groq_synthesis_status()
    if status.status == "configured":
        logger.info("Groq synthesis configured with model %s.", status.model)
    elif status.status == "misconfigured":
        logger.warning("Groq synthesis unavailable: %s", status.reason)
    else:
        logger.info("Groq synthesis disabled: %s", status.reason)


def apply_optional_groq_synthesis(ranked_candidates: list[dict], processing_errors: list[str] | None = None) -> None:
    status = get_groq_synthesis_status()
    _annotate_synthesis_status(ranked_candidates, status, overwrite=True)
    if not status.enabled:
        if status.status == "misconfigured" and processing_errors is not None:
            processing_errors.append(f"AI synthesis skipped: {status.reason}")
        return

    failure_reason = ""
    for candidate in ranked_candidates:
        ranking = candidate.get("ranking", {})
        deterministic_reasoning = {
            "recruiter_decision_summary": ranking.get("recruiter_decision_summary", ""),
            "strengths": ranking.get("strengths", [])[:2],
            "risks": ranking.get("risks", [])[:2],
            "interview_focus_areas": ranking.get("interview_focus_areas", [])[:2],
            "candidate_differentiators": ranking.get("candidate_differentiators", [])[:1],
            "could_change_ordering": ranking.get("could_change_ordering", [])[:2],
            "ranking_challenge": ranking.get("ranking_challenge", [])[:2],
            "confidence_rationale": ranking.get("confidence_rationale"),
        }
        ranking["deterministic_reasoning"] = deterministic_reasoning
        try:
            synthesis = synthesize_candidate_reasoning(candidate)
        except Exception as error:
            failure_reason = str(error)
            break
        if not synthesis:
            continue
        ranking["recruiter_decision_summary"] = _polished_summary(
            synthesis.get("summary"),
            deterministic_reasoning["recruiter_decision_summary"],
        )
        ranking["recruiter_summary"] = ranking["recruiter_decision_summary"]
        ranking["strengths"] = _polished_list(synthesis.get("strengths"), deterministic_reasoning["strengths"])
        ranking["risks"] = _polished_list(synthesis.get("risks"), deterministic_reasoning["risks"])
        ranking["weaknesses"] = ranking["risks"]
        ranking["interview_focus_areas"] = _polished_list(
            synthesis.get("interview_validations"),
            deterministic_reasoning["interview_focus_areas"],
        )
        ranking["candidate_differentiators"] = _polished_list(
            synthesis.get("candidate_differentiators"),
            deterministic_reasoning["candidate_differentiators"],
        )
        ranking["could_change_ordering"] = _polished_list(
            synthesis.get("could_change_ordering"),
            deterministic_reasoning["could_change_ordering"],
        )
        ranking["ranking_challenge"] = _polished_list(
            synthesis.get("ranking_challenge"),
            deterministic_reasoning["ranking_challenge"],
        )
        ranking["confidence_rationale"] = _polished_optional_summary(
            synthesis.get("confidence_rationale"),
            deterministic_reasoning["confidence_rationale"],
        )
        ranking.setdefault("scoring_diagnostics", {})["ai_synthesis"] = {
            **status.diagnostics(),
            "status": "applied",
            "reason": "Groq synthesis polished deterministic evidence-backed recruiter reasoning.",
        }

    if failure_reason:
        failed_status = GroqSynthesisStatus(True, "runtime_error", failure_reason, status.model)
        _annotate_synthesis_status(ranked_candidates, failed_status, overwrite_unapplied=True)
        logger.warning("Groq synthesis failed for this ranking run; deterministic reasoning kept: %s", failure_reason)
        if processing_errors is not None:
            processing_errors.append(f"AI synthesis failed; deterministic reasoning used: {failure_reason}")


def _annotate_synthesis_status(
    ranked_candidates: list[dict],
    status: GroqSynthesisStatus,
    overwrite: bool = False,
    overwrite_unapplied: bool = False,
) -> None:
    for candidate in ranked_candidates:
        ranking = candidate.get("ranking", {})
        diagnostics = ranking.setdefault("scoring_diagnostics", {})
        current = diagnostics.get("ai_synthesis", {})
        if overwrite or (overwrite_unapplied and current.get("status") != "applied"):
            diagnostics["ai_synthesis"] = status.diagnostics()
        else:
            diagnostics.setdefault("ai_synthesis", status.diagnostics())


def synthesize_candidate_reasoning(candidate: dict) -> dict:
    api_key = _env_value("GROQ_API_KEY", "")
    if not api_key:
        return {}

    payload = _candidate_payload(candidate)
    prompt = (
        "You are a bounded hiring analyst for recruiter decision support. "
        "Do not make ranking, scoring, recommendation, or confidence decisions. "
        "Rewrite only the deterministic text already provided, making it sharper, calmer, more differentiated, and more recruiter-readable. "
        "Do not add new strengths, risks, interview prompts, technologies, outcomes, or claims. "
        "Use the evidence only to preserve factual grounding and replace generic labels with specific evidence references. "
        "Prefer fewer stronger observations. Suppress generic interview prompts or generic risks. "
        "If an input list is empty, return an empty list for that field. "
        "Do not change ordering_confidence, recommendation, confidence label, scores, or ranking order. "
        "Return compact JSON with keys: summary, strengths, risks, interview_validations, "
        "candidate_differentiators, could_change_ordering, ranking_challenge, confidence_rationale."
    )
    body = {
        "model": _env_value("GROQ_SYNTHESIS_MODEL", DEFAULT_GROQ_MODEL),
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    request = urllib.request.Request(
        _env_value("GROQ_API_ENDPOINT", GROQ_ENDPOINT),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _env_value("GROQ_USER_AGENT", DEFAULT_USER_AGENT),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:240]
        raise RuntimeError(_format_groq_http_error(error.code, detail)) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Groq request failed: {error.reason}") from error

    content = response_body.get("choices", [{}])[0].get("message", {}).get("content", "{}")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError("Groq response was not valid JSON.") from error
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _format_groq_http_error(status_code: int, detail: str) -> str:
    cleaned = " ".join((detail or "").split())
    if status_code == 403 and "1010" in cleaned:
        return (
            "Groq request failed with HTTP 403 / edge error 1010. "
            "The API key is configured, but the request was blocked by Groq/edge access controls. "
            "Kept Groq enabled and used deterministic reasoning for this run."
        )
    return f"Groq request failed with HTTP {status_code}: {cleaned}"


def _candidate_payload(candidate: dict) -> dict:
    ranking = candidate.get("ranking", {})
    evidence = []
    seen = set()
    for snippets in (ranking.get("supporting_evidence_snippets", {}) or {}).values():
        for snippet in snippets or []:
            evidence_id = snippet.get("evidence_id") or snippet.get("snippet", "")
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            if snippet.get("source_type") == "skills":
                continue
            evidence.append(
                {
                    "source_type": snippet.get("source_type"),
                    "source_label": snippet.get("source_label"),
                    "evidence_strength": snippet.get("evidence_strength"),
                    "snippet": snippet.get("snippet"),
                }
            )
            if len(evidence) >= 5:
                break
        if len(evidence) >= 5:
            break
    return {
        "candidate_name": candidate.get("candidate_name"),
        "recommendation": ranking.get("recommendation"),
        "recruiter_confidence": ranking.get("recruiter_confidence"),
        "must_have_gaps": ranking.get("missing_must_haves", [])[:3],
        "deterministic_summary": ranking.get("recruiter_decision_summary", ""),
        "deterministic_strengths": ranking.get("strengths", [])[:2],
        "deterministic_risks": ranking.get("risks", [])[:2],
        "deterministic_interview_validations": ranking.get("interview_focus_areas", [])[:2],
        "deterministic_candidate_differentiators": ranking.get("candidate_differentiators", [])[:1],
        "deterministic_could_change_ordering": ranking.get("could_change_ordering", [])[:2],
        "deterministic_ranking_challenge": ranking.get("ranking_challenge", [])[:2],
        "deterministic_confidence_rationale": ranking.get("confidence_rationale"),
        "ordering_confidence": ranking.get("ordering_confidence"),
        "close_call_with": ranking.get("close_call_with", [])[:2],
        "ordering_constraints": (ranking.get("scoring_diagnostics", {}) or {}).get("ranking_trust", {}),
        "evidence": evidence,
    }


def _polished_list(value, fallback: list[str]) -> list[str]:
    fallback = fallback[:2]
    if not fallback:
        return []
    if not isinstance(value, list):
        return fallback
    cleaned = [
        " ".join(str(item).split())
        for item in value
        if str(item).strip() and not _is_generic_generated_text(str(item))
    ]
    return cleaned[: len(fallback)] or fallback


def _polished_summary(value, fallback: str) -> str:
    cleaned = " ".join(str(value or "").split())
    if not cleaned or _is_generic_generated_text(cleaned):
        return fallback
    if len(cleaned) > 320:
        return fallback
    return cleaned


def _polished_optional_summary(value, fallback: str | None) -> str | None:
    if not fallback:
        return None
    return _polished_summary(value, fallback)


def _is_generic_generated_text(value: str) -> bool:
    lowered = value.lower()
    generic_patterns = (
        "validate communication",
        "assess communication",
        "validate scalability",
        "assess backend understanding",
        "confirm deployment exposure",
        "stronger fit",
        "better alignment",
        "more relevant",
        "good candidate",
    )
    return any(pattern in lowered for pattern in generic_patterns)


def _env_value(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is not None:
        return value

    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    try:
        with open(env_path, encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, raw_value = line.split("=", 1)
                if key.strip() == name:
                    return raw_value.strip().strip('"').strip("'")
    except OSError:
        return default

    return default
