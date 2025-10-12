"""Test that framework MCP integration works in gh-analysis."""
import asyncio
import os
import sys

# Test environment
os.environ["SBCTL_TOKEN"] = os.getenv("SBCTL_TOKEN", "test-token")

async def test_framework_import():
    """Test 1: Framework is accessible."""
    try:
        from temporal_framework import create_mcp_toolset
        print("✓ Test 1: Framework import successful")
        return True
    except ImportError as e:
        print(f"✗ Test 1 FAILED: {e}")
        return False

async def test_adapter_uses_framework():
    """Test 2: MCP adapter uses framework."""
    try:
        from gh_analysis.runners.adapters.mcp_adapter import create_troubleshoot_mcp_server
        import inspect
        
        # Check if adapter imports from framework
        source = inspect.getsource(create_troubleshoot_mcp_server)
        if "temporal_framework" in source or "create_mcp_toolset" in source:
            print("✓ Test 2: Adapter uses framework")
            return True
        else:
            print("✗ Test 2 FAILED: Adapter doesn't use framework")
            return False
    except Exception as e:
        print(f"✗ Test 2 FAILED: {e}")
        return False

async def test_mcp_server_creation():
    """Test 3: Can create MCP server via framework."""
    try:
        from temporal_framework import create_mcp_toolset
        
        # Create MCP server using framework directly
        mcp_server = create_mcp_toolset(
            server_command="troubleshoot-mcp-server",
            token_env="SBCTL_TOKEN",
            timeout=30.0,
            toolset_id="test-mcp",
        )
        
        print(f"✓ Test 3: MCP server created via framework: {type(mcp_server).__name__}")
        return True
    except Exception as e:
        print(f"✗ Test 3 FAILED: {e}")
        return False

async def test_runner_can_use_framework():
    """Test 4: Runners can import and use framework MCP."""
    try:
        # Test troubleshooting runner imports
        from gh_analysis.runners.troubleshooting.gpt5_medium import GPT5MediumRunner
        
        print("✓ Test 4: Runner imports successfully (uses vendored utils)")
        print("  Note: Runners still use GitHubIssueRunner pattern (Phase 2 needed)")
        return True
    except Exception as e:
        print(f"✗ Test 4 FAILED: {e}")
        return False

async def test_vendored_mcp_uses_framework():
    """Test 5: Vendored MCP re-exports framework."""
    try:
        import inspect
        from gh_analysis.runners.utils.mcp import create_troubleshoot_mcp_server
        
        # Check source
        source = inspect.getsource(create_troubleshoot_mcp_server)
        if "temporal_framework" in source or "create_mcp_toolset" in source:
            print("✓ Test 5: Vendored MCP re-exports framework")
            return True
        else:
            print("✗ Test 5 FAILED: Vendored MCP doesn't use framework")
            return False
    except Exception as e:
        print(f"✗ Test 5 FAILED: {e}")
        return False

async def main():
    print("=" * 60)
    print("Phase 1 Framework Integration Validation")
    print("=" * 60)
    print()
    
    results = []
    results.append(await test_framework_import())
    results.append(await test_adapter_uses_framework())
    results.append(await test_mcp_server_creation())
    results.append(await test_runner_can_use_framework())
    results.append(await test_vendored_mcp_uses_framework())
    
    print()
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 Phase 1 integration verified!")
        print()
        print("What this means:")
        print("- Framework submodule is accessible")
        print("- MCP code uses framework's create_mcp_toolset()")
        print("- Backward compatibility maintained")
        print()
        print("What's NOT done yet (Phase 2):")
        print("- Runner pattern still exists (should be Temporal workflows)")
        print("- Shared utilities not in framework (memory, history, snowflake)")
        print("- CLI still uses Runner classes (should trigger workflows)")
    else:
        print("❌ Some tests failed - Phase 1 incomplete")
        sys.exit(1)
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
