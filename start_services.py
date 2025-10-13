#!/usr/bin/env python3
"""Start all services for gh-analysis Temporal testing.

Starts Temporal, Phoenix, and Worker in background.
"""

import asyncio
import os
import signal
import sys
from pathlib import Path

processes = []
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global shutdown_requested
    shutdown_requested = True
    print("\n🛑 Shutting down all services...")


async def shutdown_services():
    """Shutdown all services."""
    for proc in processes:
        try:
            if proc.pid:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except:
            try:
                proc.terminate()
            except:
                pass

    try:
        await asyncio.wait_for(
            asyncio.gather(*[proc.wait() for proc in processes], return_exceptions=True),
            timeout=3.0
        )
    except asyncio.TimeoutError:
        for proc in processes:
            try:
                if proc.pid:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except:
                try:
                    proc.kill()
                except:
                    pass
        await asyncio.gather(*[proc.wait() for proc in processes], return_exceptions=True)

    print("✅ All services stopped")


async def start_temporal():
    """Start Temporal dev server."""
    print("📦 Starting Temporal dev server...")
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
        preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
    )
    processes.append(proc)

    await asyncio.sleep(2)
    for i in range(30):
        try:
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


async def start_phoenix():
    """Start Phoenix server."""
    print("🔭 Starting Phoenix server...")
    phoenix_dir = Path("data/phoenix")
    phoenix_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PHOENIX_PORT"] = "6006"
    env["PHOENIX_WORKING_DIR"] = str(phoenix_dir.absolute())

    devnull = asyncio.subprocess.DEVNULL
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "phoenix",
        "serve",
        stdout=devnull,
        stderr=devnull,
        env=env,
        preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
    )
    processes.append(proc)

    await asyncio.sleep(2)
    for i in range(60):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("localhost", 6006),
                timeout=1.0
            )
            writer.close()
            await writer.wait_closed()
            print("   ✅ Phoenix ready at http://localhost:6006")
            return
        except:
            await asyncio.sleep(1)


async def start_worker():
    """Start Temporal worker."""
    print("⚙️  Starting Temporal worker...")
    devnull = asyncio.subprocess.DEVNULL
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "python",
        "-m",
        "gh_analysis.workers.main_worker",
        stdout=devnull,
        stderr=devnull,
        preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
    )
    processes.append(proc)

    await asyncio.sleep(3)
    print("   ✅ Worker started")


async def main():
    """Start all services."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("🚀 Starting gh-analysis Temporal services...\n")

    try:
        await start_temporal()
        await asyncio.sleep(3)
        print()

        await start_phoenix()
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
        print("  ⚙️  Worker:       gh-analysis-worker (task queue: gh-analysis-queue)")
        print()
        print("Ready to run tests:")
        print("  uv run python test_workflow.py")
        print()
        print("Press Ctrl+C to stop all services")
        print("=" * 60)
        print()

        while True:
            if shutdown_requested:
                await shutdown_services()
                return

            for i, proc in enumerate(processes):
                if proc.returncode is not None:
                    print(f"\n❌ Service {i} exited with code {proc.returncode}")
                    await shutdown_services()
                    return

            await asyncio.sleep(1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
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
