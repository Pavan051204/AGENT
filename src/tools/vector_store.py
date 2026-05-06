import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Document:
    content: str
    metadata: dict[str, Any]
    embedding: list[float] | None = None  # kept for compat, not used


class VectorStore:
    """Local TF-IDF vector store — no API calls, instant results."""

    def __init__(self, persist_path: str) -> None:
        self.persist_path = Path(persist_path)
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self.documents: list[Document] = []
        self.index_file = self.persist_path / "vector_index.json"

        # TF-IDF index (built on load / add)
        self._vocab: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._tfidf_matrix: list[dict[str, float]] = []

        self.load_index()

    # ------------------------------------------------------------------ #
    #  Text helpers
    # ------------------------------------------------------------------ #

    _STOP_WORDS = frozenset(
        "a an the is are was were be been being have has had do does did "
        "will would shall should may might can could of in to for on with "
        "at by from as into through during before after above below between "
        "out off over under again further then once here there when where "
        "why how all each every both few more most other some such no nor "
        "not only own same so than too very and but or if while".split()
    )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lower-case, strip punctuation, split into words."""
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return [w for w in text.split() if len(w) > 1]

    def _filtered_tokens(self, text: str) -> list[str]:
        return [w for w in self._tokenize(text) if w not in self._STOP_WORDS]

    # ------------------------------------------------------------------ #
    #  TF-IDF
    # ------------------------------------------------------------------ #

    def _build_index(self) -> None:
        """Build TF-IDF index from all loaded documents."""
        n = len(self.documents)
        if n == 0:
            return

        # Document frequency
        df: Counter[str] = Counter()
        doc_tokens: list[list[str]] = []
        for doc in self.documents:
            tokens = self._filtered_tokens(doc.content)
            doc_tokens.append(tokens)
            unique = set(tokens)
            for w in unique:
                df[w] += 1

        # IDF
        self._idf = {w: math.log((n + 1) / (freq + 1)) + 1 for w, freq in df.items()}

        # TF-IDF vectors per document
        self._tfidf_matrix = []
        for tokens in doc_tokens:
            tf = Counter(tokens)
            total = len(tokens) or 1
            vec: dict[str, float] = {}
            for w, count in tf.items():
                vec[w] = (count / total) * self._idf.get(w, 1.0)
            self._tfidf_matrix.append(vec)

    def _cosine_sim(self, vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
        """Cosine similarity between two sparse TF-IDF vectors."""
        common = set(vec_a) & set(vec_b)
        if not common:
            return 0.0
        dot = sum(vec_a[w] * vec_b[w] for w in common)
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def add_documents(self, docs: list[Document]) -> None:
        """Add documents and rebuild the TF-IDF index."""
        self.documents.extend(docs)
        self._build_index()
        self.save_index()

    def query(self, query_text: str, k: int = 5, role: str | None = None) -> list[Document]:
        """Query for relevant documents using TF-IDF cosine similarity."""
        if not self.documents:
            return []

        # Build query vector
        tokens = self._filtered_tokens(query_text)
        tf = Counter(tokens)
        total = len(tokens) or 1
        query_vec: dict[str, float] = {}
        for w, count in tf.items():
            query_vec[w] = (count / total) * self._idf.get(w, 1.0)

        scored: list[tuple[float, Document]] = []

        for i, doc in enumerate(self.documents):
            # RBAC filtering
            doc_role = doc.metadata.get("role", "all")
            if role:
                if isinstance(doc_role, list):
                    if role not in doc_role and "all" not in doc_role:
                        continue
                elif doc_role not in (role, "all"):
                    continue

            if i < len(self._tfidf_matrix):
                sim = self._cosine_sim(query_vec, self._tfidf_matrix[i])
            else:
                sim = 0.0

            if sim > 0:
                scored.append((sim, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:k]]

    # ------------------------------------------------------------------ #
    #  Persistence
    # ------------------------------------------------------------------ #

    def save_index(self) -> None:
        """Save documents to disk."""
        data = {
            "documents": [
                {
                    "content": doc.content,
                    "metadata": doc.metadata,
                }
                for doc in self.documents
            ]
        }
        self.index_file.write_text(json.dumps(data, indent=2))

    def load_index(self) -> None:
        """Load documents from disk and rebuild TF-IDF index."""
        if self.index_file.exists():
            data = json.loads(self.index_file.read_text())
            self.documents = [
                Document(
                    content=item["content"],
                    metadata=item["metadata"],
                )
                for item in data.get("documents", [])
            ]
            self._build_index()
            print(f"Loaded {len(self.documents)} document chunks into TF-IDF index.")
