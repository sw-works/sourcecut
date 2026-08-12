# Odyssey production operations

## Trust boundary

Runtime research uses the authenticated official `mcp-clickhouse` HTTP server and a dedicated
`sourcecut_mcp` user assigned only to `sourcecut_mcp_role`. Apply
`sql/security/odyssey_mcp_role.sql` with an administrative account, create the user separately with a
secret-manager password, and grant the role. Never pass administrative ClickHouse credentials to the
MCP deployment. `CLICKHOUSE_ALLOW_WRITE_ACCESS=false` is mandatory.

The role has read-only settings, bounded execution/results, explicit view/table grants, and row
policies that hide untrusted observations and entity mentions. Application query validation is a
second boundary; it is not a replacement for role policy.

## Deployment preflight

1. Bootstrap all numbered migrations with an administrative ingestion identity.
2. Apply `sql/security/odyssey_mcp_role.sql` and configure the dedicated user.
3. Start official `mcp-clickhouse` with authenticated HTTP using
   `deploy/odyssey-mcp.env.example` as the variable checklist.
4. Run `sourcecut-mcp-preflight`. It must prove authentication, approved tools/views, and server-side
   read-only enforcement.
5. Run `SOURCECUT_RUN_LIVE_MCP_TESTS=true` and `SOURCECUT_RUN_LIVE_POLICY_TESTS=true` integration
   tests before promotion.

## Degraded operation

`GET /readyz` reports live-research configuration and verifies every cached TEI/treebank file against
the pinned manifest. If MCP/ClickHouse is unavailable, disable new live research and keep reader,
voyage graph, metadata-only assets, parallel text, and known-good board replay available. Do not call
Perseus or museum APIs from a live session.

The offline load path is:

```shell
sourcecut-load-odyssey --source-dir data/offline/odyssey
```

## Recovery

- TEI/hash drift: quarantine the incoming import and retain the active release.
- Invalid generated evidence: reject the claim and retain the rest of the board with a warning.
- Map render failure: retain sequence graph, null geometries, citations, and accessible table.
- Export failure: retain the frozen revision and retry only the idempotent export job.
- Bad annotation release: use the audited release rollback endpoint; never rewrite raw sources or old
  board revisions.

## Privacy and telemetry

Log correlation IDs, corpus/release IDs, stages, tool names, statuses, counts, and duration. Do not log
source passages, user questions, board notes, admin credentials, authorization headers, signed URLs,
or raw provider payloads. Alert on rejected-query rate, MCP timeout rate, failed research sessions,
invalid evidence, public-rights omissions, and export failures.
