import os
import yaml
from app.models.schema import CompanionConfig, Config, MemoryEntry


def load_config(path: str) -> Config:
    with open(path, "r") as file:
        raw = yaml.safe_load(file)["config"]

    timezone = raw.get("timezone", "UTC")
    companions = {}
    for name, data in raw["companions"].items():
        memory_data = data.pop("memories", [])
        memory_objects = [MemoryEntry(**mem) for mem in memory_data]
        companions[name] = CompanionConfig(memories=memory_objects, **data)

    print(f"[CONFIG] Loaded {len(companions)} companions")

    return Config(companions=companions, timezone=timezone)


default_file = os.path.expanduser("~/.config/furina/config.yml")
fallback_file = "./config.yml"

if os.path.exists(default_file):
    config = load_config(default_file)
else:
    config = load_config(fallback_file)
