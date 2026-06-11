import logging
import math
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.retrieval.embeddings import embed_texts

logger = logging.getLogger(__name__)


def _clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _weighted_top_pool(values, top_k=5):
    if len(values) == 0:
        return 0.0

    top_values = np.sort(np.asarray(values, dtype=float))[-min(top_k, len(values)):]
    top_values = np.flip(top_values)
    weights = np.linspace(1.0, 0.7, num=len(top_values))
    return float(np.average(top_values, weights=weights))


def split_text_into_chunks(text, max_words=90, overlap_words=22):
    cleaned = _clean_text(text)
    if not cleaned:
        return []

    sentence_parts = re.split(r"(?<=[.!?])\s+|\n", cleaned)
    chunks = []
    current_words = []

    for part in sentence_parts:
        words = part.split()
        if not words:
            continue

        if len(current_words) + len(words) > max_words and current_words:
            chunks.append(" ".join(current_words))
            overlap = current_words[-overlap_words:] if overlap_words > 0 else []
            current_words = overlap + words
        else:
            current_words.extend(words)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks[:20]


def _cosine_to_recruiter_score(cosine_value):
    cosine_value = max(0.0, min(1.0, float(cosine_value)))
    logistic = 100 / (1 + math.exp(-7.0 * (cosine_value - 0.16)))
    if cosine_value > 0.18:
        logistic = max(logistic, 45)
    if cosine_value > 0.28:
        logistic = max(logistic, 60)
    if cosine_value > 0.38:
        logistic = max(logistic, 75)
    return round(max(0.0, min(100.0, logistic)), 2)


def calculate_similarity(text1, text2):
    return calculate_similarity_between_text_sets(
        split_text_into_chunks(text1) or [text1],
        split_text_into_chunks(text2) or [text2],
    )


def calculate_similarity_between_text_sets(source_texts, target_texts, return_diagnostics=False):
    source_chunks = []
    target_chunks = []

    for text in source_texts:
        source_chunks.extend(split_text_into_chunks(text) or [_clean_text(text)])
    for text in target_texts:
        target_chunks.extend(split_text_into_chunks(text) or [_clean_text(text)])

    source_chunks = [chunk for chunk in source_chunks if chunk]
    target_chunks = [chunk for chunk in target_chunks if chunk]

    if not source_chunks or not target_chunks:
        empty_diagnostics = {
            "mode": "empty_input",
            "aggregate_similarity": 0.0,
            "source_focus": 0.0,
            "target_focus": 0.0,
            "coverage_ratio": 0.0,
            "lexical_alignment": 0.0,
            "source_chunks": len(source_chunks),
            "target_chunks": len(target_chunks),
            "top_source_matches": [],
            "top_target_matches": [],
        }
        if return_diagnostics:
            return {"score": 0.0, "diagnostics": empty_diagnostics}
        return 0.0

    source_embeddings = np.asarray(embed_texts(source_chunks), dtype=float)
    target_embeddings = np.asarray(embed_texts(target_chunks), dtype=float)
    mode = "embedding"
    if source_embeddings.size == 0 or target_embeddings.size == 0:
        raise ValueError("Empty embeddings generated.")
    try:
        similarity_matrix = np.matmul(source_embeddings, target_embeddings.T)
    except Exception:
        logger.warning("Embedding similarity failed; using lexical fallback for legacy similarity route.")
        word_vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        char_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
        combined_word_matrix = word_vectorizer.fit_transform(source_chunks + target_chunks)
        combined_char_matrix = char_vectorizer.fit_transform(source_chunks + target_chunks)
        source_word_matrix = combined_word_matrix[: len(source_chunks)]
        target_word_matrix = combined_word_matrix[len(source_chunks):]
        source_char_matrix = combined_char_matrix[: len(source_chunks)]
        target_char_matrix = combined_char_matrix[len(source_chunks):]
        word_similarity = (source_word_matrix @ target_word_matrix.T).toarray()
        char_similarity = (source_char_matrix @ target_char_matrix.T).toarray()
        similarity_matrix = (word_similarity * 0.72) + (char_similarity * 0.28)
        mode = "tfidf_fallback"

    best_per_target = similarity_matrix.max(axis=0)
    best_per_source = similarity_matrix.max(axis=1)
    source_focus = _weighted_top_pool(best_per_source, top_k=5)
    target_focus = _weighted_top_pool(best_per_target, top_k=5)
    coverage_ratio = float(np.mean(best_per_target >= 0.35)) if len(best_per_target) else 0.0
    aggregate_cosine = (source_focus * 0.46) + (target_focus * 0.34) + (coverage_ratio * 0.20)
    score = _cosine_to_recruiter_score(aggregate_cosine)

    diagnostics = {
        "mode": mode,
        "aggregate_similarity": round(float(aggregate_cosine), 4),
        "source_focus": round(float(source_focus), 4),
        "target_focus": round(float(target_focus), 4),
        "coverage_ratio": round(float(coverage_ratio), 4),
        "lexical_alignment": 0.0,
        "source_chunks": len(source_chunks),
        "target_chunks": len(target_chunks),
        "top_source_matches": [round(float(value), 4) for value in sorted(best_per_source, reverse=True)[:5]],
        "top_target_matches": [round(float(value), 4) for value in sorted(best_per_target, reverse=True)[:5]],
    }
    if return_diagnostics:
        return {"score": score, "diagnostics": diagnostics}
    return score
