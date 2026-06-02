from __future__ import annotations

import gzip
import json
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Iterable, Iterator

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".json", ".jsonl", ".ndjson", ".jsonl.gz", ".ndjson.gz"}


def load_dataset(path: str | Path) -> pd.DataFrame:
    dataset_path = Path(path)
    suffix = _dataset_suffix(dataset_path)
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported dataset format: {suffix}. Use CSV, JSON, JSONL, JSONL.GZ, or NDJSON.")

    if suffix == ".csv":
        return _normalize_frame(pd.read_csv(dataset_path))
    if suffix in {".jsonl", ".ndjson", ".jsonl.gz", ".ndjson.gz"}:
        return _normalize_frame(_records_to_frame(iter_dataset_records(dataset_path)))
    return _normalize_frame(_read_json(_read_text(dataset_path)))


def load_dataset_bytes(filename: str, content: bytes) -> pd.DataFrame:
    suffix = _dataset_suffix(Path(filename))
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported dataset format: {suffix}. Use CSV, JSON, JSONL, JSONL.GZ, or NDJSON.")

    if suffix == ".csv":
        return _normalize_frame(pd.read_csv(BytesIO(content)))
    if suffix in {".jsonl.gz", ".ndjson.gz"}:
        text = gzip.decompress(content).decode("utf-8")
    else:
        text = content.decode("utf-8")
    if suffix in {".jsonl", ".ndjson", ".jsonl.gz", ".ndjson.gz"}:
        return _normalize_frame(_records_to_frame(_iter_jsonl_text(text)))
    return _normalize_frame(_read_json(text))


def iter_dataset_records(path: str | Path) -> Iterator[dict[str, Any]]:
    dataset_path = Path(path)
    suffix = _dataset_suffix(dataset_path)
    if suffix in {".jsonl", ".ndjson", ".jsonl.gz", ".ndjson.gz"}:
        with _open_text(dataset_path) as handle:
            for line_number, line in enumerate(handle, start=1):
                cleaned = line.strip()
                if not cleaned:
                    continue
                try:
                    payload = json.loads(cleaned)
                except json.JSONDecodeError as error:
                    raise ValueError(f"Invalid JSONL at line {line_number}: {error}") from error
                if not isinstance(payload, dict):
                    raise ValueError(f"JSONL line {line_number} must contain an object.")
                yield payload
        return

    if suffix == ".json":
        yield from _iter_json_payload(json.loads(_read_text(dataset_path)))
        return

    if suffix == ".csv":
        for record in pd.read_csv(dataset_path).to_dict(orient="records"):
            yield record
        return

    raise ValueError(f"Unsupported dataset format for streaming: {suffix}.")


def _read_json(text: str) -> pd.DataFrame:
    payload: Any = json.loads(text)
    return _records_to_frame(_iter_json_payload(payload))


def _iter_json_payload(payload: Any) -> Iterator[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("candidates", "profiles", "data", "rows", "items", "results"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("JSON dataset must contain an object, list of objects, or a common rows/data key.")
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"JSON row {index} must contain an object.")
        yield item


def _iter_jsonl_text(text: str) -> Iterator[dict[str, Any]]:
    for line_number, line in enumerate(StringIO(text), start=1):
        cleaned = line.strip()
        if not cleaned:
            continue
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise ValueError(f"JSONL line {line_number} must contain an object.")
        yield payload


def _records_to_frame(records: Iterable[dict[str, Any]]) -> pd.DataFrame:
    materialized = []
    for record in records:
        normalized = pd.json_normalize(record, sep=".").iloc[0].to_dict()
        if "candidate_id" in record:
            normalized["candidate_id"] = record["candidate_id"]
        if _looks_like_redrob_candidate(record):
            normalized["raw_candidate"] = record
        materialized.append(normalized)
    return pd.DataFrame(materialized)


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame


def _dataset_suffix(path: Path) -> str:
    suffixes = [suffix.lower() for suffix in path.suffixes]
    if len(suffixes) >= 2 and suffixes[-2:] in ([".jsonl", ".gz"], [".ndjson", ".gz"]):
        return "".join(suffixes[-2:])
    return path.suffix.lower()


def _read_text(path: Path) -> str:
    with _open_text(path) as handle:
        return handle.read()


def _open_text(path: Path):
    suffix = _dataset_suffix(path)
    if suffix in {".jsonl.gz", ".ndjson.gz"}:
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("rt", encoding="utf-8")


def _looks_like_redrob_candidate(record: dict[str, Any]) -> bool:
    return bool(
        record.get("candidate_id")
        and isinstance(record.get("profile"), dict)
        and isinstance(record.get("career_history"), list)
        and isinstance(record.get("skills"), list)
        and isinstance(record.get("redrob_signals"), dict)
    )
