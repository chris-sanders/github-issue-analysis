# GitHub Issue Analysis

Collect GitHub issues and analyze them with AI to improve issue labeling and categorization.

## Quick Start

1. **Setup Environment**
   ```bash
   uv sync --all-extras
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Collect Issues**
   ```bash
   uv run gh-analysis collect --org YOUR_ORG --repo YOUR_REPO --labels bug --limit 5
   ```

3. **Process with AI (Batch Processing - Recommended)**
   ```bash
   # Submit batch job (50% cheaper than individual processing)
   uv run gh-analysis batch submit product-labeling --org YOUR_ORG --repo YOUR_REPO
   
   # Check status
   uv run gh-analysis batch list
   
   # Collect results when completed
   uv run gh-analysis batch collect <job-id>
   ```

   **Individual Processing** (for single issues or custom models):
   ```bash
   # Use default model
   uv run gh-analysis process product-labeling --org YOUR_ORG --repo YOUR_REPO --issue-number 123
   
   # Use custom model with settings
   uv run gh-analysis process product-labeling --org YOUR_ORG --repo YOUR_REPO \
     --model anthropic:claude-3-5-sonnet \
     --setting temperature=0.5 \
     --setting reasoning_effort=high
   
   # Show available model settings
   uv run gh-analysis process show-settings
   ```

4. **Update Labels** (with GitHub write token)
   ```bash
   # Preview changes first
   uv run gh-analysis update-labels --org YOUR_ORG --repo YOUR_REPO --dry-run
   
   # Apply changes
   uv run gh-analysis update-labels --org YOUR_ORG --repo YOUR_REPO
   ```

## Enhanced Analysis with Memory+Tool Agents

This tool provides enhanced troubleshooting agents (with `_mt` suffix) that use **historical case retrieval** and **evidence search** for improved analysis accuracy:

- `claude_sonnet_mt`: Claude Sonnet 4 with memory injection and evidence search tools
- `gpt5_mini_medium_mt`: GPT-5 Mini (medium reasoning) with memory and evidence search  
- `gpt5_mini_high_mt`: GPT-5 Mini (high reasoning) with memory and evidence search
- `gpt5_medium_mt`: GPT-5 (medium reasoning) with memory and evidence search
- `gpt5_high_mt`: GPT-5 (high reasoning) with memory and evidence search
- `gemini_25_pro_mt`: Gemini 2.5 Pro with memory injection and evidence search tools

### Snowflake Requirements

Memory+Tool agents require Snowflake access for historical case data:

```bash
export SNOWFLAKE_ACCOUNT="your_account"
export SNOWFLAKE_USER="your_user"
export SNOWFLAKE_PRIVATE_KEY_PATH="~/.snowflake/rsa_key.pem"
export SNOWFLAKE_PRIVATE_KEY_PASSPHRASE="your_passphrase"  # Optional: passphrase for private key
export SNOWFLAKE_WAREHOUSE="COMPUTE_WH"
```

**Test Connection:**
```bash
uv run python -c "from github_issue_analysis.runners.utils.summary_retrieval import SummaryRetrievalClient; client = SummaryRetrievalClient(); print('✅ Snowflake connection successful')"
```

**Note:** Basic agents (`gpt5_mini_medium`, `gpt5_mini_high`, `gpt5_medium`, `gpt5_high`) work without Snowflake and provide standard troubleshooting analysis.

## For AI Agents

**All agent instructions are in `CLAUDE.md`** - this is the single source of truth for development workflow, commands, and requirements.

## Documentation

See `docs/` directory for user documentation:
- `architecture.md` - System design overview
- `data-schemas.md` - JSON formats and data structures  
- `api-reference.md` - CLI commands and usage
