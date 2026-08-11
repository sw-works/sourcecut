from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sourcecut_api.db.client import get_clickhouse_client

DEFAULT_GOLD = Path("fixtures/evaluation/gold_observations_sept_1805.json")
DEFAULT_RETRIEVAL = Path("fixtures/evaluation/retrieval_queries.json")


def validate_spans(items: list[dict[str, Any]]) -> tuple[str, ...]:
    failures = []
    for item in items:
        text = item["passage_text"]
        if text[item["source_start"] : item["source_end"]] != item["source_quote"]:
            failures.append(item["observation_id"])
    return tuple(failures)


def score_fixture(document: dict[str, Any]) -> dict[str, Any]:
    items = document["observations"]
    reviewed = [item for item in items if item["verdict"]]
    correct = sum(item["verdict"] in {"correct", "partial"} for item in reviewed)
    ground_truth = correct + len(document.get("missed_observations", []))
    failures = validate_spans(items)
    return {
        "provisional": len(reviewed) != len(items),
        "reviewed": len(reviewed),
        "total": len(items),
        "span_validity": 1 - len(failures) / len(items) if items else 1.0,
        "span_failures": list(failures),
        "precision": correct / len(reviewed) if reviewed else None,
        "recall": correct / ground_truth if ground_truth else None,
        "recall_denominator": "reviewed sampled-passage observations plus reviewer-added misses",
    }


def export_fixture(path: Path, size: int) -> None:
    client = get_clickhouse_client()
    rows = client.query(
        """
SELECT m.mention_id, m.passage_id, m.source_quote, m.source_start, m.source_end,
       m.entity_id, p.passage_text
FROM (SELECT * FROM entity_mentions FINAL) AS m
INNER JOIN (SELECT passage_id, passage_text FROM passages FINAL) AS p
    ON p.passage_id = m.passage_id
WHERE m.entry_date BETWEEN 18050909 AND 18050930
ORDER BY sipHash64(m.mention_id)
LIMIT {limit:UInt16}
""".strip(),
        parameters={"limit": size},
    ).result_rows
    observations = [
        {
            "observation_id": str(row[0]),
            "passage_id": str(row[1]),
            "source_quote": str(row[2]),
            "source_start": int(row[3]),
            "source_end": int(row[4]),
            "category": "entity",
            "canonical_term": str(row[5]),
            "passage_text": str(row[6]),
            "verdict": "",
            "reviewer": "",
            "review_note": "",
        }
        for row in rows
    ]
    document = {
        "schema_version": "gold-observations-v1",
        "status": "provisional",
        "source": "deterministic trusted entity mentions; human review required",
        "content_sha256": "",
        "observations": observations,
        "missed_observations": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def freeze_fixture(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    allowed = {"correct", "incorrect", "partial"}
    verdicts = {item["verdict"] for item in document["observations"]}
    if not verdicts or not verdicts <= allowed:
        raise ValueError("Every verdict must be correct, incorrect, or partial")
    document["status"] = "reviewed"
    document["content_sha256"] = ""
    canonical = json.dumps(document, separators=(",", ":"), sort_keys=True)
    document["content_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def run_evaluation(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    report = score_fixture(document)
    report["retrieval"] = {
        "token_only": {"status": "pending reviewed relevance judgments"},
        "token_dictionary": {"status": "pending reviewed relevance judgments"},
        "hybrid_cosine": {"status": "pending committed query vectors"},
    }
    output = Path("output/eval") / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["span_validity"] < 1:
        raise SystemExit(1)
    if not report["provisional"] and (
        (report["precision"] or 0) < 0.95 or (report["recall"] or 0) < 0.90
    ):
        raise SystemExit(1)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Export, freeze, or run SourceCut evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("--size", type=int, default=100)
    export.add_argument("--path", type=Path, default=DEFAULT_GOLD)
    freeze = sub.add_parser("import")
    freeze.add_argument("--path", type=Path, default=DEFAULT_GOLD)
    run = sub.add_parser("run")
    run.add_argument("--path", type=Path, default=DEFAULT_GOLD)
    args = parser.parse_args()
    if args.command == "export":
        export_fixture(args.path, args.size)
    elif args.command == "import":
        freeze_fixture(args.path)
    else:
        run_evaluation(args.path)
