import asyncio
import signal
import sys

from app.companion.companion import Companion
from app.companion.context_provider import get_context
from app.loaders.entrypoint_loader import load_entrypoints

terminate = False
reflect_interval = 5

def kill(sig, frame):
    global terminate
    print("\nShutting down... Please wait.")
    terminate = True

signal.signal(signal.SIGINT, kill)
signal.signal(signal.SIGTERM, kill)

async def run_reflection_loop(companion: Companion):
    try:
        while not terminate:
            await companion.reflect()
            await asyncio.sleep(reflect_interval)
    except asyncio.CancelledError:
        pass

async def main():
    companions, ctx = get_context()
    tasks = await load_entrypoints(ctx)
    print(tasks)

    reflection_tasks = [
        asyncio.create_task(run_reflection_loop(companions[c]))
        for c in companions
    ]
    tasks.extend(reflection_tasks)

    try:
        while not terminate:
            await asyncio.sleep(0.1)
    finally:
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        sys.exit(0)

asyncio.run(main())
