#!/usr/bin/env python3
"""
Comprehensive MCP server integration test for containerized environments.

This test verifies actual MCP server functionality without using real bundle URLs.
Designed to catch issues like:
- Missing system binaries (sbctl, kubectl, busybox)
- Wrong sbctl binary (Python package vs real binary)
- File permission issues
- MCP server subprocess failures
- Bundle download/extraction/file access issues
"""

import asyncio
import os
import tempfile
import tarfile
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def create_mock_bundle() -> str:
    """Create a mock support bundle tar.gz file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        bundle_path = tmp.name

    # Create temporary directory structure mimicking a support bundle
    with tempfile.TemporaryDirectory() as temp_dir:
        bundle_dir = Path(temp_dir) / "support-bundle-test"
        bundle_dir.mkdir()

        # Create realistic support bundle structure
        (bundle_dir / "analysis.json").write_text(
            '{"version": "test", "bundle_type": "host"}'
        )
        (bundle_dir / "version.yaml").write_text('version: "test-bundle-1.0"')

        # Create execution-data directory
        exec_dir = bundle_dir / "execution-data"
        exec_dir.mkdir()
        (exec_dir / "metadata.json").write_text('{"collector": "test"}')

        host_dir = bundle_dir / "host-collectors" / "run-host"
        host_dir.mkdir(parents=True)

        # Create mock files that MCP server expects
        (
            host_dir / "mount.txt"
        ).write_text("""proc on /proc type proc (rw,nosuid,nodev,noexec,relatime)
/dev/sda1 on / type ext4 (rw,relatime,errors=remount-ro)
/dev/sdb1 on /var/lib/rook type ext4 (ro,relatime)
tmpfs on /dev/shm type tmpfs (rw,nosuid,nodev)
/dev/sdb1 on /mnt/kubelet/pods/b58acb5d-1234/volumes/kubernetes.io~local-volume/pvc-bab3e901-abcd type ext4 (ro,relatime)
""")

        (
            host_dir / "df.txt"
        ).write_text("""Filesystem      1K-blocks     Used Available Use% Mounted on
/dev/sda1        20971520 18874368   1048576  95% /
/dev/sdb1       104857600 89128960  13631488  85% /var/lib/rook
tmpfs             1048576        0   1048576   0% /dev/shm
""")

        (
            host_dir / "journalctl-kubelet.txt"
        ).write_text("""Sep 05 14:30:15 node1 kubelet[1234]: E0905 14:30:15.123456 1234 pod_workers.go:951] "Error syncing pod" err="orphaned pod failed to rmdir() volume /var/lib/kubelet/pods/b58acb5d-1234/volumes/kubernetes.io~local-volume/pvc-bab3e901-abcd: directory not empty"
