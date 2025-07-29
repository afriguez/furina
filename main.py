import asyncio
import signal
import sys

from app.companion.context_provider import get_context
from app.loaders.entrypoint_loader import load_entrypoints

terminate = False
def kill(sig, frame):
    global terminate
    print("\nExiting...")
    terminate = True

signal.signal(signal.SIGINT, kill)
signal.signal(signal.SIGTERM, kill)

async def main():
    ctx = get_context()
    tasks = await load_entrypoints(ctx)
    try:
        while not terminate:
            await asyncio.sleep(0.1)
    finally:
        for task in tasks:
            if hasattr(task, "close"):
                task.close()
                await task.wait_closed()
            elif hasattr(task, "cancel"):
                task.cancel()
        sys.exit(0)

asyncio.run(main())
