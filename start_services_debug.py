#!/usr/bin/env python3
"""Start services for debugging - KEEP STDERR VISIBLE."""

import asyncio
import signal

processes = []


async def start_temporal():
    """Start Temporal - stderr VISIBLE."""
    print("📦 Starting Temporal...")
    proc = await asyncio.create_subprocess_exec(
        "temporal",
        "server",
        "start-dev",
        "--ip",
        "0.0.0.0",
        "--ui-port",
        "8233",
        stdout=asyncio.subprocess.DEVNULL,
        # Keep stderr visible to see crashes!
    )
    processes.append(proc)

    await asyncio.sleep(2)
    for i in range(30):
        try:
            test = await asyncio.create_subprocess_exec(
                "temporal",
                "operator",
                "namespace",
                "list",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await test.wait()
            if test.returncode == 0:
                print("   ✅ Temporal ready")
                return
        except:
            pass
        await asyncio.sleep(1)


async def start_worker():
    """Start worker - stderr VISIBLE."""
    print("⚙️  Starting worker...")
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "python",
        "-m",
        "gh_analysis.workers.main_worker",
        stdout=asyncio.subprocess.DEVNULL,
        # Keep stderr visible!
    )
    processes.append(proc)
    await asyncio.sleep(3)
    print("   ✅ Worker started")


async def main():
    signal.signal(signal.SIGINT, lambda s, f: print("\nStopping...") or exit(0))

    await start_temporal()
    await start_worker()

    print("\n✅ Services running - Press Ctrl+C to stop\n")
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