Sep 05 14:30:20 node1 kubelet[1234]: E0905 14:30:20.654321 1234 pod_workers.go:951] "Error syncing pod" err="orphaned pod failed to rmdir() volume /var/lib/kubelet/pods/b58acb5d-1234/volumes/kubernetes.io~local-volume/pvc-bab3e901-abcd: directory not empty"
""")

        # Create tar.gz
        with tarfile.open(bundle_path, "w:gz") as tar:
            tar.add(bundle_dir, arcname="support-bundle-test")

    return bundle_path


async def test_system_dependencies():
    """Test that required system binaries are available and working."""
    print("=== Testing System Dependencies ===")

    tests = [
        ("sbctl", ["version"], "sbctl version dev"),
        ("kubectl", ["version", "--client"], "Client Version"),
        ("busybox", ["--help"], "BusyBox"),
    ]

    for binary, args, expected_output in tests:
        try:
            proc = await asyncio.create_subprocess_exec(
                binary,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode() + stderr.decode()

            if proc.returncode == 0 and expected_output in output:
                print(f"✓ {binary} available and working")
            else:
                print(f"❌ {binary} failed - Return code: {proc.returncode}")
                print(f"   Output: {output[:200]}")
                return False
        except FileNotFoundError:
            print(f"❌ {binary} not found in PATH")
            return False

    return True


async def test_sbctl_serve_functionality():
    """Test that sbctl serve command works (not the wrong Python package)."""
    print("\n=== Testing sbctl serve Command ===")

    try:
        # Test sbctl serve --help to ensure it has the serve subcommand
        proc = await asyncio.create_subprocess_exec(
            "sbctl",
            "serve",
            "--help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode() + stderr.decode()

        if proc.returncode == 0 and "Start API server" in output:
            print("✓ sbctl serve command available")
            return True
        else:
            print(f"❌ sbctl serve failed - Return code: {proc.returncode}")
            print(f"   Output: {output[:300]}")

            # Check if this is the wrong sbctl (Python package)
            if "storage-node" in output and "control-plane" in output:
                print(
                    "❌ CRITICAL: Wrong sbctl binary detected (Python package, not Replicated sbctl)"
                )
                print(
                    "   This is the Python 'sbctl' package, not the Replicated support bundle tool"
                )

            return False

    except FileNotFoundError:
        print("❌ sbctl command not found")
        return False


async def test_mcp_server_initialization():
    """Test that MCP server can start without errors."""
    print("\n=== Testing MCP Server Initialization ===")

    try:
        server_params = StdioServerParameters(
            command="/bin/sh",
            args=["-c", "cd /app && timeout 10s uv run troubleshoot-mcp-server"],
            env={**os.environ},
        )

        # Test server can start and respond to basic requests
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Test listing available tools
                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]

                expected_tools = [
                    "initialize_bundle",
                    "list_files",
                    "read_file",
                    "grep_files",
                ]
                missing_tools = [
                    tool for tool in expected_tools if tool not in tool_names
                ]

                if missing_tools:
                    print(f"❌ Missing expected tools: {missing_tools}")
                    print(f"   Available tools: {tool_names}")
                    return False
                else:
                    print(f"✓ MCP server initialized with tools: {tool_names}")
                    return True

    except Exception as e:
        print(f"❌ MCP server initialization failed: {e}")
        return False


async def test_mcp_bundle_processing():
    """Test MCP server with a mock bundle to verify file access."""
    print("\n=== Testing MCP Bundle Processing ===")

    mock_bundle = create_mock_bundle()
    print(f"Created mock bundle: {mock_bundle}")

    try:
        server_params = StdioServerParameters(
            command="/bin/sh",
            args=["-c", "cd /app && uv run troubleshoot-mcp-server"],
            env={**os.environ},
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Test 1: Initialize with mock bundle (file:// URL)
                result = await session.call_tool(
                    "initialize_bundle", {"source": f"file://{mock_bundle}"}
                )

                if result.isError:
                    print("❌ Bundle initialization failed:")
                    if result.content:
                        for content in result.content:
                            if hasattr(content, "text"):
                                print(f"   Error: {content.text[:300]}")
                    return False

                print("✓ Bundle initialized successfully")

                # Test 2: List files in bundle
                file_result = await session.call_tool("list_files", {"path": ""})
                if file_result.isError:
                    print("❌ File listing failed")
                    return False

                # Verify expected files are present
                files_content = ""
                if file_result.content:
                    for content in file_result.content:
                        if hasattr(content, "text"):
                            files_content = content.text

                expected_files = [
                    "analysis.json",
                    "host-collectors/",
                    "version.yaml",
                    "execution-data/",
                ]
                for expected_file in expected_files:
                    if expected_file not in files_content:
                        print(f"❌ Expected file not found: {expected_file}")
                        print(f"   Available files: {files_content[:200]}")
                        return False

                print("✓ File listing successful, expected files present")

                # Test 3: Read a specific file
                read_result = await session.call_tool(
                    "read_file", {"path": "host-collectors/run-host/mount.txt"}
                )

                if read_result.isError:
                    print("❌ File reading failed")
                    return False

                # Verify file content
                file_content = ""
                if read_result.content:
                    for content in read_result.content:
                        if hasattr(content, "text"):
                            file_content = content.text

                if "/dev/sdb1" not in file_content or "ext4" not in file_content:
                    print(f"❌ File content incorrect: {file_content[:100]}")
                    return False

                print("✓ File reading successful, content verified")

                # Test 4: Grep functionality
                grep_result = await session.call_tool(
                    "grep_files",
                    {
                        "pattern": "read-only",
                        "path": "host-collectors",
                        "case_sensitive": False,
                    },
                )

                if grep_result.isError:
                    print("❌ Grep failed")
                    return False

                print("✓ Grep functionality working")

                return True

    except Exception as e:
        print(f"❌ MCP bundle processing failed: {e}")
        return False
    finally:
        # Cleanup
        try:
            os.unlink(mock_bundle)
        except (OSError, FileNotFoundError):
            pass


async def test_file_permissions():
    """Test that the container has proper file permissions for non-root user."""
    print("\n=== Testing File Permissions ===")

    try:
        # Test writing to /app directory (should work as appuser)
        test_file = "/app/test_permissions.tmp"

        # Test write permission
        with open(test_file, "w") as f:
            f.write("test")

        # Test read permission
        with open(test_file, "r") as f:
            content = f.read()

        if content != "test":
            print("❌ File read/write test failed")
            return False

        # Cleanup
        os.unlink(test_file)

        print("✓ File permissions working (can read/write in /app)")
        return True

    except Exception as e:
        print(f"❌ File permissions test failed: {e}")
        return False


async def run_all_tests():
    """Run all integration tests."""
    print("🧪 Starting MCP Integration Tests\n")

    tests = [
        ("System Dependencies", test_system_dependencies),
        ("sbctl serve Command", test_sbctl_serve_functionality),
        ("File Permissions", test_file_permissions),
        ("MCP Server Initialization", test_mcp_server_initialization),
        ("MCP Bundle Processing", test_mcp_bundle_processing),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if await test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")

    print(f"\n📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! MCP server is working correctly.")
        return True
    else:
        print("❌ Some tests failed. MCP server has issues that need to be fixed.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
