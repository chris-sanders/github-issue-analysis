#!/usr/bin/env python3
"""
Start all services needed for exp05_temporal: Temporal, Phoenix, and Worker.

This script manages three background processes:
1. Temporal dev server
2. Phoenix server
3. Temporal worker

Usage:
    uv run python -m exp.exp05_temporal.start_services

Press Ctrl+C to stop all services gracefully.
"""

import asyncio
import os
import signal
import sys
from pathlib import Path

# Track subprocesses for cleanup
processes = []
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully - set shutdown flag."""
    global shutdown_requested
    shutdown_requested = True
    print("\n🛑 Shutting down all services...")


async def shutdown_services():
    """Async shutdown of all services."""
    # Kill entire process groups (including all child processes)
    for proc in processes:
        try:
            # Kill the process group, not just the process
            if proc.pid:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except:
            # Fallback to regular terminate
            try:
                proc.terminate()
            except:
                pass

    # Wait for graceful shutdown
    try:
        await asyncio.wait_for(
            asyncio.gather(
                *[proc.wait() for proc in processes], return_exceptions=True
            ),
            timeout=3.0,
        )
    except asyncio.TimeoutError:
        # Force kill process groups
        for proc in processes:
            try:
                if proc.pid:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except:
                try:
                    proc.kill()
                except:
                    pass
        # Wait for kill to complete
        await asyncio.gather(
            *[proc.wait() for proc in processes], return_exceptions=True
        )

    print("✅ All services stopped")


async def start_temporal():
    """Start Temporal dev server."""
    print("📦 Starting Temporal dev server...")

    # Redirect output to /dev/null to keep terminal clean
    # Create new process group so we can kill the entire process tree
    devnull = asyncio.subprocess.DEVNULL
    proc = await asyncio.create_subprocess_exec(
        "temporal",
        "server",
        "start-dev",
        "--ip",
        "0.0.0.0",
        "--ui-port",
        "8233",
        stdout=devnull,
        stderr=devnull,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )
    processes.append(proc)

    # Wait for Temporal to be ready
    print("   Waiting for Temporal to start...")
    for i in range(30):
        try:
            # Try to connect
            test_proc = await asyncio.create_subprocess_exec(
                "temporal",
                "operator",
                "namespace",
                "list",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await test_proc.wait()
            if test_proc.returncode == 0:
                print("   ✅ Temporal ready at http://localhost:8233")
                return
        except:
            pass
        await asyncio.sleep(1)

    print("   ⚠️ Temporal may not be fully ready, continuing anyway...")


async def start_phoenix():
    """Start Phoenix server."""
    print("🔭 Starting Phoenix server...")

    # Set Phoenix data directory
    phoenix_dir = Path("data/phoenix")
    phoenix_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PHOENIX_PORT"] = "6006"
    env["PHOENIX_WORKING_DIR"] = str(phoenix_dir.absolute())

    # Redirect output to /dev/null to keep terminal clean
    # Create new process group so we can kill the entire process tree
    devnull = asyncio.subprocess.DEVNULL
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "phoenix",
        "serve",
        stdout=devnull,
        stderr=devnull,
        env=env,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )
    processes.append(proc)

    # Wait for Phoenix to be ready (takes ~10s for migrations)
    print("   Waiting for Phoenix to start (migrations may take ~10s)...")
    for i in range(60):  # Increased from 30 to 60 seconds
        try:
            # Check if port is open
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("localhost", 6006), timeout=1.0
            )
            writer.close()
            await writer.wait_closed()
            print("   ✅ Phoenix ready at http://localhost:6006")
            return
        except:
            await asyncio.sleep(1)

    print("   ⚠️ Phoenix may not be fully ready, continuing anyway...")


async def start_worker():
    """Start Temporal worker."""
    print("⚙️  Starting Temporal worker...")

    # Redirect output to /dev/null to keep terminal clean
    # Create new process group so we can kill the entire process tree
    devnull = asyncio.subprocess.DEVNULL
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "python",
        "-m",
        "exp.exp05_temporal.workers.main_worker",
        stdout=devnull,
        stderr=devnull,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )
    processes.append(proc)

    # Give worker a moment to initialize
    await asyncio.sleep(3)
    print("   ✅ Worker started")


async def monitor_output(proc, prefix):
    """Monitor and print output from a process."""
    if not proc.stdout:
        return

    while True:
        try:
            line = await proc.stdout.readline()
            if not line:
                break
            # Print with prefix for clarity
            print(f"[{prefix}] {line.decode().rstrip()}")
        except:
            break


async def main():
    """Start all services and monitor them."""
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("🚀 Starting exp05_temporal services...\n")

    # Optional: Clean Phoenix databases (set CLEAN_PHOENIX_DATA=true to enable)
    # This deletes all traces on startup
    if os.getenv("CLEAN_PHOENIX_DATA", "").lower() in ("1", "true", "yes"):
        import shutil

        phoenix_home = Path.home() / ".phoenix"
        phoenix_data = Path("data/phoenix")

        print("🧹 Cleaning Phoenix databases (CLEAN_PHOENIX_DATA=true)...")
        if phoenix_home.exists():
            shutil.rmtree(phoenix_home)
            print(f"   ✅ Cleaned {phoenix_home}")
        if phoenix_data.exists():
            shutil.rmtree(phoenix_data)
            print(f"   ✅ Cleaned {phoenix_data}")
        print()

    try:
        # Start services in order
        await start_temporal()
        # Wait extra time for Temporal to be fully ready before starting worker
        await asyncio.sleep(3)
        print()

        await start_phoenix()
        # Wait extra time for Phoenix migrations to complete
        await asyncio.sleep(5)
        print()

        await start_worker()
        print()

        print("=" * 60)
        print("✅ All services running!")
        print()
        print("Services:")
        print("  📦 Temporal UI:  http://localhost:8233")
        print("  🔭 Phoenix UI:   http://localhost:6006")
        print("  ⚙️  Worker:       exp05-temporal-worker (task queue: exp05-analysis)")
        print()
        print("Ready to run tests:")
        print("  uv run python -m exp.exp05_temporal.test_single")
        print()
        print("Press Ctrl+C to stop all services")
        print("=" * 60)
        print()

        # Monitor processes - if any dies or shutdown requested, cleanup
        service_names = ["Temporal", "Phoenix", "Worker"]
        while True:
            # Check for shutdown request
            if shutdown_requested:
                await shutdown_services()
                return

            # Check if any process died
            for i, proc in enumerate(processes):
                # Check returncode (asyncio Process updates this automatically)
                if proc.returncode is not None:
                    print(f"\n❌ {service_names[i]} exited with code {proc.returncode}")
                    await shutdown_services()
                    return

            await asyncio.sleep(1)

    except Exception as e:
        print(f"\n❌ Error starting services: {e}")
        await shutdown_services()
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Services stopped")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
