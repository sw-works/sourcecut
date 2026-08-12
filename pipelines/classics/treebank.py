from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher

from sourcecut_api.models.classical_text import TextUnit
from sourcecut_api.models.linguistic import (
    FormulaOccurrence,
    LinguisticAnnotationRelease,
    TextToken,
)

TREEBANK_VERSION = "perseus-aldt-v2.1"
TOKENIZER_VERSION = "sourcecut-unicode-v1"
TOKEN_CITE = re.compile(r":(?P<book>\d+)\.(?P<line>\d+)$")
POS = {
    "n": "noun", "v": "verb", "a": "adjective", "d": "adverb",
    "l": "article", "g": "particle", "c": "conjunction", "r": "preposition",
    "p": "pronoun", "m": "numeral", "i": "interjection", "e": "exclamation",
    "u": "punctuation",
}
PERSON = {"1": "first", "2": "second", "3": "third"}
NUMBER = {"s": "singular", "p": "plural", "d": "dual"}
TENSE = {
    "p": "present", "i": "imperfect", "r": "perfect", "l": "pluperfect",
    "t": "future-perfect", "f": "future", "a": "aorist",
}
MOOD = {
    "i": "indicative", "s": "subjunctive", "o": "optative", "n": "infinitive",
    "m": "imperative", "p": "participle",
}
VOICE = {"a": "active", "m": "middle", "p": "passive", "e": "medio-passive"}
GENDER = {"m": "masculine", "f": "feminine", "n": "neuter"}
CASE = {"n": "nominative", "g": "genitive", "d": "dative", "a": "accusative", "v": "vocative"}
DEGREE = {"c": "comparative", "s": "superlative"}


class TreebankAlignmentError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParsedLinguistics:
    release: LinguisticAnnotationRelease
    tokens: tuple[TextToken, ...]
    formulae: tuple[FormulaOccurrence, ...]
    annotated_tokens: int
    unannotated_tokens: int


@dataclass(frozen=True, slots=True)
class _TreeToken:
    book: int
    form: str
    lemma: str
    postag: str
    relation: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class _SourceToken:
    unit: TextUnit
    index: int
    start: int
    end: int
    surface: str


def parse_odyssey_treebank(
    raw_content: str,
    *,
    text_units: tuple[TextUnit, ...],
    upstream_revision: str,
    upstream_path: str,
    repository_url: str,
    expected_sha256: str,
) -> ParsedLinguistics:
    actual_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
    if actual_hash != expected_sha256:
        raise TreebankAlignmentError("Pinned Odyssey treebank hash does not match manifest")
    try:
        root = ET.fromstring(raw_content)
    except ET.ParseError as error:
        raise TreebankAlignmentError(f"Malformed Odyssey treebank: {error}") from error
    source_urn = root.attrib.get("cts", "")
    if not source_urn.startswith("urn:cts:greekLit:tlg0012.tlg002"):
        raise TreebankAlignmentError("Treebank is not an Odyssey annotation document")

    release_id = f"odyssey-treebank:{upstream_revision[:12]}:{actual_hash[:12]}"
    release = LinguisticAnnotationRelease(
        annotation_release_id=release_id,
        source_version_id="odyssey-perseus-grc2",
        annotation_source="Perseus Ancient Greek Dependency Treebank",
        annotation_version=TREEBANK_VERSION,
        source_document_urn=source_urn,
        repository_url=repository_url,
        upstream_path=upstream_path,
        upstream_revision=upstream_revision,
        source_sha256=actual_hash,
        license_id="cc-by-sa-3.0-us",
        raw_content=raw_content,
    )
    tree_by_book = _tree_tokens(root)
    source_by_book = _source_tokens(text_units)
    tokens: list[TextToken] = []
    annotated = 0
    for book in range(1, 25):
        tree = tree_by_book[book]
        source = source_by_book[book]
        matcher = SequenceMatcher(
            None,
            [_search_key(item.form) for item in tree],
            [_search_key(item.surface) for item in source],
            autojunk=False,
        )
        aligned: dict[int, _TreeToken] = {}
        for tree_start, source_start, size in matcher.get_matching_blocks():
            for offset in range(size):
                aligned[source_start + offset] = tree[tree_start + offset]
        for source_index, source_token in enumerate(source):
            tree_token = aligned.get(source_index)
            if tree_token is not None:
                annotated += 1
            tokens.append(_token_record(source_token, tree_token, release_id))
    formulae = build_formula_occurrences(tuple(tokens))
    return ParsedLinguistics(
        release=release,
        tokens=tuple(tokens),
        formulae=formulae,
        annotated_tokens=annotated,
        unannotated_tokens=len(tokens) - annotated,
    )


