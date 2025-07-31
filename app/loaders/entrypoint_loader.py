from asyncio.tasks import Task
from collections.abc import Awaitable
import importlib.util
import os
import asyncio
from typing import Any

_ENTRYPOINTS_DIRS = [
    "./entrypoints",
    os.path.expanduser("~/.config/furina/entrypoints")
]

async def load_entrypoints(context: dict[str, Any]) -> list[Task[Any]]:
    tasks = []

    for entry_dir in _ENTRYPOINTS_DIRS:
        if not os.path.isdir(entry_dir):
            print(f"[ENTRYPOINT] [WARNING] Directory not found: {entry_dir}")
            continue

        for filename in os.listdir(entry_dir):
            if not filename.endswith(".py"):
                continue

            path = os.path.join(entry_dir, filename)
            name = os.path.splitext(filename)[0]

            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                print(f"[ENTRYPOINT] [ERROR] Loading {filename} from {entry_dir}: {e}")
                continue

            start_fn = getattr(module, "start", None)
            if asyncio.iscoroutinefunction(start_fn):
                try:
                    result = await start_fn(context)

                    if not isinstance(result, Awaitable):
                        raise TypeError(
                            f"[ENTRYPOINT] [ERROR] `{filename}` start(ctx) returned non-awaitable: {type(result).__name__}"
                        )

                    if isinstance(result, asyncio.AbstractServer):
                        raise TypeError(
                            f"[ENTRYPOINT] [ERROR] `{filename}` returned `asyncio.Server`, which must be managed manually."
                        )

                    tasks.append(result)
                    print(f"[ENTRYPOINT] Loaded {filename} from {entry_dir}")
                except Exception as e:
                    print(f"[ENTRYPOINT] [ERROR] Starting {filename} from {entry_dir}: {e}")
            else:
                print(f"[ENTRYPOINT] [SKIP] {filename} in {entry_dir} has no async def start(ctx)")

    return tasks
