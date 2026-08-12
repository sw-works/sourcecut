FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY apps ./apps
COPY pipelines ./pipelines
COPY data/reference ./data/reference
ENV PATH="/app/.venv/bin:$PATH" PORT=8080
EXPOSE 8080
CMD ["python", "-m", "sourcecut_api.main"]
