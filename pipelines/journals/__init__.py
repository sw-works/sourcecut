from pipelines.journals.gutenberg import (
    download_gutenberg_text,
    parse_journal_entries,
    read_gutenberg_text,
    serialize_entries,
    strip_gutenberg_wrapper,
)
from pipelines.journals.passages import segment_entries, segment_entry

__all__ = [
    "download_gutenberg_text",
    "parse_journal_entries",
    "read_gutenberg_text",
    "serialize_entries",
    "segment_entries",
    "segment_entry",
    "strip_gutenberg_wrapper",
]
