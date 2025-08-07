# GitHub Issue Analysis Documentation

User documentation for the GitHub issue collection and AI analysis tool.

## Documentation Structure

- [Architecture](architecture.md) - System design and component overview
- [API Reference](api-reference.md) - CLI commands and usage
- [Data Schemas](data-schemas.md) - JSON schemas for issues and results
- [Label Updates Guide](label-updates-guide.md) - Comprehensive guide for automated label updates

## Quick Start

1. Set up environment: `uv sync --all-extras`
2. Configure `.env` file with API keys
3. Collect issues: `uv run gh-analysis collect --org myorg --repo myrepo`
4. Process issues: `uv run gh-analysis process product-labeling --org myorg --repo myrepo`
5. Update labels: `uv run gh-analysis update-labels --org myorg --repo myrepo --dry-run`

## For AI Agents

**See `CLAUDE.md` in the project root** - this contains all agent development instructions, workflow, and requirements.