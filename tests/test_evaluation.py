from __future__ import annotations

from sourcecut_api.evaluation import score_fixture, validate_spans


def item() -> dict[str, object]:
    return {
        "observation_id": "observation-1",
        "passage_text": "the mountains were covered with snow",
        "source_quote": "snow",
        "source_start": 32,
        "source_end": 36,
        "verdict": "",
    }


def test_provisional_fixture_warns_without_failing_targets() -> None:
    report = score_fixture({"observations": [item()], "missed_observations": []})

    assert report["provisional"] is True
    assert report["span_validity"] == 1
    assert report["precision"] is None


def test_span_validation_catches_corrupted_offset() -> None:
    corrupted = item()
    corrupted["source_start"] = 31

    assert validate_spans([corrupted]) == ("observation-1",)


def test_partial_verdicts_do_not_satisfy_the_gates() -> None:
    reviewed = item()
    reviewed["verdict"] = "partial"

    report = score_fixture({"observations": [reviewed], "missed_observations": []})

    assert report["provisional"] is False
    assert report["precision"] == 0.0
    assert report["partial_fraction"] == 1.0
    assert report["recall"] == 0.0


def test_correct_verdicts_score_fully() -> None:
    reviewed = item()
    reviewed["verdict"] = "correct"

    report = score_fixture({"observations": [reviewed], "missed_observations": []})

    assert report["precision"] == 1.0
    assert report["partial_fraction"] == 0.0
    assert report["recall"] == 1.0
