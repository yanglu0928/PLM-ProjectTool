from __future__ import annotations

from typing import Iterable


def top_k_recall(expected_ids: Iterable[str], actual_ids: Iterable[str], *, k: int) -> float:
    if k < 1:
        raise ValueError("k must be positive")
    expected = set(expected_ids)
    if not expected:
        raise ValueError("expected_ids must not be empty")
    actual = list(actual_ids)[:k]
    return len(expected.intersection(actual)) / len(expected)
