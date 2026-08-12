from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlencode

from sourcecut_api.models.classical_text import ResolvedCitation

CONVENTIONAL = re.compile(
    r"^(?:Hom(?:er)?[,.]?\s*)?(?:Od(?:yssey)?\.?)?\s*"
    r"(?P<book>\d{1,2})\.(?P<start>\d{1,4})"
    r"(?:\s*[-–—]\s*(?:(?P<end_book>\d{1,2})\.)?(?P<end>\d{1,4}))?$",
    re.IGNORECASE,
)
CTS = re.compile(
    r"^(?P<version>urn:cts:greekLit:tlg0012\.tlg002\.[A-Za-z0-9_-]+):"
    r"(?P<book>\d{1,2})\.(?P<start>\d{1,4})"
    r"(?:-(?:(?P<end_book>\d{1,2})\.)?(?P<end>\d{1,4}))?$"
)


class CitationResolutionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CitationResolver:
    version_urns: dict[str, str]

    def resolve(self, reference: str, version_id: str) -> ResolvedCitation:
        version_urn = self.version_urns.get(version_id)
        if version_urn is None:
            raise CitationResolutionError("Unknown Odyssey version")
        candidate = reference.strip()
        match = CTS.fullmatch(candidate)
        if match is not None:
            if match.group("version") != version_urn:
                raise CitationResolutionError("CTS reference does not match requested version")
        else:
            match = CONVENTIONAL.fullmatch(candidate)
        if match is None:
            raise CitationResolutionError("Invalid Odyssey citation")
        book = int(match.group("book"))
        line_start = int(match.group("start"))
        line_end = int(match.group("end") or line_start)
        end_book = int(match.group("end_book") or book)
        if not 1 <= book <= 24 or end_book != book:
            raise CitationResolutionError("Citation must stay within one of Odyssey books 1–24")
        if line_end < line_start:
            raise CitationResolutionError("Citation line range is reversed")
        if line_end - line_start > 199:
            raise CitationResolutionError("Citation range exceeds 200 lines")
        line_ref = f"{book}.{line_start}"
        if line_end != line_start:
            line_ref += f"-{book}.{line_end}"
        citation = f"Od. {book}.{line_start}"
        if line_end != line_start:
            citation += f"–{line_end}"
        return ResolvedCitation(
            version_id=version_id,
            book=book,
            line_start=line_start,
            line_end=line_end,
            citation=citation,
            cts_urn=f"{version_urn}:{line_ref}",
            canonical_url=(
                f"/odyssey/read/{book}?"
                + urlencode(
                    {
                        "version": version_id,
                        "lines": f"{line_start}-{line_end}",
                    }
                )
            ),
        )
