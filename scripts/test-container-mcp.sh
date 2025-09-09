#!/bin/bash
set -e

# Local testing script for MCP container functionality
# This script builds and tests the container without requiring real bundle URLs

echo "🧪 Testing Containerized MCP Server Functionality"
echo "================================================"

# Check if podman is available
if ! command -v podman &> /dev/null; then
    echo "❌ Podman not found. Please install podman."
    exit 1
fi

CONTAINER_CMD="podman"

echo "Using container runtime: $CONTAINER_CMD"

# Build the container
echo ""
echo "🔨 Building container..."
$CONTAINER_CMD build -t gh-analysis:test .

# Set up test environment variables
export GITHUB_TOKEN="ghp_mock_token_for_testing_1234567890"
export OPENAI_API_KEY="sk-mock-key-for-testing" 
export SBCTL_TOKEN="mock-sbctl-token-12345"

echo ""
echo "🧪 Running MCP Integration Tests..."
echo "-----------------------------------"

# Run the comprehensive MCP integration tests
$CONTAINER_CMD run --rm \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e SBCTL_TOKEN="$SBCTL_TOKEN" \
  --entrypoint=/bin/sh \
  gh-analysis:test \
  -c "cd /app && uv run python tests/mcp_integration_check.py"

echo ""
echo "🔍 Testing CLI Help Commands..."
echo "-------------------------------"

# Test CLI functionality
$CONTAINER_CMD run --rm \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e SBCTL_TOKEN="$SBCTL_TOKEN" \
  --entrypoint=/bin/sh \
  gh-analysis:test \
  -c "gh-analysis process troubleshoot --help"

echo ""
echo "🔒 Testing Container Entrypoint Validation..."
echo "--------------------------------------------"

# Test entrypoint validation (should fail without ISSUE_URL)
set +e
OUTPUT=$($CONTAINER_CMD run --rm gh-analysis:test 2>&1)
EXIT_CODE=$?
set -e

if echo "$OUTPUT" | grep -q "ISSUE_URL environment variable is required"; then
    echo "✓ Entrypoint validation working correctly"
else
    echo "❌ Entrypoint validation failed"
    echo "Output: $OUTPUT"
    exit 1
fi

echo ""
echo "🔍 Testing System Dependencies..."
echo "--------------------------------"

# Test individual system dependencies
DEPS=("sbctl version" "kubectl version --client" "busybox --help")
for dep in "${DEPS[@]}"; do
    echo "Testing: $dep"
    $CONTAINER_CMD run --rm --entrypoint=/bin/sh gh-analysis:test -c "$dep" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✓ $dep working"
    else
        echo "❌ $dep failed"
        exit 1
    fi
done

echo ""
echo "🎉 All container tests passed!"
echo ""
echo "📝 To test with a real issue (requires real tokens):"
echo "   export ISSUE_URL=\"https://github.com/your-org/your-repo/issues/123\""
echo "   export GITHUB_TOKEN=\"your-real-token\""
echo "   export OPENAI_API_KEY=\"your-real-key\""
echo "   export SBCTL_TOKEN=\"your-real-sbctl-token\""
echo "   $CONTAINER_CMD run --rm \\"
echo "     -e GITHUB_TOKEN=\$GITHUB_TOKEN \\"
echo "     -e OPENAI_API_KEY=\$OPENAI_API_KEY \\"  
echo "     -e SBCTL_TOKEN=\$SBCTL_TOKEN \\"
echo "     -v \$(pwd)/data:/app/data \\"
echo "     -e ISSUE_URL=\"\$ISSUE_URL\" \\"
echo "     -e CLI_ARGS=\"--agent gpt5_mini_medium\" \\"
echo "     gh-analysis:test"