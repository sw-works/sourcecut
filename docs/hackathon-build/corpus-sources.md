# Corpus source decisions

The corpus may redistribute only editions whose text and editorial matter are public domain in
the United States. The University of Nebraska journal site remains validation-only.

## Patrick Gass — go, implemented

- Source: [Internet Archive item `gasssjournalofle00gass`](https://archive.org/details/gasssjournalofle00gass).
- Edition: *Gass's Journal of the Lewis and Clark Expedition*, edited by James Kendall Hosmer,
  A. C. McClurg & Co., 1904; the title page says it reprints the 1811 edition.
- Rights: published in the United States in 1904; the archive item reports
  `possible copyright status: NOT_IN_COPYRIGHT`.
- Use: ingest the archive's OCR text with its own parser and retain the scan URL as provenance.
  OCR errors are preserved rather than silently modernized.

## John Ordway — go, not implemented in Task 025

- Source: [Internet Archive item `journalsofcaptai00lewirich`](https://archive.org/details/journalsofcaptai00lewirich),
  also cataloged by [Open Library](https://openlibrary.org/books/OL6590313M/The_journals_of_Captain_Meriwether_Lewis_and_Sergeant_John_Ordway).
- Edition: *The Journals of Captain Meriwether Lewis and Sergeant John Ordway*, edited by Milo M.
  Quaife, State Historical Society of Wisconsin Collections volume XXII, 1916.
- Rights: U.S. publication in 1916; the scan is identified as public domain in the United States.
- Decision: eligible, but deferred. Its distinct typography/OCR requires a separately tested parser;
  it is not needed to satisfy the one-additional-author milestone.

## Joseph Whitehouse — go for the 1905 edition, not implemented in Task 025

- Source: [American Journeys document AJ-100g](https://www.americanjourneys.org/aj-100g/),
  volume 7 of the Thwaites edition.
- Edition: *Original Journals of the Lewis and Clark Expedition, 1804–1806*, volume 7, edited by
  Reuben Gold Thwaites, Dodd, Mead & Company, 1905.
- Rights: U.S. publication in 1905. This decision applies only to that edition, not to the modern
  Moulton/University of Nebraska edition.
- Decision: eligible, but deferred until a parser can isolate Whitehouse from Floyd, appendices,
  notes, and index material without mixing authors.
