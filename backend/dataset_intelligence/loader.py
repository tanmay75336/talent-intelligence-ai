from __future__ import annotations

import json
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".json", ".jsonl", ".ndjson"}


def load_dataset(path: str | Path) -> pd.DataFrame:
    dataset_path = Path(path)
    suffix = dataset_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported dataset format: {suffix}. Use CSV, JSON, JSONL, or NDJSON.")

    if suffix == ".csv":
        return _normalize_frame(pd.read_csv(dataset_path))
    if suffix in {".jsonl", ".ndjson"}:
        return _normalize_frame(pd.read_json(dataset_path, lines=True))
    return _normalize_frame(_read_json(dataset_path.read_text(encoding="utf-8")))


def load_dataset_bytes(filename: str, content: bytes) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported dataset format: {suffix}. Use CSV, JSON, JSONL, or NDJSON.")

    if suffix == ".csv":
        return _normalize_frame(pd.read_csv(BytesIO(content)))
    text = content.decode("utf-8")
    if suffix in {".jsonl", ".ndjson"}:
        return _normalize_frame(pd.read_json(StringIO(text), lines=True))
    return _normalize_frame(_read_json(text))


def _read_json(text: str) -> pd.DataFrame:
    payload: Any = json.loads(text)
    if isinstance(payload, dict):
        for key in ("candidates", "profiles", "data", "rows", "items", "results"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("JSON dataset must contain an object, list of objects, or a common rows/data key.")
    return pd.json_normalize(payload, sep=".")


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame

