from __future__ import annotations
import hashlib
import re
from pathlib import Path
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

class DeterministicEmbeddings(Embeddings):
    dimensions = 256
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]
    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            index = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % self.dimensions
            vector[index] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

class KnowledgeRetriever:
    """LangChain InMemoryVectorStore over the supplied Markdown files."""
    def __init__(self, knowledge_dir: Path):
        documents = []
        self.documents_by_source: dict[str, list[Document]] = {}
        for path in sorted(knowledge_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for section in (x.strip() for x in re.split(r"\n(?=#)", text)):
                if section:
                    document = Document(page_content=section, metadata={"source": path.name})
                    documents.append(document)
                    self.documents_by_source.setdefault(path.name, []).append(document)
        self.store = InMemoryVectorStore(DeterministicEmbeddings())
        if documents:
            self.store.add_documents(documents)
    def search(self, query: str, k: int = 3, preferred_source: str | None = None) -> list[Document]:
        """Retrieve semantically, pinning an authoritative source when routing identifies one."""
        preferred = list(self.documents_by_source.get(preferred_source or "", []))
        semantic = self.store.similarity_search(query, k=k)
        combined = preferred + semantic
        unique: list[Document] = []
        seen: set[tuple[str, str]] = set()
        for document in combined:
            key = (document.metadata.get("source", ""), document.page_content)
            if key not in seen:
                seen.add(key)
                unique.append(document)
        return unique[:k]
