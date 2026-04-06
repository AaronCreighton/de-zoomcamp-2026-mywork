FROM python:3.13.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

# Copy dependency files
COPY "pyproject.toml" ".python-version" "uv.lock" ./

# Install dependencies
RUN uv sync --locked --no-dev --no-cache

# or if you want to use docker layer cache 
# RUN --mount=type=cache,target=/root/.cache/uv \
#  uv sync --no-dev

# Copy project files
COPY pipeline.py  pipeline.py

# Set entry point
ENTRYPOINT ["python", "pipeline.py"]