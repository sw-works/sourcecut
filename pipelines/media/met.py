from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sourcecut_api.models.media import HistoricalRelationship, MediaAsset, RightsStatus
from sourcecut_api.models.visual_culture import (
    AssetCorpusLink,
    AssetRelationshipAssessment,
    OdysseyAssetMetadata,
    VisualCultureRelease,
)


def load_met_odyssey_release(manifest_path: Path, cache_dir: Path) -> VisualCultureRelease:
    manifest = json.loads(manifest_path.read_text())
    assets = []
    metadata = []
    links = []
    assessments = []
    for record in manifest["objects"]:
        object_id = str(record["object_id"])
        raw_path = cache_dir / "objects" / f"{object_id}.json"
        raw = raw_path.read_text()
        if hashlib.sha256(raw.encode()).hexdigest() != record["raw_sha256"]:
            raise ValueError(f"Pinned Met record hash mismatch: {object_id}")
        payload = json.loads(raw)
        if str(payload["objectID"]) != object_id:
            raise ValueError(f"Met cache identity mismatch: {object_id}")
        public = bool(payload["isPublicDomain"])
        image_path = (
            f"/odyssey/media/{object_id}.jpg" if public and payload.get("primaryImageSmall") else ""
        )
        if image_path and not (cache_dir / "images" / f"{object_id}.jpg").is_file():
            raise ValueError(f"Public-domain Met image is not cached: {object_id}")
        if image_path:
            image_hash = hashlib.sha256(
                (cache_dir / "images" / f"{object_id}.jpg").read_bytes()
            ).hexdigest()
            if image_hash != record["image_sha256"]:
                raise ValueError(f"Pinned Met image hash mismatch: {object_id}")
        relationship = record["relationship"]
        generic = (
            HistoricalRelationship.PERIOD_COMPARATIVE
            if relationship.startswith("ANCIENT_")
            else HistoricalRelationship.LATER_REPRESENTATION
        )
        assets.append(
            MediaAsset(
                asset_id=f"met:{object_id}",
                provider="Metropolitan Museum of Art",
                provider_id=object_id,
                title=payload["title"],
                description=record["production_use"],
                creators=tuple(x["name"] for x in payload.get("constituents") or []),
                asset_type=payload.get("classification") or payload.get("objectName") or "object",
                creation_date_text=payload.get("objectDate", ""),
                subjects=tuple(x["term"] for x in payload.get("tags") or []),
                source_url=payload["objectURL"],
                media_url=payload.get("primaryImageSmall", "") if public else "",
                thumbnail_path=image_path,
                rights_status=RightsStatus.PUBLIC_DOMAIN if public else RightsStatus.RESTRICTED,
                rights_text="Met Open Access: Public Domain"
                if public
                else payload.get("rightsAndReproduction") or "Image not Open Access",
                historical_relationship=generic,
                raw_metadata=raw,
                metadata_sha256=hashlib.sha256(raw.encode()).hexdigest(),
            )
        )
        metadata.append(
            OdysseyAssetMetadata(
                asset_id=f"met:{object_id}",
                institution=payload["repository"],
                object_id=payload["accessionNumber"],
                culture=payload.get("culture", ""),
                period=payload.get("period", ""),
                object_date=payload.get("objectDate", ""),
                object_begin_date=int(payload.get("objectBeginDate") or 0),
                object_end_date=int(payload.get("objectEndDate") or 0),
                medium=payload.get("medium", ""),
                image_rights_status="public_domain" if public else "restricted",
                image_attribution=f"The Metropolitan Museum of Art, {payload['accessionNumber']}",
                cached_image_path=image_path,
                public_display=relationship != "UNRELATED_OR_UNSUPPORTED",
            )
        )
        evidence = []
        for index, (kind, target) in enumerate(record["links"]):
            links.append(
                AssetCorpusLink(
                    asset_link_id=f"asset-link:met:{object_id}:{index}",
                    asset_id=f"met:{object_id}",
                    target_kind=kind,
                    target_id=target,
                    relationship_class=relationship,
                )
            )
            evidence.append(target)
        assessments.append(
            AssetRelationshipAssessment(
                assessment_id=f"asset-assessment:met:{object_id}",
                asset_id=f"met:{object_id}",
                relationship_class=relationship,
                production_use=record["production_use"],
                limitations=record["limitations"],
                evidence_ids=tuple(evidence),
                confidence=record["confidence"],
                verification_status=record["status"],
            )
        )
    release = VisualCultureRelease(
        release_id=manifest["release_id"],
        assets=tuple(assets),
        metadata=tuple(metadata),
        links=tuple(links),
        assessments=tuple(assessments),
    )
    validate_visual_culture_release(release)
    return release


def validate_visual_culture_release(release: VisualCultureRelease) -> None:
    metadata = {item.asset_id: item for item in release.metadata}
    for assessment in release.assessments:
        item = metadata[assessment.asset_id]
        if assessment.relationship_class.startswith("ANCIENT_") and item.object_end_date > 500:
            raise ValueError(f"Ancient relationship is incompatible with date: {item.asset_id}")
        if (
            assessment.relationship_class
            in {
                "LATER_CLASSICAL_RECEPTION",
                "POST_CLASSICAL_RECEPTION",
            }
            and item.object_begin_date < 500
        ):
            raise ValueError(f"Later reception is incompatible with date: {item.asset_id}")
        if assessment.verification_status != "rejected" and not assessment.evidence_ids:
            raise ValueError(f"Displayed asset lacks linked evidence: {item.asset_id}")
        if item.image_rights_status != "public_domain" and item.cached_image_path:
            raise ValueError(f"Restricted image cannot have a public cache path: {item.asset_id}")
        if assessment.verification_status == "rejected" and item.public_display:
            raise ValueError(f"Rejected asset cannot be publicly displayed: {item.asset_id}")
