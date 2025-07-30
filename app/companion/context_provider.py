import json

from app.ai.ai_client import AIClient
from app.ai.memory import Memory
from app.companion.companion import Companion
from app.config import config
from app.loaders.tool_loader import load_tools
from app.models.schema import PromptMessage


_companions: dict[str, Companion] | None = None

def get_context():
    registry, desc_list = load_tools()

    global _companions
    if _companions is None:
        companions: dict[str, Companion] = {}
        for name, conf in config.companions.items():
            ai_client = AIClient(conf.ai_api_url, conf.ai_api_key, registry, desc_list)
            memory = Memory(conf, conf.memories)
            companion = Companion(conf, ai_client, memory)
            companions[name] = companion
        _companions = companions

    async def handle_stream(message: str):
        msg = PromptMessage(**json.loads(message))
        name = msg.companion_name.strip().lower()

        companion = next((c for c in _companions.values() if c.config.ai_name.lower() == name), None)
        if companion is None:
            print(f"[CONTEXT] [ERROR] Companion '{msg.companion_name}' not found.")
            return
        async for chunk in companion.ask_stream(msg):
            yield chunk

    async def handle(message: str) -> str:
        msg = PromptMessage(**json.loads(message))
        name = msg.companion_name.strip().lower()

        companion = next((c for c in _companions.values() if c.config.ai_name.lower() == name), None)
        if companion is None:
            return f"[CONTEXT] [ERROR] Companion '{msg.companion_name}' not found."

        return await companion.ask(msg)

    return _companions, {
        "handle_stream": handle_stream,
        "handle": handle
    }
