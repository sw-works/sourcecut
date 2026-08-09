# Task 010 — Library of Congress Media Ingest

## Goal

Create the first archive media pipeline after the evidence milestone is proven.

## Scope

- harvest relevant LOC records;
- cache raw JSON;
- normalize metadata;
- preserve item-level rights;
- cache approved thumbnails;
- insert media records into ClickHouse.

## Rules

- never assume every LOC record is public domain;
- preserve `raw_metadata`;
- no live archive dependency during research demo.

## Acceptance criteria

The Bitterroot demo corpus includes a useful set of historical maps/images/documents that can be searched locally.
