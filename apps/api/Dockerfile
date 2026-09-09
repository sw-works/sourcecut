FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
# Dependencies first, without the project itself: this layer is cached across
# source changes. Installing the project here would fail anyway, since hatchling
# reads the readme and the package directories, and neither is copied yet.
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev --no-install-project
# LICENSE travels with README.md: pyproject names both, so hatchling needs the
# file present before the project itself installs.
COPY README.md LICENSE ./
COPY apps ./apps
COPY pipelines ./pipelines
COPY data/reference ./data/reference
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" PORT=8080
EXPOSE 8080
CMD ["python", "-m", "sourcecut_api.main"]
