# Stage 1: Dependencies
FROM python:3.13-slim as builder
WORKDIR /app

# Install build dependencies for snowflake-connector-python
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    curl \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install sbctl (support bundle control tool) - required for MCP server
RUN curl -L https://github.com/replicatedhq/sbctl/releases/download/v0.17.3/sbctl_linux_arm64.tar.gz -o /tmp/sbctl.tar.gz && \
    tar -xzf /tmp/sbctl.tar.gz -C /tmp && \
    mv /tmp/sbctl /usr/local/bin/sbctl && \
    chmod +x /usr/local/bin/sbctl && \
    rm -f /tmp/sbctl.tar.gz

# Install kubectl - required for MCP server Kubernetes operations
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/arm64/kubectl" && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && \
    rm kubectl

# Copy dependency files and source code
COPY pyproject.toml uv.lock ./
COPY gh_analysis ./gh_analysis

# Install dependencies
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.13-slim
WORKDIR /app

# Create non-root user, SSH directory for Snowflake keys, and data directory
RUN useradd -m -u 1000 appuser && \
    mkdir -p /home/appuser/.ssh && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /home/appuser/.ssh /app/data

# Install additional system dependencies for MCP server
RUN apt-get update && apt-get install -y \
    ca-certificates \
    busybox \
    && rm -rf /var/lib/apt/lists/*

# Copy uv, sbctl, kubectl, and dependencies from builder  
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /usr/local/bin/sbctl /usr/local/bin/sbctl
COPY --from=builder /usr/local/bin/kubectl /usr/local/bin/kubectl
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Fix ownership of .venv and application directory for appuser
RUN chown -R appuser:appuser /app/.venv /app

# Create scripts directory and make entrypoint executable
RUN mkdir -p /app/scripts && chmod +x /app/scripts/container-entrypoint.sh

# Switch to non-root user
USER appuser

# Set entrypoint
ENTRYPOINT ["/app/scripts/container-entrypoint.sh"]