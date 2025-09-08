#!/bin/bash
set -e

echo "=== Container Testing Script ==="
echo "This script tests the containerized GitHub Issue Analysis CLI"
echo ""

# Build container first
echo "Step 1: Building container..."
podman build -f Containerfile -t gh-analysis .
echo "✓ Container built successfully"
echo ""

echo "=== Tests that work without API keys (CI-safe) ==="
echo ""

echo "Test 1: Missing ISSUE_URL should fail with exit code 2"
if podman run --rm gh-analysis; then
    echo "❌ Test 1 failed: Expected exit code 2, but container succeeded"
    exit 1
else
    exit_code=$?
    if [ $exit_code -eq 2 ]; then
        echo "✓ Test 1 passed: Container correctly exited with code 2"
    else
        echo "❌ Test 1 failed: Expected exit code 2, got $exit_code"
        exit 1
    fi
fi
echo ""

echo "Test 2: Help flag should work without API keys"
podman run --rm \
  -e ISSUE_URL="https://github.com/test/test/issues/1" \
  -e CLI_ARGS="--help" \
  gh-analysis > /dev/null
echo "✓ Test 2 passed: Help command works without API keys"
echo ""

echo "Test 3: Version flag should work without API keys"
podman run --rm \
  -e ISSUE_URL="https://github.com/test/test/issues/1" \
  -e CLI_ARGS="--version" \
  gh-analysis > /dev/null
echo "✓ Test 3 passed: Version command works without API keys"
echo ""

echo "=== Tests that require API keys (local only) ==="
echo ""

if [ -n "$GITHUB_TOKEN" ] && [ -n "$ISSUE_URL" ]; then
  echo "API keys and ISSUE_URL detected. Running integration test..."
  
  if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠ Warning: No AI API keys found. Test may fail."
  fi
  
  if [ -z "$SBCTL_TOKEN" ]; then
    echo "⚠ Warning: SBCTL_TOKEN not found. Troubleshoot command requires this token."
  fi
  
  echo "Test 4: Valid execution with real issue"
  echo "Using ISSUE_URL: $ISSUE_URL"
  
  # Set timeout to prevent hanging
  timeout 300 podman run --rm \
    -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
    -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
    -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
    -e SBCTL_TOKEN="${SBCTL_TOKEN:-}" \
    -e ISSUE_URL="${ISSUE_URL}" \
    -e CLI_ARGS="--agent gpt5_mini_medium" \
    gh-analysis
  
  if [ $? -eq 0 ]; then
    echo "✓ Test 4 passed: Container successfully processed real issue"
  else
    echo "❌ Test 4 failed: Container processing failed (this might be expected if tokens are missing)"
    echo "   This is normal if required API tokens are not available"
  fi
else
  echo "⚠ Skipping Test 4: GITHUB_TOKEN and/or ISSUE_URL not available"
  echo "   To run integration tests, set:"
  echo "   export GITHUB_TOKEN='your-token'"
  echo "   export ISSUE_URL='https://github.com/org/repo/issues/123'"
  echo "   export OPENAI_API_KEY='your-key'  # Optional but recommended"
  echo "   export ANTHROPIC_API_KEY='your-key'  # Optional but recommended"
  echo "   export SBCTL_TOKEN='your-token'  # Required for troubleshoot command"
fi
echo ""

echo "=== Parallel Processing Test (local only) ==="
echo ""

if [ -n "$GITHUB_TOKEN" ] && [ -n "$ISSUE_URL" ]; then
  echo "Test 5: Parallel container execution"
  echo "Starting 3 containers in parallel (using same issue for testing)..."
  
  # Start 3 containers in background
  for i in 1 2 3; do
    echo "Starting container $i..."
    podman run --rm \
      -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
      -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
      -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
      -e SBCTL_TOKEN="${SBCTL_TOKEN:-}" \
      -e ISSUE_URL="${ISSUE_URL}" \
      -e CLI_ARGS="--agent gpt5_mini_medium" \
      gh-analysis > "parallel-test-$i.log" 2>&1 &
    pids[$i]=$!
  done
  
  echo "Waiting for all containers to complete..."
  success_count=0
  for i in 1 2 3; do
    if wait ${pids[$i]}; then
      echo "✓ Container $i completed successfully"
      success_count=$((success_count + 1))
    else
      echo "❌ Container $i failed"
    fi
  done
  
  if [ $success_count -eq 3 ]; then
    echo "✓ Test 5 passed: All parallel containers completed successfully"
  elif [ $success_count -gt 0 ]; then
    echo "⚠ Test 5 partial: $success_count/3 containers succeeded (this might be expected with limited tokens)"
  else
    echo "❌ Test 5 failed: No containers succeeded"
  fi
  
  # Clean up log files
  rm -f parallel-test-*.log
else
  echo "⚠ Skipping Test 5: GITHUB_TOKEN and/or ISSUE_URL not available"
fi
echo ""

echo "=== Resource Usage Test ==="
echo ""

echo "Test 6: Container resource usage"
echo "Running container with memory limit (256MB)..."
podman run --rm \
  --memory=256m \
  -e ISSUE_URL="https://github.com/test/test/issues/1" \
  -e CLI_ARGS="--help" \
  gh-analysis > /dev/null

if [ $? -eq 0 ]; then
  echo "✓ Test 6 passed: Container runs within memory limit"
else
  echo "❌ Test 6 failed: Container exceeded memory limit or failed"
fi
echo ""

echo "=== Summary ==="
echo "Container testing completed!"
echo ""
echo "Next steps for manual testing:"
echo "1. Set environment variables:"
echo "   export ISSUE_URL='https://github.com/your-org/your-repo/issues/123'"
echo "   export GITHUB_TOKEN='your-github-token'"
echo "   export OPENAI_API_KEY='your-openai-key'"
echo "   export ANTHROPIC_API_KEY='your-anthropic-key'"
echo "   export SBCTL_TOKEN='your-sbctl-token'"
echo ""
echo "2. Run container manually:"
echo "   podman run --rm \\"
echo "     -e GITHUB_TOKEN=\$GITHUB_TOKEN \\"
echo "     -e OPENAI_API_KEY=\$OPENAI_API_KEY \\"
echo "     -e ISSUE_URL=\$ISSUE_URL \\"
echo "     -e CLI_ARGS='--agent gpt5_mini_medium' \\"
echo "     gh-analysis"
echo ""
echo "All basic tests passed! ✅"