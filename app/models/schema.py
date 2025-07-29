from dataclasses import dataclass, field
from typing import Literal


@dataclass
class PromptMessage:
    companion_name: str
    user_prompt: str
    system_prompt: str
    use_personality: bool
    allow_memory_lookup: bool
    allow_memory_insertion: bool
    source: str
    metadata: dict[str, str]
    max_tokens: int
    stream: bool

@dataclass
class Message:
    role: Literal["user", "assistant", "system"]
    content: str

@dataclass
class MemoryEntry:
    id: str
    document: str
    metadata: dict[str, str]

@dataclass
class CompanionConfig:
    user_name: str
    ai_name: str
    collection_name: str
    memory_prompt: str
    memory_recall_count: int
    memory_query_message_count: int
    ai_api_key: str
    ai_api_url: str
    personality_prompt: str
    memories: list[MemoryEntry] = field(default_factory=list)

@dataclass
class Config:
    companions: dict[str, CompanionConfig]
