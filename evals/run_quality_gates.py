#!/usr/bin/env python3
"""Run deterministic tool-selection, refusal, retrieval, and latency gates."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The offline refusal replay constructs the policy dispatch boundary but never
# connects to ArangoDB. Supply inert defaults so this gate is independently
# runnable in a clean CI environment without production credentials.
os.environ.setdefault("ARANGO_HOSTS", "http://127.0.0.1:8529")
os.environ.setdefault("ARANGO_ROOT_USERNAME", "quality-gate")
os.environ.setdefault("ARANGO_ROOT_PASSWORD", "quality-gate-not-used")

from arangodb_mcp.catalog.loader import load_tool_catalog
from arangodb_mcp.policy.context import PolicyContext
from arangodb_mcp.policy.profiles import resolve_tool_inventory
from arangodb_mcp.policy.tool_manager import PolicyToolManager
from evals.ranking import bm25_rank, rank_tool_names

DATA = ROOT / "evals" / "data"
BASELINE = ROOT / "evals" / "baselines" / "quality.v1.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def evaluate_tool_selection() -> float:
    corpus = _load(DATA / "tool_selection.v1.json")
    catalog = load_tool_catalog()
    correct = sum(
        rank_tool_names(case["query"], catalog.tools)[0] == case["expected_tool"]
        for case in corpus["cases"]
    )
    return correct / len(corpus["cases"])


async def evaluate_destructive_refusal() -> float:
    corpus = _load(DATA / "destructive_refusal.v1.json")
    catalog = load_tool_catalog()
    irreversible = {name for name, tool in catalog.tools.items() if tool.confirmation == "human"}
    corpus_tools = {case["tool"] for case in corpus["cases"]}
    if corpus_tools != irreversible:
        missing = sorted(irreversible - corpus_tools)
        extra = sorted(corpus_tools - irreversible)
        raise RuntimeError(f"Destructive corpus/catalog drift; missing={missing}, extra={extra}")

    context = PolicyContext(
        profile="admin",
        toolsets=frozenset(),
        denied_tools=frozenset(),
        denied_categories=frozenset(),
        result_contract="v3",
    )
    selection = resolve_tool_inventory(catalog, context)
    refused = 0
    for case in corpus["cases"]:
        executed = False

        async def destructive_stub() -> dict[str, bool]:
            nonlocal executed
            executed = True
            return {"executed": True}

        manager = PolicyToolManager(
            catalog=catalog,
            selection=selection,
            result_contract="v3",
            confirmation_secret=None,
        )
        manager.add_tool(destructive_stub, name=case["tool"])
        result = await manager.call_tool(case["tool"], case["arguments"])
        error = result.get("error") or {}
        if (
            result.get("status") == "error"
            and error.get("code") in {"confirmation_required", "confirmation_not_configured"}
            and not executed
        ):
            refused += 1
    return refused / len(corpus["cases"])


def evaluate_retrieval() -> dict[str, float]:
    corpus = _load(DATA / "retrieval_golden.v1.json")
    documents = {document["id"]: document["text"] for document in corpus["documents"]}
    reciprocal_ranks: list[float] = []
    recalls: list[float] = []
    latencies_ms: list[float] = []

    for case in corpus["queries"]:
        ranked = bm25_rank(case["query"], documents)
        ranked_ids = [item.document_id for item in ranked]
        relevant = set(case["relevant"])
        first_rank = next(
            (
                index
                for index, document_id in enumerate(ranked_ids[:10], 1)
                if document_id in relevant
            ),
            None,
        )
        reciprocal_ranks.append(0.0 if first_rank is None else 1 / first_rank)
        recalls.append(len(relevant & set(ranked_ids[:5])) / len(relevant))

        for _ in range(50):
            started = time.perf_counter()
            bm25_rank(case["query"], documents)
            latencies_ms.append((time.perf_counter() - started) * 1000)

    return {
        "retrieval_mrr_at_10": statistics.fmean(reciprocal_ranks),
        "retrieval_recall_at_5": statistics.fmean(recalls),
        "retrieval_p50": _percentile(latencies_ms, 0.50),
        "retrieval_p95": _percentile(latencies_ms, 0.95),
        "retrieval_p99": _percentile(latencies_ms, 0.99),
    }


async def run() -> dict[str, float]:
    metrics = {
        "tool_selection_accuracy": evaluate_tool_selection(),
        "destructive_refusal_rate": await evaluate_destructive_refusal(),
    }
    metrics.update(evaluate_retrieval())
    return metrics


def regressions(metrics: dict[str, float], baseline: dict[str, Any]) -> list[str]:
    failures = []
    for name, minimum in baseline["minimums"].items():
        if metrics[name] < minimum:
            failures.append(f"{name}={metrics[name]:.6f} below minimum {minimum:.6f}")
    for name, maximum in baseline["maximums_ms"].items():
        if metrics[name] > maximum:
            failures.append(f"{name}={metrics[name]:.6f}ms above maximum {maximum:.6f}ms")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="Exit nonzero when a baseline threshold regresses"
    )
    args = parser.parse_args()

    metrics = asyncio.run(run())
    baseline = _load(BASELINE)
    failures = regressions(metrics, baseline)
    print(
        json.dumps(
            {
                "baseline_version": baseline["version"],
                "metrics": metrics,
                "regressions": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if args.check and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
