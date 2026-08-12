from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from sourcecut_api.models.export import (
    BoardExportRequest,
    ExportFormat,
    ExportJob,
    ProvenanceManifest,
    SharedBoard,
    ShareLink,
)
from sourcecut_api.models.odyssey_board import BoardItemKind, OdysseyBoard
from sourcecut_api.services.odyssey_board import OdysseyBoardService
from sourcecut_api.telemetry import add_counter, observe_histogram, telemetry_span

PUBLIC_ASSET_RIGHTS = {"PUBLIC_DOMAIN", "CC_BY", "CC_BY_SA", "CC0"}
FONT_ROOT = Path(__file__).resolve().parent.parent / "assets" / "fonts"
REGULAR_FONT = FONT_ROOT / "NotoSerif-Regular.ttf"
BOLD_FONT = FONT_ROOT / "NotoSerif-Bold.ttf"


class ExportNotFoundError(LookupError):
    pass


class ExportTokenError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    job: ExportJob
    content: bytes


@dataclass(frozen=True, slots=True)
class StoredShare:
    link: ShareLink
    shared: SharedBoard


class OdysseyExportService:
    def __init__(self, boards: OdysseyBoardService, *, secret: bytes | None = None) -> None:
        self._boards = boards
        self._secret = (
            secret
            or os.getenv("SOURCECUT_EXPORT_SIGNING_SECRET", "").encode()
            or secrets.token_bytes(32)
        )
        self._artifacts: dict[str, StoredArtifact] = {}
        self._shares: dict[str, StoredShare] = {}

    def create_export(self, board_id: str, request: BoardExportRequest) -> ExportJob:
        started = datetime.now(UTC)
        with telemetry_span(
            "sourcecut.odyssey.export",
            {
                "sourcecut.corpus.id": "odyssey",
                "sourcecut.export.format": request.format.value,
                "sourcecut.export.display_policy": request.display_policy,
            },
        ):
            revision = self._boards.revision(board_id, request.revision_id)
            board, omitted = _apply_rights(revision.document, request.display_policy)
            manifest = _manifest(board, omitted)
            content, content_type, extension = _render(request.format, board, manifest)
        now = datetime.now(UTC)
        job_id = str(uuid.uuid4())
        expires_at = now + timedelta(hours=1)
        token = self._signed_token(job_id, expires_at)
        job = ExportJob(
            job_id=job_id,
            board_id=board_id,
            revision_id=request.revision_id,
            format=request.format,
            status="complete",
            display_policy=request.display_policy,
            rights_decision=(
                f"{len(omitted)} restricted asset(s) reduced to metadata-only"
                if omitted
                else "all selected records are eligible for this display policy"
            ),
            artifact_sha256=hashlib.sha256(content).hexdigest(),
            manifest_sha256=hashlib.sha256(manifest.model_dump_json().encode()).hexdigest(),
            content_type=content_type,
            filename=f"odyssey-board-{board_id[:8]}-{request.revision_id[:8]}.{extension}",
            download_url=f"/api/v1/exports/{job_id}/download?token={token}",
            expires_at=expires_at,
            created_at=now,
        )
        self._artifacts[job_id] = StoredArtifact(job=job, content=content)
        add_counter(
            "sourcecut.odyssey.exports",
            1,
            {"format": request.format.value, "status": "complete"},
        )
        observe_histogram(
            "sourcecut.odyssey.export.duration",
            (datetime.now(UTC) - started).total_seconds() * 1000,
            {"format": request.format.value},
        )
        return job

    def download(self, job_id: str, token: str) -> StoredArtifact:
        artifact = self._artifacts.get(job_id)
        if artifact is None:
            raise ExportNotFoundError(job_id)
        self._verify_token(token, job_id, artifact.job.expires_at)
        return artifact

    def share(self, board_id: str, revision_id: str, expires_in_days: int) -> ShareLink:
        revision = self._boards.revision(board_id, revision_id)
        board, omitted = _apply_rights(revision.document, "public_reusable")
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=expires_in_days)
        share_id = secrets.token_urlsafe(24)
        token = self._signed_token(share_id, expires_at)
        link = ShareLink(
            share_token=token,
            board_id=board_id,
            revision_id=revision_id,
            share_url=f"/api/v1/shared/boards/{token}",
            omitted_item_count=len(omitted),
            expires_at=expires_at,
            created_at=now,
        )
        shared = SharedBoard(
            board=board,
            provenance_manifest=_manifest(board, omitted),
            omitted_item_count=len(omitted),
            rights_notice=(
                f"{len(omitted)} restricted asset(s) are shown as metadata only."
                if omitted
                else "All displayed records passed the public rights filter."
            ),
            expires_at=expires_at,
        )
        self._shares[share_id] = StoredShare(link=link, shared=shared)
        return link

    def shared_board(self, token: str) -> SharedBoard:
        share_id, expiry = self._decode_token(token)
        stored = self._shares.get(share_id)
        if stored is None:
            raise ExportNotFoundError(share_id)
        self._verify_expiry(expiry, stored.link.expires_at)
        return stored.shared

    def _signed_token(self, subject: str, expires_at: datetime) -> str:
        payload = f"{subject}.{int(expires_at.timestamp())}"
        signature = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{signature}"

    def _decode_token(self, token: str) -> tuple[str, int]:
        try:
            subject, expiry, signature = token.rsplit(".", 2)
            expected = hmac.new(
                self._secret, f"{subject}.{expiry}".encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ExportTokenError("invalid export signature")
            return subject, int(expiry)
        except (ValueError, TypeError) as error:
            raise ExportTokenError("invalid export token") from error

    def _verify_token(self, token: str, subject: str, expires_at: datetime) -> None:
        token_subject, expiry = self._decode_token(token)
        if token_subject != subject:
            raise ExportTokenError("export token does not match artifact")
        self._verify_expiry(expiry, expires_at)

    @staticmethod
    def _verify_expiry(expiry: int, expected: datetime) -> None:
        if expiry != int(expected.timestamp()) or datetime.now(UTC) >= expected:
            raise ExportTokenError("export token has expired")


def _apply_rights(board: OdysseyBoard, policy: str) -> tuple[OdysseyBoard, tuple[str, ...]]:
    if policy == "private":
        return board, ()
    omitted: list[str] = []
    sections = []
    for section in board.sections:
        items = []
        for item in section.items:
            if item.kind == BoardItemKind.ASSET and item.rights_status not in PUBLIC_ASSET_RIGHTS:
                omitted.append(item.item_id)
                item = item.model_copy(
                    update={
                        "metadata": {
                            "display": "metadata_only",
                            "omission_reason": "image rights do not permit public reuse",
                        }
                    }
                )
            items.append(item)
        sections.append(section.model_copy(update={"items": tuple(items)}))
    return board.model_copy(update={"sections": tuple(sections)}), tuple(omitted)


def _manifest(board: OdysseyBoard, omitted: tuple[str, ...]) -> ProvenanceManifest:
    references = tuple(
        sorted({item.reference_id for section in board.sections for item in section.items})
    )
    digest_input = json.dumps(
        {
            "board": board.board_id,
            "revision": board.revision_id,
            "release": board.release_pins.release_manifest_id,
            "refs": references,
            "omitted": omitted,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return ProvenanceManifest(
        manifest_id=f"manifest-{hashlib.sha256(digest_input.encode()).hexdigest()[:20]}",
        board_id=board.board_id,
        revision_id=board.revision_id,
        release_manifest_id=board.release_pins.release_manifest_id,
        corpus_revision=board.release_pins.corpus_revision,
        annotation_release_ids=board.release_pins.annotation_release_ids,
        active_versions=board.release_pins.active_versions,
        active_hypotheses=board.release_pins.active_hypotheses,
        source_session_id=board.source_session_id,
        source_references=references,
        omitted_item_ids=omitted,
        generated_at=datetime.now(UTC),
    )


def _render(
    format_: ExportFormat, board: OdysseyBoard, manifest: ProvenanceManifest
) -> tuple[bytes, str, str]:
    renderers = {
        ExportFormat.JSON: lambda: _json(board, manifest),
        ExportFormat.MARKDOWN: lambda: _markdown(board, manifest).encode(),
        ExportFormat.HTML: lambda: _html(board, manifest).encode(),
        ExportFormat.PDF: lambda: _pdf(board, manifest),
        ExportFormat.CITATIONS_TEXT: lambda: _citations(board, markdown=False).encode(),
        ExportFormat.CITATIONS_MARKDOWN: lambda: _citations(board, markdown=True).encode(),
        ExportFormat.CSL_JSON: lambda: _csl(board),
        ExportFormat.BIBTEX: lambda: _bibtex(board).encode(),
        ExportFormat.GEOJSON: lambda: _geojson(board),
        ExportFormat.MAP_PNG: lambda: _map_png(board, manifest),
    }
    content_types = {
        ExportFormat.JSON: ("application/json", "json"),
        ExportFormat.MARKDOWN: ("text/markdown; charset=utf-8", "md"),
        ExportFormat.HTML: ("text/html; charset=utf-8", "html"),
        ExportFormat.PDF: ("application/pdf", "pdf"),
        ExportFormat.CITATIONS_TEXT: ("text/plain; charset=utf-8", "txt"),
        ExportFormat.CITATIONS_MARKDOWN: ("text/markdown; charset=utf-8", "md"),
        ExportFormat.CSL_JSON: ("application/vnd.citationstyles.csl+json", "json"),
        ExportFormat.BIBTEX: ("application/x-bibtex", "bib"),
        ExportFormat.GEOJSON: ("application/geo+json", "geojson"),
        ExportFormat.MAP_PNG: ("image/png", "png"),
    }
    content_type, extension = content_types[format_]
    return renderers[format_](), content_type, extension


def _json(board: OdysseyBoard, manifest: ProvenanceManifest) -> bytes:
    return json.dumps(
        {
            "board": board.model_dump(mode="json"),
            "provenance_manifest": manifest.model_dump(mode="json"),
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode()


def _markdown(board: OdysseyBoard, manifest: ProvenanceManifest) -> str:
    lines = [f"# {board.title}", "", board.question, "", board.summary, ""]
    for section in board.sections:
        lines.extend([f"## {section.title}", ""])
        if section.generated_text and not section.hidden_generated_text:
            lines.extend(["*Generated synthesis*", "", section.generated_text, ""])
        if section.user_notes:
            lines.extend(["*User notes*", "", section.user_notes, ""])
        lines.extend(
            f"- **{item.label}** ({item.kind.value}) - {item.citation or item.reference_id}"
            for item in section.items
        )
        lines.append("")
    lines.extend(["## Warnings and unresolved questions", ""])
    lines.extend(
        f"- {value}" for value in board.warnings + board.conflicts + board.unsupported_questions
    )
    lines.extend(
        [
            "",
            "## Provenance",
            "",
            f"Manifest: `{manifest.manifest_id}`",
            f"Corpus release: `{manifest.release_manifest_id}`",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _html(board: OdysseyBoard, manifest: ProvenanceManifest) -> str:
    sections = "".join(
        f"<section><h2>{escape(section.title)}</h2>"
        + (
            "<div class='generated'><b>Generated synthesis</b>"
            f"<p>{escape(section.generated_text)}</p></div>"
            if section.generated_text and not section.hidden_generated_text
            else ""
        )
        + (
            f"<div class='notes'><b>User notes</b><p>{escape(section.user_notes)}</p></div>"
            if section.user_notes
            else ""
        )
        + "<ul>"
        + "".join(
            f"<li><strong>{escape(item.label)}</strong>"
            f"<small>{escape(item.citation or item.reference_id)}</small></li>"
            for item in section.items
        )
        + "</ul></section>"
        for section in board.sections
    )
    warnings = "".join(
        f"<li>{escape(value)}</li>"
        for value in board.warnings + board.conflicts + board.unsupported_questions
    )
    css = (
        "@page{margin:18mm}body{font:16px/1.55 Georgia,serif;max-width:900px;"
        "margin:auto;color:#1b1a18}header{border-bottom:3px solid #b36b21;padding:3rem 0}"
        "h1{font-size:3rem;line-height:1}section{break-inside:avoid;padding:1.5rem 0;"
        "border-bottom:1px solid #bbb}small{display:block;color:#666}.generated{border-left:"
        "3px solid #b36b21;padding-left:1rem}.notes{background:#f3eee5;padding:1rem}"
        "footer{margin-top:3rem;font-size:.8rem}"
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(board.title)}</title><style>{css}</style></head><body>"
        f"<header><p>SourceCut / Odyssey</p><h1>{escape(board.title)}</h1>"
        f"<p>{escape(board.question)}</p></header>{sections}"
        f"<section><h2>Warnings and unresolved questions</h2><ul>{warnings}</ul></section>"
        f"<footer>Provenance {escape(manifest.manifest_id)} · "
        f"{escape(manifest.release_manifest_id)}</footer></body></html>"
    )


def _citations(board: OdysseyBoard, *, markdown: bool) -> str:
    citations = sorted(
        {item.citation or item.reference_id for section in board.sections for item in section.items}
    )
    if markdown:
        return "# Citations\n\n" + "\n".join(f"- {citation}" for citation in citations) + "\n"
    return "\n".join(citations) + "\n"


def _csl(board: OdysseyBoard) -> bytes:
    records = [
        {
            "id": version,
            "type": "book",
            "title": "Odyssey",
            "author": [{"literal": "Homer"}],
            "note": board.release_pins.release_manifest_id,
        }
        for version in board.release_pins.active_versions
    ]
    records.extend(
        {"id": item.reference_id, "type": "graphic", "title": item.label, "note": item.citation}
        for section in board.sections
        for item in section.items
        if item.kind == BoardItemKind.ASSET
    )
    return json.dumps(records, ensure_ascii=False, indent=2).encode()


def _bibtex(board: OdysseyBoard) -> str:
    entries = [
        _bib_entry(
            "book",
            version,
            (
                "author = {Homer}",
                "title = {Odyssey}",
                f"note = {{{board.release_pins.release_manifest_id}}}",
            ),
        )
        for version in board.release_pins.active_versions
    ]
    entries.extend(
        _bib_entry(
            "misc",
            _bib_key(item.reference_id),
            (f"title = {{{item.label}}}", f"note = {{{item.citation}}}"),
        )
        for section in board.sections
        for item in section.items
        if item.kind == BoardItemKind.ASSET
    )
    return "\n\n".join(entries) + "\n"


def _bib_key(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value).strip("-")


def _bib_entry(kind: str, key: str, fields: tuple[str, ...]) -> str:
    return f"@{kind}{{{key},\n  " + ",\n  ".join(fields) + "\n}"


def _geojson(board: OdysseyBoard) -> bytes:
    features = []
    for section in board.sections:
        for item in section.items:
            if item.kind != BoardItemKind.MAP_VIEW:
                continue
            coordinates = item.metadata.get("coordinates")
            geometry = (
                {"type": "Point", "coordinates": coordinates}
                if isinstance(coordinates, list) and len(coordinates) == 2
                else None
            )
            features.append(
                {
                    "type": "Feature",
                    "id": item.item_id,
                    "geometry": geometry,
                    "properties": {
                        "feature_kind": item.kind.value,
                        "label": item.label,
                        "hypothesis_id": item.metadata.get("hypothesis_id", item.reference_id),
                        "confidence": item.metadata.get("confidence", "unknown"),
                        "citation_ids": [item.citation] if item.citation else [],
                        "display_style": item.metadata.get("display_style", "hypothesis"),
                    },
                }
            )
    return json.dumps(
        {"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2
    ).encode()


def _map_png(board: OdysseyBoard, manifest: ProvenanceManifest) -> bytes:
    image = Image.new("RGB", (1200, 700), "#e9e1d2")
    draw = ImageDraw.Draw(image)
    font = _pil_font(24)
    title = _pil_font(44)
    draw.text((60, 48), board.title, fill="#171917", font=title)
    draw.text((60, 112), "Hypothesis-aware map export", fill="#8a541e", font=font)
    draw.rectangle((60, 175, 1140, 555), outline="#635f56", width=2)
    map_items = [
        item
        for section in board.sections
        for item in section.items
        if item.kind == BoardItemKind.MAP_VIEW
    ]
    located = [
        item
        for item in map_items
        if isinstance(item.metadata.get("coordinates"), list)
        and len(item.metadata["coordinates"]) == 2
    ]
    if located:
        for item in located:
            longitude, latitude = item.metadata["coordinates"]
            x = int(80 + (float(longitude) + 180) / 360 * 1040)
            y = int(195 + (90 - float(latitude)) / 180 * 340)
            draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill="#b36b21", outline="#171917")
            draw.text((x + 14, y - 12), item.label, fill="#171917", font=font)
    else:
        draw.text((360, 340), "No located points in this board revision", fill="#635f56", font=font)
    draw.text(
        (60, 585),
        "Legend: amber point = selected hypothesis; "
        "unlocated records remain in GeoJSON with null geometry",
        fill="#171917",
        font=_pil_font(18),
    )
    draw.text(
        (60, 625),
        f"Attribution: SourceCut / Odyssey · {manifest.release_manifest_id} · "
        f"{manifest.manifest_id}",
        fill="#635f56",
        font=_pil_font(17),
    )
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _pil_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return (
        ImageFont.truetype(str(REGULAR_FONT), size)
        if REGULAR_FONT.exists()
        else ImageFont.load_default()
    )


def _pdf(board: OdysseyBoard, manifest: ProvenanceManifest) -> bytes:
    if not REGULAR_FONT.exists() or not BOLD_FONT.exists():
        raise RuntimeError("embedded Unicode PDF fonts are unavailable")
    if "SourceCutNoto" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("SourceCutNoto", str(REGULAR_FONT)))
        pdfmetrics.registerFont(TTFont("SourceCutNotoBold", str(BOLD_FONT)))
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=board.title,
        author="SourceCut",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "OdysseyBody",
        parent=styles["BodyText"],
        fontName="SourceCutNoto",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#27251f"),
        spaceAfter=6,
    )
    heading = ParagraphStyle(
        "OdysseyHeading",
        parent=body,
        fontName="SourceCutNotoBold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#171917"),
        spaceBefore=12,
        spaceAfter=8,
    )
    title = ParagraphStyle(
        "OdysseyTitle",
        parent=heading,
        fontSize=30,
        leading=34,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#8a541e"),
        spaceAfter=14,
    )
    small = ParagraphStyle(
        "OdysseySmall", parent=body, fontSize=7.5, leading=10, textColor=colors.HexColor("#635f56")
    )
    story = [
        Paragraph("SOURCECUT / ODYSSEY", small),
        Spacer(1, 18 * mm),
        Paragraph(escape(board.title), title),
        Paragraph(escape(board.question), body),
        Spacer(1, 8 * mm),
        HRFlowable(color=colors.HexColor("#b36b21")),
        Spacer(1, 8 * mm),
        Paragraph(escape(board.summary or "Research board"), body),
        Spacer(1, 12 * mm),
        Paragraph(f"Pinned release: {escape(board.release_pins.release_manifest_id)}", small),
        Paragraph(f"Revision: {escape(board.revision_id)}", small),
        PageBreak(),
    ]
    for section in board.sections:
        story.append(Paragraph(escape(section.title), heading))
        if section.generated_text and not section.hidden_generated_text:
            story.append(Paragraph("GENERATED SYNTHESIS", small))
            story.append(Paragraph(escape(section.generated_text), body))
        if section.user_notes:
            story.append(Paragraph("USER NOTES", small))
            story.append(Paragraph(escape(section.user_notes), body))
        for item in section.items:
            detail = escape(item.citation or item.reference_id)
            if item.metadata.get("display") == "metadata_only":
                detail += " · image omitted by rights policy"
            story.append(
                Paragraph(f"<b>{escape(item.label)}</b><br/><font size='7'>{detail}</font>", body)
            )
        story.append(HRFlowable(color=colors.HexColor("#d3ccc0"), thickness=0.5))
    story.extend([PageBreak(), Paragraph("Warnings and unresolved questions", heading)])
    for warning in board.warnings + board.conflicts + board.unsupported_questions:
        story.append(Paragraph(f"• {escape(warning)}", body))
    story.extend(
        [
            Paragraph("Provenance manifest", heading),
            Paragraph(
                f"{escape(manifest.manifest_id)}<br/>"
                f"{escape(manifest.release_manifest_id)}<br/>"
                f"Corpus revision {escape(manifest.corpus_revision)}",
                small,
            ),
        ]
    )

    def footer(canvas: object, doc: object) -> None:
        canvas.saveState()
        canvas.setFont("SourceCutNoto", 7)
        canvas.setFillColor(colors.HexColor("#635f56"))
        canvas.drawString(22 * mm, 11 * mm, manifest.manifest_id)
        canvas.drawRightString(A4[0] - 22 * mm, 11 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
