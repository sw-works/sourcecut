from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sourcecut_api.db.client import get_clickhouse_client

DEFAULT_GOLD = Path("fixtures/evaluation/gold_observations_sept_1805.json")
DEFAULT_RETRIEVAL = Path("fixtures/evaluation/retrieval_queries.json")
DEFAULT_ODYSSEY_GOLD = Path("fixtures/evaluation/odyssey_gold_questions.json")


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
    # Only fully-correct verdicts count toward the quality gates; "partial"
    # is reported separately so half-right extractions cannot satisfy the
    # 95%/90% targets.
    correct = sum(item["verdict"] == "correct" for item in reviewed)
    partial = sum(item["verdict"] == "partial" for item in reviewed)
    ground_truth = correct + partial + len(document.get("missed_observations", []))
    failures = validate_spans(items)
    return {
        "provisional": len(reviewed) != len(items),
        "reviewed": len(reviewed),
        "total": len(items),
        "span_validity": 1 - len(failures) / len(items) if items else 1.0,
        "span_failures": list(failures),
        "precision": correct / len(reviewed) if reviewed else None,
        "partial_fraction": partial / len(reviewed) if reviewed else None,
        "recall": correct / ground_truth if ground_truth else None,
        "recall_denominator": (
            "fully-correct plus partial reviewed observations plus reviewer-added misses"
        ),
    }


def score_odyssey_answers(gold: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    answer_by_id = {item["question_id"]: item for item in answers.get("answers", [])}
    expected_claims = 0
    returned_claims = 0
    correct_claims = 0
    failures: list[str] = []
    for question in gold["questions"]:
        answer = answer_by_id.get(question["question_id"], {})
        expected = set(question.get("expected_reference_ids", []))
        returned = set(answer.get("reference_ids", []))
        expected_claims += len(expected)
        returned_claims += len(returned)
        correct_claims += len(expected & returned)
        if (
            question.get("expected_status") == "unsupported"
            and answer.get("status") != "unsupported"
        ):
            failures.append(f"{question['question_id']}: unsupported request was overclaimed")
        if not returned <= expected:
            failures.append(f"{question['question_id']}: returned unexpected references")
    precision = correct_claims / returned_claims if returned_claims else 1.0
    recall = correct_claims / expected_claims if expected_claims else 1.0
    return {
        "precision": precision,
        "recall": recall,
        "passes_precision": precision >= 0.95,
        "passes_recall": recall >= 0.90,
        "failures": failures,
    }


def score_odyssey_invariants(root: Path = Path(".")) -> dict[str, Any]:
    from sourcecut_api.services.readiness import readiness_report

    narrative = json.loads(
        (root / "data/reference/odyssey_narrative.json").read_text(encoding="utf-8")
    )
    geography = json.loads(
        (root / "data/reference/odyssey_geography.json").read_text(encoding="utf-8")
    )
    visual = json.loads(
        (root / "data/reference/odyssey_visual_culture.json").read_text(encoding="utf-8")
    )
    snapshot = json.loads(
        (root / "data/offline/odyssey/known-good-board.json").read_text(encoding="utf-8")
    )
    failures: list[str] = []
    events = narrative["events"]
    if any(event["reading_order_start"] > event["reading_order_end"] for event in events):
        failures.append("narrative event has reversed reading order")
    identifications = geography["identifications"]
    for item in identifications:
        located = item["longitude"] is not None or item["latitude"] is not None
        if located and (item["longitude"] is None or item["latitude"] is None):
            failures.append(f"{item['identification_id']}: partial coordinates")
        if located and not item["scholarly_source_ids"]:
            failures.append(f"{item['identification_id']}: coordinates lack authority")
    for item in visual["objects"]:
        if item["status"] != "rejected" and not item["links"]:
            failures.append(f"met-{item['object_id']}: accepted asset lacks corpus links")
        if not item["limitations"]:
            failures.append(f"met-{item['object_id']}: missing limitations")
    readiness = readiness_report()
    if not readiness["offline_corpus_ready"]:
        failures.extend(readiness["failures"])
    kinds = {item["kind"] for item in snapshot["references"]}
    if not {"passage", "entity", "map_view", "asset"} <= kinds:
        failures.append("known-good board lacks required reference kinds")
    return {
        "passes": not failures,
        "failures": failures,
        "events": len(events),
        "located_map_features": sum(
            item["longitude"] is not None and item["latitude"] is not None
            for item in identifications
        ),
        "visual_assets": len(visual["objects"]),
        "offline_corpus_ready": readiness["offline_corpus_ready"],
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


def score_extraction_candidates(
    document: dict[str, Any], candidates: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Score a candidate set against the reviewed fixture without touching the DB.

    Lets a prompt, model, or sampling change (for example self-consistency
    voting) be compared against the single-shot baseline on the same reviewed
    spans. Only fully-correct verdicts count, matching score_fixture.
    """
    verdicts = {
        (
            str(item["passage_id"]),
            int(item["source_start"]),
            int(item["source_end"]),
        ): str(item["verdict"])
        for item in document["observations"]
        if item.get("verdict")
    }
    if not verdicts:
        return {"status": "fixture has no reviewed verdicts"}
    matched = 0
    correct = 0
    unreviewed = 0
    for item in candidates:
        key = (
            str(item["passage_id"]),
            int(item["source_start"]),
            int(item["source_end"]),
        )
        verdict = verdicts.get(key)
        if verdict is None:
            unreviewed += 1
            continue
        matched += 1
        correct += verdict == "correct"
    reviewed_correct = sum(value == "correct" for value in verdicts.values())
    return {
        "candidates": len(candidates),
        "matched_reviewed": matched,
        "unreviewed": unreviewed,
        "precision_on_reviewed": correct / matched if matched else None,
        "recall_on_reviewed": (
            correct / reviewed_correct if reviewed_correct else None
        ),
        "reviewed_correct_total": reviewed_correct,
    }


def run_evaluation(
    path: Path, candidate_paths: Mapping[str, Path] | None = None
) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    report = score_fixture(document)
    report["retrieval"] = {
        "token_only": {"status": "pending reviewed relevance judgments"},
        "token_dictionary": {"status": "pending reviewed relevance judgments"},
        "hybrid_cosine": {"status": "pending committed query vectors"},
    }
    if candidate_paths:
        report["extraction_variants"] = {
            label: score_extraction_candidates(
                document, json.loads(source.read_text(encoding="utf-8"))
            )
            for label, source in candidate_paths.items()
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
    run.add_argument(
        "--candidates",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help=(
            "Score an extraction candidate file against the reviewed fixture, "
            "e.g. --candidates single=out/single.json --candidates consensus=out/sc.json"
        ),
    )
    args = parser.parse_args()
    if args.command == "export":
        export_fixture(args.path, args.size)
    elif args.command == "import":
        freeze_fixture(args.path)
    else:
        variants: dict[str, Path] = {}
        for item in args.candidates:
            label, _, raw = item.partition("=")
            if not label or not raw:
                parser.error("--candidates expects LABEL=PATH")
            variants[label] = Path(raw)
        run_evaluation(args.path, variants or None)
