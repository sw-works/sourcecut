"""The Lewis and Clark corpus, described the way the Odyssey corpus is.

This corpus predates the registry: it was loaded straight into `sources` and
`passages` while the registry was built for the second corpus. Registering it
here is what lets one page say, of both corpora, where the text came from, who
may show it, and how far its ingestion has run.

Nothing here is a claim about content. It is provenance: editions, publication
years, the rights that govern display, and the parsers that turned each text
into dated entries.
"""

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

GUTENBERG_EBOOK = "https://www.gutenberg.org/ebooks/8419"
ARCHIVE_ITEM = "https://archive.org/details/gasssjournalofle00gass"

PUBLIC_DOMAIN = LicenseRecord(
    license_id="public-domain-us-pre-1929",
    spdx_or_rights_code="PD-US",
    display_name="Public domain in the United States",
    canonical_url="https://www.gutenberg.org/policy/permission.html",
    attribution_template="{title}. {editor}. Public domain.",
    share_alike=False,
    commercial_use_allowed=True,
    derivatives_allowed=True,
    bulk_export_allowed=True,
    notes=(
        "Both editions were published well before 1929 and their transcriptions carry no "
        "additional rights claim that restricts research use."
    ),
)

LEWIS_AND_CLARK_CORPUS = CorpusRecord(
    corpus_id="lewis-and-clark",
    title="Lewis and Clark expedition journals",
    description=(
        "The journals three men kept on the expedition of 1804–1806, segmented into dated "
        "entries and passages, with observations extracted against the exact characters "
        "they came from."
    ),
    default_work_id="lewis-and-clark-journals",
    adapter_version="lewis-and-clark-v1",
    display_policy=DisplayDecision.FULL_TEXT_AND_EXPORT,
    status=CorpusStatus.ACTIVE,
)

LEWIS_AND_CLARK_WORK = WorkRecord(
    work_id="lewis-and-clark-journals",
    corpus_id="lewis-and-clark",
    cts_work_urn="",
    author_display_name="Meriwether Lewis, William Clark, Patrick Gass",
    title="Journals of the Lewis and Clark expedition",
    original_language="eng",
    book_count=2,
    metadata={
        "expedition_start": "1804-05-14",
        "expedition_end": "1806-09-23",
        "diarists": ["Meriwether Lewis", "William Clark", "Patrick Gass"],
    },
)

LEWIS_AND_CLARK_VERSIONS = (
    SourceVersionRecord(
        version_id="gutenberg-8419",
        work_id="lewis-and-clark-journals",
        cts_version_urn="",
        version_type=VersionType.EDITION,
        language="eng",
        label="The Journals of Lewis and Clark",
        editor_names=("Meriwether Lewis", "William Clark"),
        bibliographic_description=(
            "The Journals of Lewis and Clark, 1804–1806. Project Gutenberg ebook 8419, "
            "from the edition of the original journals."
        ),
        publication_year=1905,
        source_url=GUTENBERG_EBOOK,
        upstream_revision="pg8419",
        license_id=PUBLIC_DOMAIN.license_id,
        display_decision=DisplayDecision.FULL_TEXT_AND_EXPORT,
        raw_manifest={
            "download_url": "https://www.gutenberg.org/cache/epub/8419/pg8419.txt",
            "parser": "pipelines/journals/gutenberg.py",
            "parser_version": "gutenberg-heading-v1",
            "entry_heading": "[Lewis, September 16, 1805]",
        },
    ),
    SourceVersionRecord(
        version_id="archive-gasssjournalofle00gass",
        work_id="lewis-and-clark-journals",
        cts_version_urn="",
        version_type=VersionType.WITNESS,
        language="eng",
        label="Gass's Journal of the Lewis and Clark Expedition",
        editor_names=("James Kendall Hosmer",),
        bibliographic_description=(
            "Patrick Gass. Gass's Journal of the Lewis and Clark Expedition. "
            "James Kendall Hosmer, editor. Chicago: A. C. McClurg, 1904."
        ),
        publication_year=1904,
        source_url=ARCHIVE_ITEM,
        upstream_revision="gasssjournalofle00gass",
        license_id=PUBLIC_DOMAIN.license_id,
        display_decision=DisplayDecision.FULL_TEXT_AND_EXPORT,
        raw_manifest={
            "download_url": (
                "https://archive.org/download/gasssjournalofle00gass/"
                "gasssjournalofle00gass_djvu.txt"
            ),
            "parser": "pipelines/journals/gass.py",
            "parser_version": "gass-hosmer-1904-ocr-heading-v1",
            "entry_heading": "Monday 16th September, 1805.",
        },
    ),
)


class LewisAndClarkCorpusAdapter:
    corpus_id = "lewis-and-clark"

    def summary(self) -> CorpusRecord:
        return LEWIS_AND_CLARK_CORPUS

    def detail(self) -> CorpusDetail:
        return CorpusDetail(
            corpus=LEWIS_AND_CLARK_CORPUS,
            works=(LEWIS_AND_CLARK_WORK,),
            versions=LEWIS_AND_CLARK_VERSIONS,
            licenses=(PUBLIC_DOMAIN,),
            release_manifest_id="lewis-and-clark-gutenberg-8419-archive-gass",
            known_limitations=(
                "Gass is an OCR transcription of a 1904 edition; his entries carry the "
                "editor's spelling, not the manuscript's.",
                "Only the segments listed in data/reference/research_scopes.json have had "
                "observations extracted; the rest of the corpus is loaded but unextracted.",
                "The expedition's own maps and photographs of the route are held by other "
                "institutions; archive references come from the Library of Congress.",
            ),
        )
