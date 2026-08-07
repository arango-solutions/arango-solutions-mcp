"""Small deterministic lexical rankers used by blocking offline evaluations."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

_TOKEN = re.compile(r"[a-z0-9]+")
_SYNONYMS = {
    "add": "create",
    "backup": "backup",
    "db": "database",
    "fetch": "get",
    "find": "search",
    "inspect": "get",
    "query": "search",
    "remove": "delete",
    "show": "list",
}


def tokenize(value: str) -> list[str]:
    tokens: list[str] = []
    for token in _TOKEN.findall(value.lower().replace("_", "-")):
        normalized = _SYNONYMS.get(token, token)
        if normalized.endswith("ies") and len(normalized) > 4:
            normalized = f"{normalized[:-3]}y"
        elif normalized.endswith("s") and len(normalized) > 3:
            normalized = normalized[:-1]
        tokens.append(normalized)
    return tokens


def rank_tool_names(query: str, tool_names: Iterable[str]) -> list[str]:
    query_tokens = set(tokenize(query))
    ranked: list[tuple[float, str]] = []
    for name in tool_names:
        name_tokens = set(tokenize(name))
        overlap = len(query_tokens & name_tokens)
        action_bonus = 2 if tokenize(name)[0] in query_tokens else 0
        exact_bonus = 5 if name.replace("-", " ") in query.lower() else 0
        score = overlap * 3 + action_bonus + exact_bonus
        ranked.append((score, name))
    return [name for _, name in sorted(ranked, key=lambda item: (-item[0], item[1]))]


@dataclass(frozen=True)
class RankedDocument:
    document_id: str
    score: float


def bm25_rank(query: str, documents: Mapping[str, str]) -> Sequence[RankedDocument]:
    """Rank a fixed corpus using standard BM25 with deterministic tie-breaking."""
    tokenized = {document_id: tokenize(text) for document_id, text in documents.items()}
    query_terms = tokenize(query)
    if not query_terms:
        return tuple(RankedDocument(document_id, 0.0) for document_id in sorted(documents))
    average_length = sum(map(len, tokenized.values())) / max(len(tokenized), 1)
    frequencies = {
        term: sum(term in tokens for tokens in tokenized.values()) for term in set(query_terms)
    }
    k1 = 1.2
    b = 0.75
    ranked: list[RankedDocument] = []
    for document_id, tokens in tokenized.items():
        counts = Counter(tokens)
        score = 0.0
        for term in query_terms:
            document_frequency = frequencies[term]
            inverse_frequency = math.log(
                1 + (len(tokenized) - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            frequency = counts[term]
            denominator = frequency + k1 * (1 - b + b * len(tokens) / max(average_length, 1))
            if denominator:
                score += inverse_frequency * frequency * (k1 + 1) / denominator
        ranked.append(RankedDocument(document_id, score))
    return tuple(sorted(ranked, key=lambda item: (-item.score, item.document_id)))
