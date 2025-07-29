import chromadb
from uuid import uuid4
from chromadb.api.types import Embeddable
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from overrides import final

from app.models.schema import CompanionConfig, MemoryEntry


@final
class Memory:
    def __init__(self, conf: CompanionConfig, memories: list[MemoryEntry]) -> None:
        self.conf = conf
        self.memories = memories

        embedding_func: chromadb.EmbeddingFunction[
            chromadb.Documents | Embeddable
        ] = SentenceTransformerEmbeddingFunction(
            "all-MiniLM-L6-v2"
        )

        self.client = chromadb.PersistentClient()
        self.collection = self.client.get_or_create_collection( 
            self.conf.collection_name,
            embedding_function=embedding_func
        )

        count = self.collection.count()
        print(f"[MEMORY] [{self.conf.ai_name}] Found {count} memories in database.")

        if count == 0:
            print(f"[MEMORY] [{self.conf.ai_name}] No memories found, importing base memories...")
            self.load_memories()

    def load_memories(self):
        for memory in self.memories:
            self.collection.upsert(
                memory.id,
                documents=memory.document,
                metadatas=memory.metadata
            )
        print(f"[MEMORY] [{self.conf.ai_name}] Loaded {len(self.memories)} memories.")

    def create_memory(self, memories: list[str]):
        self.collection.upsert(
            str(uuid4()),
            documents=memories,
            metadatas={"type": "short-term"}
        )

    def create_activity_memory(self, activities: list[str]):
        self.collection.upsert(
            ids=[str(uuid4()) for _ in activities],
            documents=activities,
            metadatas=[{"type": "activity"} for _ in activities]
        )

    def clear_activities(self):
        short_term = self.collection.get(where={"type": "activity"})
        self.collection.delete(short_term["ids"])

    def clear_short_term(self):
        short_term = self.collection.get(where={"type": "short-term"})
        self.collection.delete(short_term["ids"])

    def get_memories(self, query: str = ""):
        data = []
        if query == "":
            memories = self.collection.get()
            for i in range(len(memories["ids"])):
                data.append({
                    "id": memories["ids"][i],
                    "document": memories["documents"][i],
                    "metadata": memories["metadatas"][i]
                })
        else:
            memories = self.collection.query(query_texts=query,n_results=15)
            for i in range(len(memories["ids"])):
                data.append({
                    "id": memories["ids"][0][i],
                    "document": memories["documents"][0][i],
                    "metadata": memories["metadatas"][0][i],
                    "distance": memories["distances"][0][i]
                })

            data = sorted(data, key=lambda x: x["distance"])
        return data
