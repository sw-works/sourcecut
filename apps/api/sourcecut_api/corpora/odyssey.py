from __future__ import annotations

from sourcecut_api.models.corpus import (
    CorpusDetail,
    CorpusRecord,
    CorpusStatus,
    DisplayDecision,
    LicenseRecord,
    SourceVersionRecord,
    VersionType,
    WorkRecord,
)

PERSEUS_REVISION = "790c84289edbdbe289dd7b752bfea29f0af4299d"
PERSEUS_ROOT = "https://github.com/PerseusDL/canonical-greekLit"
ODYSSEY_ROOT = f"{PERSEUS_ROOT}/tree/{PERSEUS_REVISION}/data/tlg0012/tlg002"

PERSEUS_LICENSE = LicenseRecord(
    license_id="cc-by-sa-4.0-perseus-default",
    spdx_or_rights_code="CC-BY-SA-4.0",
    display_name="Creative Commons Attribution-ShareAlike 4.0 International",
    canonical_url="https://creativecommons.org/licenses/by-sa/4.0/",
    attribution_template="Text provided by the Perseus Digital Library.",
    share_alike=True,
    commercial_use_allowed=True,
    derivatives_allowed=True,
    bulk_export_allowed=True,
    notes=(
        "Perseus states that component rights vary and not all headers have been checked. "
        "The public display decision remains provisional until each Odyssey TEI header is audited."
    ),
)

TREEBANK_LICENSE = LicenseRecord(
    license_id="cc-by-sa-3.0-us",
    spdx_or_rights_code="CC-BY-SA-3.0-US",
    display_name="Creative Commons Attribution-ShareAlike 3.0 United States",
    canonical_url="https://creativecommons.org/licenses/by-sa/3.0/us/",
    attribution_template=(
        "Morphological annotations from the Perseus Ancient Greek Dependency Treebank."
    ),
    share_alike=True,
    commercial_use_allowed=True,
    derivatives_allowed=True,
    bulk_export_allowed=True,
)

ODYSSEY_CORPUS = CorpusRecord(
    corpus_id="odyssey",
    title="SourceCut Odyssey",
    description=(
        "An evidence-backed research environment for Homer's Odyssey, its translations, "
        "narrative structure, geography, and visual reception."
    ),
    default_work_id="odyssey",
    adapter_version="odyssey-v1",
    display_policy=DisplayDecision.FULL_TEXT_NO_BULK_EXPORT,
    status=CorpusStatus.PREVIEW,
)

ODYSSEY_WORK = WorkRecord(
    work_id="odyssey",
    corpus_id="odyssey",
    cts_work_urn="urn:cts:greekLit:tlg0012.tlg002",
    author_display_name="Homer",
    title="Odyssey",
    original_language="grc",
    book_count=24,
    metadata={"greek_title": "Ὀδύσσεια"},
)

ODYSSEY_VERSIONS = (
    SourceVersionRecord(
        version_id="odyssey-perseus-grc2",
        work_id="odyssey",
        cts_version_urn="urn:cts:greekLit:tlg0012.tlg002.perseus-grc2",
        version_type=VersionType.EDITION,
        language="grc",
        label="Ὀδύσσεια — Murray edition",
        editor_names=("A. T. Murray",),
        bibliographic_description=(
            "Homer. The Odyssey, Volume 1–2. A. T. Murray, editor. London: William "
            "Heinemann; New York: G. P. Putnam's Sons, 1919."
        ),
        publication_year=1919,
        source_url=f"{ODYSSEY_ROOT}/tlg0012.tlg002.perseus-grc2.xml",
        upstream_revision=PERSEUS_REVISION,
        license_id=PERSEUS_LICENSE.license_id,
        display_decision=DisplayDecision.FULL_TEXT_NO_BULK_EXPORT,
        raw_manifest={
            "upstream_repository": PERSEUS_ROOT,
            "upstream_path": "data/tlg0012/tlg002/tlg0012.tlg002.perseus-grc2.xml",
        },
    ),
    SourceVersionRecord(
        version_id="odyssey-perseus-eng3",
        work_id="odyssey",
        cts_version_urn="urn:cts:greekLit:tlg0012.tlg002.perseus-eng3",
        version_type=VersionType.TRANSLATION,
        language="eng",
        label="Odyssey — Murray translation",
        translator_names=("A. T. Murray",),
        bibliographic_description=(
            "Homer. The Odyssey, Volume 1–2. A. T. Murray, translator. London: William "
            "Heinemann; New York: G. P. Putnam's Sons, 1919."
        ),
        publication_year=1919,
        source_url=f"{ODYSSEY_ROOT}/tlg0012.tlg002.perseus-eng3.xml",
        upstream_revision=PERSEUS_REVISION,
        license_id=PERSEUS_LICENSE.license_id,
        display_decision=DisplayDecision.FULL_TEXT_NO_BULK_EXPORT,
        raw_manifest={
            "upstream_repository": PERSEUS_ROOT,
            "upstream_path": "data/tlg0012/tlg002/tlg0012.tlg002.perseus-eng3.xml",
        },
    ),
    SourceVersionRecord(
        version_id="odyssey-perseus-eng4",
        work_id="odyssey",
        cts_version_urn="urn:cts:greekLit:tlg0012.tlg002.perseus-eng4",
        version_type=VersionType.TRANSLATION,
        language="eng",
        label="Odyssey — Butler translation, revised",
        translator_names=("Samuel Butler",),
        editor_names=("Timothy Power", "Gregory Nagy"),
        bibliographic_description=(
            "Homer. The Odyssey: rendered into English prose for the use of those who cannot "
            "read the original. Samuel Butler, translator; revised by Timothy Power and "
            "Gregory Nagy. London: A. C. Fifield, 1900."
        ),
        publication_year=1900,
        source_url=f"{ODYSSEY_ROOT}/tlg0012.tlg002.perseus-eng4.xml",
        upstream_revision=PERSEUS_REVISION,
        license_id=PERSEUS_LICENSE.license_id,
        display_decision=DisplayDecision.FULL_TEXT_NO_BULK_EXPORT,
        raw_manifest={
            "upstream_repository": PERSEUS_ROOT,
            "upstream_path": "data/tlg0012/tlg002/tlg0012.tlg002.perseus-eng4.xml",
        },
    ),
)


class OdysseyCorpusAdapter:
    corpus_id = "odyssey"

    def summary(self) -> CorpusRecord:
        return ODYSSEY_CORPUS

    def detail(self) -> CorpusDetail:
        return CorpusDetail(
            corpus=ODYSSEY_CORPUS,
            works=(ODYSSEY_WORK,),
            versions=ODYSSEY_VERSIONS,
            licenses=(PERSEUS_LICENSE, TREEBANK_LICENSE),
            release_manifest_id=f"odyssey-perseus-{PERSEUS_REVISION[:12]}",
            known_limitations=(
                "Component-level TEI header rights review is required before public launch.",
                "Text content and source hashes are populated by the E2 ingestion pipeline.",
                "No modern copyrighted translations are included.",
            ),
        )
