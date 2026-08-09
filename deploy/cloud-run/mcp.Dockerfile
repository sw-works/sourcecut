FROM python:3.10-slim

RUN pip install --no-cache-dir mcp-clickhouse==0.4.1

ENV CLICKHOUSE_MCP_SERVER_TRANSPORT=http \
    CLICKHOUSE_MCP_BIND_HOST=0.0.0.0 \
    CLICKHOUSE_MCP_BIND_PORT=8080 \
    CLICKHOUSE_ALLOW_WRITE_ACCESS=false \
    CLICKHOUSE_ALLOW_DROP=false

EXPOSE 8080
CMD ["mcp-clickhouse"]
