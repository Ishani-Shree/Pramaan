"""Pure scoring helpers (no DB, no LLM) so they can be unit-tested."""

from __future__ import annotations

import re
import statistics
from typing import Iterable

import numpy as np


def normalize(text: str) -> str:
    """Case-insensitive, and ignore formatting that doesn't change meaning:
    thousands separators (1,326 == 1326) and hyphens/dashes/underscores
    (EfficientNet-B2 == EfficientNet B2)."""
    text = text.lower()
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)
    text = re.sub(r"[-‐‑–—_]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def missing_facts(answer: str, key_facts: list) -> list:
    """Key facts not found in the answer. A fact is a string, or a list of
    acceptable alternatives (any one of them counts)."""
    norm_answer = normalize(answer)
    missing = []
    for fact in key_facts:
        alternatives = fact if isinstance(fact, list) else [fact]
        if not any(normalize(a) in norm_answer for a in alternatives):
            missing.append(fact)
    return missing


def percentile(values: Iterable[float], q: float) -> float:
    vals = list(values)
    return float(np.percentile(vals, q)) if vals else 0.0


def median(values: Iterable[float]) -> float:
    vals = list(values)
    return float(statistics.median(vals)) if vals else 0.0
