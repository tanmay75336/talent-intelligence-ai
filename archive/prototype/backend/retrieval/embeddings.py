from __future__ import annotations

import logging
import os
import re
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
ENABLE_EMBEDDINGS = os.getenv("ENABLE_EMBEDDINGS", "true").lower() == "true"
EMBEDDING_DIMENSION = 384


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


@lru_cache(maxsize=1)
def get_embedding_provider() -> SentenceTransformer:
    if not ENABLE_EMBEDDINGS:
        raise RuntimeError("Embeddings are disabled by ENABLE_EMBEDDINGS=false.")

    logger.info("Loading embedding model: %s", DEFAULT_MODEL)
    model = SentenceTransformer(DEFAULT_MODEL)
    logger.info("Embedding model loaded successfully.")
    return model


def embedding_dimension() -> int:
    return EMBEDDING_DIMENSION


def embed_text(text: str) -> list[float]:
    cleaned = _clean_text(text)
    if not cleaned:
        return []

    model = get_embedding_provider()
    vector = model.encode(cleaned, normalize_embeddings=True)
    vector = np.asarray(vector, dtype=float)
    validate_embedding_dimension(vector)
    return vector.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    cleaned_texts = [_clean_text(text) for text in texts if _clean_text(text)]
    if not cleaned_texts:
        return []

    model = get_embedding_provider()
    vectors = model.encode(cleaned_texts, normalize_embeddings=True)
    vectors = np.asarray(vectors, dtype=float)
    if vectors.ndim == 1:
        vectors = np.expand_dims(vectors, axis=0)
    for vector in vectors:
        validate_embedding_dimension(vector)
    return vectors.tolist()


def validate_embedding_dimension(vector: np.ndarray | list[float]) -> None:
    dimension = len(vector)
    if dimension != EMBEDDING_DIMENSION:
        raise ValueError(f"Unexpected embedding dimension: {dimension}. Expected {EMBEDDING_DIMENSION}.")


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if not vector_a or not vector_b:
        return 0.0
    a = np.asarray(vector_a, dtype=float)
    b = np.asarray(vector_b, dtype=float)
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0.0:
        return 0.0
    return float(np.dot(a, b) / denominator)
