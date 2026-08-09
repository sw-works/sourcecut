# Task 008 — ADK Historical Evidence Tool

## Goal

Allow Gemini/ADK to research through typed Python evidence tools.

## Required tool

`search_historical_evidence(start_date, end_date, terms)`

## Desired behavior

For a historical production question, the agent chooses the evidence tool instead of answering from model memory.

## Acceptance tests

1. Ask for production-relevant visual details during the September 1805 Bitterroot crossing; return cited evidence grouped across authors.
2. Ask whether wagons should be depicted; if no retrieved support exists, say the corpus does not support the claim.
3. Ask for the source behind a snow claim; resolve to deterministic passage lookup without another Gemini call.

## Milestone gate

Do not start serious media ingestion until this task passes reliably.
