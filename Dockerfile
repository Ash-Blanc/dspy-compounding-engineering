FROM python:3.10-slim

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files and README (required for metadata)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies (uv sync creates .venv by default)
# --no-dev: Exclude development dependencies (mkdocs, pytest, etc.)
RUN uv sync --frozen --no-dev

# Place the virtual environment in the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY . .

# Set entrypoint
ENTRYPOINT ["python", "cli.py"]
CMD ["--help"]
