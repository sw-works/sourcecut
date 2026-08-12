from __future__ import annotations

import asyncio
from typing import Any

from fastapi.testclient import TestClient

from sourcecut_api.main import create_app
from sourcecut_api.models.claim import ClaimCreate, ClaimReviewStatus
from sourcecut_api.services.claim_validation import ClaimValidationService

UNIT_HASH = "a" * 64
VERSION_HASH = "b" * 64


class FakeClaimMcp:
    async def get_odyssey_claim_source(self, source_record_id: str) -> dict[str, Any]:
        if source_record_id == "text-unit:missing":
            return {"rows": []}
        version = "odyssey-perseus-eng3" if "eng3" in source_record_id else "odyssey-perseus-grc2"
        text = (
            "Tell me, Muse, of the man of many ways"
            if version.endswith("eng3")
            else "ἄνδρα μοι ἔννεπε, μοῦσα, πολύτροπον"
        )
        return {
            "rows": [
                {
                    "text_unit_id": source_record_id,
                    "version_id": version,
                    "book": 1,
                    "line_start": 1,
                    "line_end": 1,
                    "citation": "Od. 1.1",
                    "cts_urn": "urn:cts:greekLit:tlg0012.tlg002.perseus-grc2:1.1",
                    "original_text": text,
                    "normalized_text": text,
                    "text_sha256": UNIT_HASH,
                    "source_document_id": "odyssey-document:1",
                    "source_version_hash": VERSION_HASH,
                    "source_url": "https://example.test/source",
                    "bibliographic_description": "Pinned test edition",
                    "display_decision": "full_text_no_bulk_export",
                }
            ]
        }

    async def get_odyssey_scholarly_source(self, source_record_id: str) -> dict[str, Any]:
        if source_record_id == "scholarship:reviewed-1":
            return {
                "rows": [
                    {
                        "scholarly_source_id": source_record_id,
                        "citation_text": "Scholar 2020, 42.",
                    }
                ]
            }
        return {"rows": []}

    async def get_odyssey_token(self, token_id: str) -> dict[str, Any]:
        return {
            "rows": [
                {
                    "token_id": token_id,
                    "text_unit_id": "text-unit:grc2:1.1",
                    "version_id": "odyssey-perseus-grc2",
                    "citation": "Od. 1.1",
                    "cts_urn": "urn:cts:greekLit:tlg0012.tlg002.perseus-grc2:1.1",
                    "book": 1,
                    "line": 1,
                    "char_start": 0,
                    "char_end": 5,
                    "surface": "ἄνδρα",
                }
            ]
        }


def _greek_claim(quote: str = "ἄνδρα") -> dict[str, Any]:
    return {
        "claim_text": "The poem opens by invoking a man.",
        "claim_category": "language",
        "evidence_class": "PRIMARY_GREEK_EXPLICIT",
        "confidence": "HIGH",
        "evidence": [
            {
                "support_role": "supports",
                "source_kind": "text_span",
                "source_record_id": "text-unit:grc2:1.1",
                "version_id": "odyssey-perseus-grc2",
                "source_quote": quote,
                "source_start": 0,
                "source_end": 5,
            }
        ],
    }


def test_exact_claim_validation_and_trusted_publication_boundary() -> None:
    service = ClaimValidationService(FakeClaimMcp)
    claim = asyncio.run(service.create(ClaimCreate.model_validate(_greek_claim())))

    assert claim.evidence[0].validation_status == "valid"
    assert claim.evidence[0].source_unit_hash == UNIT_HASH
    assert not service.publication_decision(claim.claim_id).allowed

    trusted = service.review(
        claim.claim_id,
        status=ClaimReviewStatus.TRUSTED,
        reviewer_id="curator:1",
        note="Exact Greek support reviewed.",
    )
    decision = service.publication_decision(claim.claim_id)

    assert trusted.evidence[0].trusted
    assert decision.allowed


def test_invalid_quote_is_retained_but_cannot_be_trusted_for_publication() -> None:
    service = ClaimValidationService(FakeClaimMcp)
    candidate = _greek_claim("ἄνδρε")
    claim = asyncio.run(service.create(ClaimCreate.model_validate(candidate)))
    service.review(
        claim.claim_id,
        status=ClaimReviewStatus.TRUSTED,
        reviewer_id="curator:1",
        note="Testing invalid evidence.",
    )

    assert claim.evidence[0].validation_status == "invalid"
    assert "does not match" in claim.evidence[0].validation_errors[0]
    assert not service.publication_decision(claim.claim_id).allowed


def test_translation_dependency_conflict_matrix_and_trace() -> None:
    service = ClaimValidationService(FakeClaimMcp)
    text = "Tell me, Muse, of the man of many ways"
    claim = asyncio.run(
        service.create(
            ClaimCreate.model_validate(
                {
                    "claim_text": "Murray renders the opening as ‘the man of many ways’.",
                    "claim_category": "translation",
                    "evidence_class": "TRANSLATION_WORDING",
                    "confidence": "MEDIUM",
                    "evidence": [
                        {
                            "support_role": "supports",
                            "source_kind": "text_span",
                            "source_record_id": "text-unit:eng3:1.1",
                            "version_id": "odyssey-perseus-eng3",
                            "source_quote": "man of many ways",
                            "source_start": text.index("man"),
                            "source_end": len(text),
                        },
                        {
                            "support_role": "conflicts",
                            "source_kind": "scholarship",
                            "source_record_id": "scholarship:reviewed-1",
                            "citation": "Scholar 2020, 42.",
                        },
                    ],
                }
            )
        )
    )

    matrix = service.matrix()[0]
    trace = asyncio.run(service.trace(claim.claim_id))

    assert claim.translation_dependent
    assert claim.translation_version_ids == ("odyssey-perseus-eng3",)
    assert len(matrix.supports) == 1
    assert len(matrix.conflicts) == 1
    assert "Depends on wording" in matrix.limitations[0]
    assert trace.evidence_chain[0]["source"]["source_url"] == "https://example.test/source"  # type: ignore[index]


def test_claim_api_displays_unsupported_questions_and_rejects_publication() -> None:
    service = ClaimValidationService(FakeClaimMcp)
    app = create_app(claim_service=service)
    client = TestClient(app)
    response = client.post(
        "/api/v1/claims",
        json={
            "claim_text": "The poem identifies the historical location of Ogygia.",
            "claim_category": "geography",
            "evidence_class": "UNSUPPORTED",
            "confidence": "UNKNOWN",
            "unsupported_question": "Where was Ogygia historically located?",
            "evidence": [],
        },
    )
    claim_id = response.json()["claim_id"]
    publication = client.post(f"/api/v1/claims/{claim_id}/publication")

    assert response.status_code == 201
    assert client.get("/api/v1/claims/matrix").json()[0]["evidence_class"] == "UNSUPPORTED"
    assert publication.status_code == 409
    assert "absences" in publication.json()["detail"]["reasons"][0]
