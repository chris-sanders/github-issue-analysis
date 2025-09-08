# Stage 1: Dependencies
FROM python:3.13-slim as builder
WORKDIR /app

# Install build dependencies for snowflake-connector-python
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files and source code
COPY pyproject.toml uv.lock ./
COPY github_issue_analysis ./github_issue_analysis

# Create symlink for package structure (gh_analysis -> github_issue_analysis)
RUN ln -s github_issue_analysis gh_analysis

# Install dependencies
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.13-slim
WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy uv and dependencies from builder
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Create scripts directory and make entrypoint executable
RUN mkdir -p /app/scripts && chmod +x /app/scripts/container-entrypoint.sh

# Switch to non-root user
USER appuser

# Set entrypoint
ENTRYPOINT ["/app/scripts/container-entrypoint.sh"]