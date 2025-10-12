#!/bin/bash
cd /Users/chris/src/github-issue-analysis/trees/temporal-framework-migration
uv run gh-analysis process troubleshoot \
  --url https://github.com/replicated-collab/knime-replicated/issues/358 \
  --agent claude_sonnet_4_5
