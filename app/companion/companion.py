from copy import deepcopy
from overrides import final

from app.ai.ai_client import AIClient
from app.ai.memory import Memory
from app.models.schema import CompanionConfig, Message, PromptMessage


@final
class Companion:
    def __init__(self, config: CompanionConfig, client: AIClient, memory: Memory) -> None:
        self.config = config
        self.ai_client = client
        self.memory = memory
        self.message_history: list[Message] = []
        self._processed_count = 0

    def _build_messages(self, msg: PromptMessage) -> list[Message]:
        messages: list[Message] = []

        system_prompt = msg.system_prompt.strip()
        if system_prompt:
            if msg.use_personality:
                messages.append(Message("system", self.config.personality_prompt + "\n" + system_prompt))
            else:
                messages.append(Message("system", system_prompt))
        elif msg.use_personality:
            messages.append(Message("system", self.config.personality_prompt))

        metadata = ""
        if msg.metadata:
            metadata = "Metadata:\n"
            metadata += "\n".join(f"- {k}: {v}" for k, v in msg.metadata.items())
            metadata += "\nEnd of metadata section\n"

        user_prompt = self.get_knowledge_for(msg.user_prompt) if msg.allow_memory_lookup else ""
        user_message = Message("user", metadata + user_prompt + msg.user_prompt)

        messages.append(user_message)
        return messages


    async def ask_stream(self, msg: PromptMessage):
        messages = self._build_messages(msg)

        full_response = ""
        async for chunk in self.ai_client.post_messages_stream(messages, msg.max_tokens):
            full_response += chunk
            yield chunk

        if msg.allow_memory_insertion:
            self.message_history.append(Message("user", msg.user_prompt))
            self.message_history.append(Message("assistant", full_response))

    async def ask(self, msg: PromptMessage) -> str:
        messages = self._build_messages(msg)

        response = await self.ai_client.post_messages(messages, msg.max_tokens)

        if msg.allow_memory_insertion:
            self.message_history.append(Message("user", msg.user_prompt))
            self.message_history.append(Message("assistant", response))

        return response

    async def reflect(self, max_tokens: int = 200):
        if self._processed_count > len(self.message_history):
            self._processed_count = 0

        if len(self.message_history) - self._processed_count >= 10:
            print(f"[COMPANION] [{self.config.ai_name}] Reflecting...")
            msgs = deepcopy(self.message_history[-(len(self.message_history) - self._processed_count):])

            for msg in msgs:
                if msg.role == "user" and msg.content != "":
                    msg.content = self.config.user_name + ":" + msg.content + "\n"
                elif msg.role == "assistant" and msg.content != "":
                    msg.content = self.config.ai_name + ":" + msg.content + "\n"

            chat_section = ""
            for msg in msgs:
                chat_section += msg.content

            raw_memories = await self.ai_client.post_messages(
                [Message("user", chat_section + self.config.memory_prompt)],
                max_tokens
            )
            new_memories = raw_memories.split("{qa}")

            for memory in new_memories:
                memory = memory.strip()
                if memory != "":
                    self.memory.create_memory([memory])

            self._processed_count = len(self.message_history)
            print(f"[COMPANION] [{self.config.ai_name}] has {len(new_memories)} new memories.")

    def get_knowledge_for(self, prompt: str) -> str:
        memories = self.memory.collection.query(
                query_texts=prompt,
                n_results=self.config.memory_recall_count
        )
        text = ""
        if len(memories["ids"][0]):
            text += f"{self.config.ai_name} knows these things:\n"
            for i in range(len(memories["ids"][0])):
                text += memories["documents"][0][i] + "\n"
            text += "End of knowledge section\n"

        not_processed_count = len(self.message_history) - self._processed_count
        not_processed = self.message_history[-not_processed_count:]

        if not_processed:
            text += "Latest conversation messages:\n"
            for msg in not_processed:
                if msg.role == "user" and msg.content != "":
                    text += self.config.user_name + ":" + msg.content + "\n"
                elif msg.role == "assistant" and msg.content != "":
                    text += self.config.ai_name + ":" + msg.content + "\n"
            text += "End of conversation section.\n"

        return text

    def get_knowledge_section(self) -> str:
        query = ""
        for msg in self.message_history[-self.config.memory_query_message_count:]:
            if msg.role == "user" and msg.content != "":
                query += self.config.user_name + ":" + msg.content + "\n"
            elif msg.role == "assistant" and msg.content != "":
                query += self.config.ai_name + ":" + msg.content + "\n"

        memories = self.memory.collection.query(
            query_texts=query,
            n_results=self.config.memory_recall_count
        )

        text = ""
        if len(memories["ids"][0]):
            text += f"{self.config.ai_name} knows these things:\n"
            for i in range(len(memories["ids"][0])):
                text += memories["documents"][0][i] + "\n"
            text += "End of knowledge section\n"

        return text
