import importlib.util
import inspect
import os
import sys
from typing import Any


TOOL_DIRS = [
    "./tools",
    os.path.expanduser("~/.config/furina/tools")
]

def load_tools() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    tool_registry: dict[str, Any] = {}
    tool_desc_list: list[dict[str, Any]] = []

    for tools_dir in TOOL_DIRS:
        if not os.path.isdir(tools_dir):
            print(f"[TOOLS] [WARN] Directory not found: {tools_dir}")
            continue

        for filename in os.listdir(tools_dir):
            if not filename.endswith(".py"):
                continue

            path = os.path.join(tools_dir, filename)
            name = os.path.splitext(filename)[0]

            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                print(f"[TOOLS] [ERROR] Failed to load module {filename}: {e}")
                continue

            for class_name, class_obj in inspect.getmembers(module, inspect.isclass):
                if class_obj.__module__ != module.__name__:
                    continue

                try:
                    instance = class_obj()

                    tool_attr = getattr(instance, "tool", None)
                    if not isinstance(tool_attr, dict):
                        print(f"[TOOLS] [WARN] {class_name} in {filename}: `.tool` must be a dict.")
                        continue

                    run_method = getattr(instance, "run", None)
                    if not callable(run_method):
                        print(f"[TOOLS] [WARN] {class_name} in {filename}: `.run()` method missing or not callable.")
                        continue

                    tool_registry[class_name] = instance
                    tool_desc_list.append(tool_attr)

                except Exception as e:
                    print(f"[TOOLS] [ERROR] Failed to instantiate {class_name} in {filename}: {e}")

    return tool_registry, tool_desc_list
