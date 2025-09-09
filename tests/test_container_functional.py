#!/usr/bin/env python3
"""
Simple functional test for containerized environment.

Tests basic functionality that should work regardless of specific implementation:
- Can import key modules?
- Do CLI commands respond to help?
- Can basic data structures be handled?

This avoids testing implementation details or requiring real bundle URLs.
"""

import subprocess
import sys


def test_cli_help():
    """Test that CLI help commands work and have required options."""
    print("=== Testing CLI Help Commands ===")

    try:
        # Test main help
        result = subprocess.run(
            ["gh-analysis", "--help"], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and "GitHub issue collection" in result.stdout:
            print("✓ Main CLI help working")
        else:
            print(f"❌ Main CLI help failed: {result.stderr}")
            return False

        # Test process troubleshoot help
        result = subprocess.run(
            ["gh-analysis", "process", "troubleshoot", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Check for key options that indicate functional CLI
        required_options = ["limit-comments", "agent", "url"]
        missing_options = []

        for option in required_options:
            if option not in result.stdout:
                missing_options.append(option)

        if result.returncode == 0 and not missing_options:
            print(
                f"✓ Troubleshoot CLI help working with all required options: {required_options}"
            )
        else:
            if missing_options:
                print(f"❌ Troubleshoot CLI missing options: {missing_options}")
            else:
                print(f"❌ Troubleshoot CLI help failed: {result.stderr}")
            return False

        return True

    except Exception as e:
        print(f"❌ CLI help test failed: {e}")
        return False


def test_environment_validation():
    """Test that CLI validates required environment variables."""
    print("\n=== Testing Environment Validation ===")

    try:
        # Test using uv run since that's how it's invoked in container
        result = subprocess.run(
            [
                "uv",
                "run",
                "gh-analysis",
                "process",
                "troubleshoot",
                "--url",
                "https://github.com/test/test/issues/1",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin"},
        )

        if result.returncode != 0:
            print("✓ CLI properly validates required environment variables")
            return True
        else:
            print("❌ CLI should fail when environment variables are missing")
            print(f"   Output: {result.stdout[:200]}")
            return False

    except Exception as e:
        print(f"❌ Environment validation test failed: {e}")
        return False


def test_import_core_modules():
    """Test that core modules can be imported."""
    print("\n=== Testing Core Module Imports ===")

    modules_to_test = [
        "gh_analysis.cli.process",
        "gh_analysis.runners.adapters.mcp_adapter",
        "gh_analysis.storage.file_storage",
    ]

    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"✓ {module_name} imports successfully")
        except ImportError as e:
            print(f"❌ {module_name} import failed: {e}")
            return False
        except Exception as e:
            print(f"❌ {module_name} import error: {e}")
            return False

    return True


def run_all_tests():
    """Run all functional tests."""
    print("🧪 Container Functional Tests")
    print("============================")
    print("Testing basic containerized functionality without requiring")
    print("real bundle URLs or specific implementation details.\n")

    tests = [
        ("CLI Help Commands", test_cli_help),
        ("Environment Validation", test_environment_validation),
        ("Core Module Imports", test_import_core_modules),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():  # type: ignore[no-untyped-call]
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")

    print(f"\n📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All functional tests passed!")
        print("Container environment is working correctly.")
        return True
    else:
        print("❌ Some functional tests failed.")
        print("Container has functional issues.")
        return False


if __name__ == "__main__":
    success = run_all_tests()  # type: ignore[no-untyped-call]
    sys.exit(0 if success else 1)
