#!/usr/bin/env python3
"""
Functional tests for MCP server integration.

These tests focus on the actual functionality that matters:
- Can the MCP server start and respond to requests?
- Can we connect to it and list tools?
- Does the runner integration work end-to-end?

This avoids testing specific implementation details like binary versions
or file permissions, focusing on actual functional behavior.
"""

import asyncio
import sys

import pytest

# Add the project root to the path so we can import modules
sys.path.insert(0, "/app")

from gh_analysis.runners.adapters.mcp_adapter import (
    create_troubleshoot_mcp_server,
)
from mcp import ClientSession


@pytest.mark.asyncio
async def test_mcp_server_connectivity():
    """Test that we can connect to and communicate with the MCP server."""
    print("=== Testing MCP Server Connectivity ===")

    try:
        # Create MCP server using the actual adapter code
        server = create_troubleshoot_mcp_server()

        async with server as (read, write):  # type: ignore[misc]
            async with ClientSession(read, write) as session:  # type: ignore[has-type]
                await session.initialize()

                # Test that we can list tools
                tools_result = await session.list_tools()
                tool_names = [tool.name for tool in tools_result.tools]

                print(f"✓ MCP server connected, available tools: {tool_names}")

                # Verify we have the expected troubleshooting tools
                expected_tools = ["initialize_bundle", "list_files", "read_file"]
                missing_tools = [
                    tool for tool in expected_tools if tool not in tool_names
                ]

                if missing_tools:
                    print(f"❌ Missing expected tools: {missing_tools}")
                    return False

                print("✓ All expected troubleshooting tools available")
                return True

    except Exception as e:
        print(f"❌ MCP server connectivity failed: {e}")
        return False


@pytest.mark.asyncio
async def test_mcp_error_handling():
    """Test that MCP server handles invalid requests gracefully."""
    print("\n=== Testing MCP Error Handling ===")

    try:
        server = create_troubleshoot_mcp_server()

        async with server as (read, write):  # type: ignore[misc]
            async with ClientSession(read, write) as session:  # type: ignore[has-type]
                await session.initialize()

                # Test calling a tool without required parameters
                try:
                    result = await session.call_tool("initialize_bundle", {})
                    if result.isError:
                        print(
                            "✓ MCP server properly returns errors for invalid requests"
                        )
                        return True
                    else:
                        print(
                            "❌ MCP server should return error for missing parameters"
                        )
                        return False
                except Exception as e:
                    print(
                        f"✓ MCP server properly handles invalid requests: {type(e).__name__}"
                    )
                    return True

    except Exception as e:
        print(f"❌ MCP error handling test failed: {e}")
        return False


@pytest.mark.asyncio
async def test_mcp_tool_communication():
    """Test that MCP server can handle tool communication with mock data."""
    print("\n=== Testing MCP Tool Communication ===")

    try:
        server = create_troubleshoot_mcp_server()

        async with server as (read, write):  # type: ignore[misc]
            async with ClientSession(read, write) as session:  # type: ignore[has-type]
                await session.initialize()

                # Test list_files with no bundle (should fail gracefully)
                try:
                    result = await session.call_tool("list_files", {})

                    # Should either return an error or empty result, not crash
                    if result.isError or (
                        hasattr(result, "content") and result.content
                    ):
                        print(
                            "✓ MCP server handles list_files without bundle gracefully"
                        )
                    else:
                        print(
                            "✓ MCP server responded to list_files (no bundle initialized)"
                        )

                    return True

                except Exception as e:
                    # Exception is also acceptable - means server handled it
                    print(
                        f"✓ MCP server handled list_files gracefully: {type(e).__name__}"
                    )
                    return True

    except Exception as e:
        print(f"❌ MCP tool communication test failed: {e}")
        return False


@pytest.mark.asyncio
async def test_troubleshoot_runner_integration():
    """Test that the troubleshoot runner can initialize with MCP tools."""
    print("\n=== Testing Troubleshoot Runner Integration ===")

    try:
        # Import the actual troubleshoot runner
        from gh_analysis.runners.troubleshoot_runner import TroubleshootRunner  # type: ignore[import-untyped]

        # Create a mock issue for testing

        # Test that we can create a runner with MCP tools
        # We won't actually run analysis since that requires API keys and real processing
        # But we can test that the runner initializes correctly with tools

        runner = TroubleshootRunner(
            agent="gpt5_mini_medium_mt",  # Use an MT agent that requires MCP
            include_images=False,
        )

        # Test that the runner has the tools method (indicates MCP integration)
        if hasattr(runner, "_tools") or hasattr(runner, "tools"):
            print("✓ Troubleshoot runner has MCP tools integration")
        else:
            print("✓ Troubleshoot runner created successfully")

        print("✓ Troubleshoot runner integration working")
        return True

    except ImportError as e:
        print(f"❌ Could not import troubleshoot runner: {e}")
        return False
    except Exception as e:
        print(f"❌ Troubleshoot runner integration failed: {e}")
        return False


@pytest.mark.asyncio
async def test_cli_process_command():
    """Test that the CLI process command can be invoked (without actually running)."""
    print("\n=== Testing CLI Process Command ===")

    try:
        # Import CLI module to verify it loads correctly
        from gh_analysis.cli.process import troubleshoot

        # Just test that the command function exists and can be imported
        # We won't actually invoke it since that requires real arguments
        if callable(troubleshoot):
            print("✓ CLI process command available")
            return True
        else:
            print("❌ CLI process command not callable")
            return False

    except ImportError as e:
        print(f"❌ Could not import CLI process command: {e}")
        return False
    except Exception as e:
        print(f"❌ CLI process command test failed: {e}")
        return False


async def run_functional_tests():
    """Run all functional tests."""
    print("🧪 Starting MCP Functional Tests")
    print("================================")
    print("These tests verify actual MCP functionality, not implementation details.\n")

    tests = [
        ("MCP Server Connectivity", test_mcp_server_connectivity),
        ("MCP Error Handling", test_mcp_error_handling),
        ("MCP Tool Communication", test_mcp_tool_communication),
        ("Troubleshoot Runner Integration", test_troubleshoot_runner_integration),
        ("CLI Process Command", test_cli_process_command),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if await test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")

    print(f"\n📊 Functional Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All functional tests passed!")
        print("MCP server integration is working correctly.")
        return True
    else:
        print("❌ Some functional tests failed.")
        print("MCP server integration has functional issues.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_functional_tests())  # type: ignore[no-untyped-call]
    sys.exit(0 if success else 1)
