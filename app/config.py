import yaml
from app.models.schema import CompanionConfig, Config, MemoryEntry


def load_config(path: str) -> Config:
    with open(path, 'r') as file:
        raw = yaml.safe_load(file)['config']

    companions = {}
    for name, data in raw['companions'].items():
        memory_data = data.pop('memories', [])
        memory_objects = [MemoryEntry(**mem) for mem in memory_data]
        companions[name] = CompanionConfig(memories=memory_objects, **data)

    return Config(companions=companions)

config = load_config("./config.yml")
