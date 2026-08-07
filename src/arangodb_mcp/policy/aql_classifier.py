"""Classify AQL from ArangoDB's parser AST, never from query-text regexes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


class AQLClassification(str, Enum):
    READ = "read"
    MUTATION = "mutation"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class AQLClassificationResult:
    classification: AQLClassification
    reasons: tuple[str, ...]
    mutation_nodes: tuple[str, ...] = ()


_MUTATION_NODE_TYPES = frozenset({"insert", "update", "replace", "remove", "upsert"})
_DYNAMIC_FUNCTIONS = frozenset({"CALL", "APPLY"})


def _walk_nodes(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if isinstance(value.get("type"), str):
            yield value
        for child in value.values():
            yield from _walk_nodes(child)
    elif isinstance(value, list | tuple):
        for child in value:
            yield from _walk_nodes(child)


def classify_aql_parse_result(parse_result: Mapping[str, Any]) -> AQLClassificationResult:
    """Classify the authoritative `POST /_api/query` parser response."""
    if parse_result.get("parsed") is not True:
        return AQLClassificationResult(
            AQLClassification.AMBIGUOUS, ("parser did not report parsed=true",)
        )
    ast = parse_result.get("ast")
    if not isinstance(ast, list) or not ast:
        return AQLClassificationResult(
            AQLClassification.AMBIGUOUS, ("parser response did not contain an AST",)
        )

    nodes = tuple(_walk_nodes(ast))
    mutation_nodes = tuple(
        sorted(
            {
                str(node["type"]).lower()
                for node in nodes
                if str(node.get("type", "")).lower() in _MUTATION_NODE_TYPES
            }
        )
    )
    if mutation_nodes:
        return AQLClassificationResult(
            AQLClassification.MUTATION,
            ("parser AST contains data-modification nodes",),
            mutation_nodes,
        )

    ambiguous_reasons: list[str] = []
    for node in nodes:
        node_type = str(node.get("type", "")).lower()
        name = str(node.get("name", "")).upper()
        if node_type == "user function call":
            ambiguous_reasons.append(f"user-defined function call {name or '<unknown>'}")
        elif node_type == "function call" and name in _DYNAMIC_FUNCTIONS:
            ambiguous_reasons.append(f"dynamic function dispatch via {name}")
    if ambiguous_reasons:
        return AQLClassificationResult(
            AQLClassification.AMBIGUOUS, tuple(sorted(set(ambiguous_reasons)))
        )

    return AQLClassificationResult(
        AQLClassification.READ, ("parser AST contains no mutation or dynamic-call nodes",)
    )
