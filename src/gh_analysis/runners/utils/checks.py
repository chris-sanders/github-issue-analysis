"""Environment requirement checking utilities."""

import asyncio
import os
import subprocess
from collections.abc import Callable


def github():
    """Check GITHUB_TOKEN env var, print error if missing, return True/False."""
    if not os.getenv("GITHUB_TOKEN"):
        print("❌ GITHUB_TOKEN environment variable required")
        return False
    return True


def snowflake():
    """Check required Snowflake env vars, print error if any missing, return True/False."""
    required_vars = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PRIVATE_KEY_PATH",
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(
            f"❌ Required Snowflake environment variables missing: {', '.join(missing_vars)}"
        )
        return False
    return True


def openai():
    """Check OPENAI_API_KEY env var, print error if missing, return True/False."""
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY environment variable required")
        return False
    return True


def podman() -> bool:
    """Check if podman is available"""
    try:
        result = subprocess.run(["podman", "--version"], capture_output=True)
        if result.returncode != 0:
            print("❌ podman not found. Install podman to continue.")
            return False
        return True
    except FileNotFoundError:
        print("❌ podman not found. Install podman to continue.")
        return False


def sbctl_token() -> bool:
    """Check if SBCTL_TOKEN is set"""
    if not os.getenv("SBCTL_TOKEN"):
        print("❌ SBCTL_TOKEN environment variable not set")
        return False
    return True


def anthropic():
    """Check ANTHROPIC_API_KEY env var, print error if missing, return True/False."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY environment variable required for Claude models")
        return False
    return True


def gemini():
    """Check GEMINI_API_KEY env var, print error if missing, return True/False."""
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY environment variable required for Gemini models")
        return False
    return True


async def run_checks(check_functions: list[Callable]) -> bool:
    """Run multiple check functions in parallel, return True only if all pass"""
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, check) for check in check_functions]
    results = await asyncio.gather(*tasks)
    return all(results)