def build_formula_occurrences(tokens: tuple[TextToken, ...]) -> tuple[FormulaOccurrence, ...]:
    by_line: dict[tuple[int, int], list[TextToken]] = defaultdict(list)
    for token in tokens:
        by_line[(token.book, token.line)].append(token)
    candidates: dict[tuple[int, str], list[tuple[list[TextToken], str]]] = defaultdict(list)
    for line_tokens in by_line.values():
        ordered = sorted(line_tokens, key=lambda token: token.token_index)
        for size in range(2, 6):
            for start in range(0, len(ordered) - size + 1):
                window = ordered[start : start + size]
                normalized = " ".join(token.accentless_surface for token in window)
                display = " ".join(token.surface for token in window)
                candidates[(size, normalized)].append((window, display))
    rows: list[FormulaOccurrence] = []
    for (size, normalized), occurrences in candidates.items():
        if len(occurrences) < 2:
            continue
        formula_hash = hashlib.sha256(f"{size}:{normalized}".encode()).hexdigest()
        formula_id = f"formula:{formula_hash[:24]}"
        for window, display in occurrences:
            first = window[0]
            occurrence_hash = hashlib.sha256(
                f"{formula_id}:{first.text_unit_id}:{first.token_index}".encode()
            ).hexdigest()
            rows.append(
                FormulaOccurrence(
                    occurrence_id=f"formula-occurrence:{occurrence_hash[:24]}",
                    formula_id=formula_id,
                    version_id=first.version_id,
                    book=first.book,
                    line_start=first.line,
                    line_end=window[-1].line,
                    ngram_size=size,
                    normalized_formula=normalized,
                    display_formula=display,
                    token_ids=tuple(token.token_id for token in window),
                    occurrence_sha256=occurrence_hash,
                )
            )
    return tuple(sorted(rows, key=lambda row: (row.formula_id, row.book, row.line_start)))


def _tree_tokens(root: ET.Element) -> dict[int, list[_TreeToken]]:
    result: dict[int, list[_TreeToken]] = defaultdict(list)
    for sentence in root.iter("sentence"):
        sentence_id = sentence.attrib.get("id", "unknown")
        fallback_book = int(sentence.attrib.get("subdoc", "0.0").split(".", 1)[0])
        for word in sentence.findall("word"):
            if word.attrib.get("postag", "").startswith("u"):
                continue
            match = TOKEN_CITE.search(word.attrib.get("cite", ""))
            book = int(match.group("book")) if match else fallback_book
            result[book].append(
                _TreeToken(
                    book=book,
                    form=word.attrib.get("form", ""),
                    lemma=word.attrib.get("lemma", ""),
                    postag=word.attrib.get("postag", ""),
                    relation=word.attrib.get("relation", ""),
                    source_ref=f"sentence:{sentence_id}:word:{word.attrib.get('id', '')}",
                )
            )
    return result


def _source_tokens(text_units: tuple[TextUnit, ...]) -> dict[int, list[_SourceToken]]:
    result: dict[int, list[_SourceToken]] = defaultdict(list)
    for unit in sorted(text_units, key=lambda item: (item.book, item.line_start)):
        for index, (start, end) in enumerate(_lexical_spans(unit.original_text)):
            result[unit.book].append(
                _SourceToken(unit, index, start, end, unit.original_text[start:end])
            )
    return result


def _lexical_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for index, character in enumerate(text + " "):
        category = unicodedata.category(character)
        is_token = category.startswith(("L", "M")) or (
            start is not None and character in "ʼ’'᾽"
        )
        if is_token and start is None:
            start = index
        elif not is_token and start is not None:
            spans.append((start, index))
            start = None
    return spans


def _search_key(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFD", value).casefold()
        if not unicodedata.combining(character) and character not in "ʼ’'᾽"
    )


def _token_record(source: _SourceToken, tree: _TreeToken | None, release_id: str) -> TextToken:
    lemma = tree.lemma if tree else ""
    postag = tree.postag if tree else ""
    morphology = _morphology(postag, tree.relation) if tree else {}
    identity = f"{source.unit.text_unit_id}:{source.start}:{source.end}"
    token_hash = hashlib.sha256(
        json.dumps(
            {
                "identity": identity,
                "surface": source.surface,
                "lemma": lemma,
                "morphology": morphology,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    return TextToken(
        token_id=f"token:{hashlib.sha256(identity.encode()).hexdigest()[:28]}",
        text_unit_id=source.unit.text_unit_id,
        version_id=source.unit.version_id,
        book=source.unit.book,
        line=source.unit.line_start,
        token_index=source.index,
        surface=source.surface,
        normalized_surface=unicodedata.normalize("NFC", source.surface).casefold(),
        accentless_surface=_search_key(source.surface),
        lemma=lemma,
        lemma_search=_search_key(lemma),
        part_of_speech=POS.get(postag[:1], "unknown"),
        morphology=morphology,
        char_start=source.start,
        char_end=source.end,
        annotation_source=(
            "Perseus Ancient Greek Dependency Treebank"
            if tree
            else "SourceCut Unicode tokenizer"
        ),
        annotation_confidence=0.95 if tree else 0.0,
        review_status="imported_unreviewed" if tree else "tokenized_unannotated",
        annotation_version=TREEBANK_VERSION if tree else TOKENIZER_VERSION,
        annotation_release_id=release_id if tree else "",
        source_token_ref=tree.source_ref if tree else "",
        token_sha256=token_hash,
    )


def _morphology(postag: str, relation: str) -> dict[str, str]:
    padded = postag.ljust(9, "-")
    fields = (
        ("person", PERSON, padded[1]), ("number", NUMBER, padded[2]),
        ("tense", TENSE, padded[3]), ("mood", MOOD, padded[4]),
        ("voice", VOICE, padded[5]), ("gender", GENDER, padded[6]),
        ("case", CASE, padded[7]), ("degree", DEGREE, padded[8]),
    )
    result = {"postag": postag, "dependency_relation": relation}
    result.update({name: mapping[code] for name, mapping, code in fields if code in mapping})
    return result
