from __future__ import annotations

import json, logging, pickle, hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_STORE_PATH = Path(__file__).parent.parent / "logs" / "vector_store.pkl"

@dataclass
class SearchResult:
    entity_uri: str
    entity_label: str
    entity_type: str
    score: float           # cosine similarity 0-1
    metadata: dict

class VectorStore:
    """In-memory embedding store with optional pgvector backend."""

    def __init__(self):
        self._index: dict[str, dict] = {}   # uri -> {label, type, embedding, metadata}
        self._use_pgvector = False
        self._load()

    def _load(self):
        if _STORE_PATH.exists():
            try:
                with open(_STORE_PATH, "rb") as f:
                    self._index = pickle.load(f)
                logger.info("Vector store loaded: %d entities", len(self._index))
            except Exception:
                self._index = {}

    def _save(self):
        _STORE_PATH.parent.mkdir(exist_ok=True)
        with open(_STORE_PATH, "wb") as f:
            pickle.dump(self._index, f)

    def _embed(self, text: str) -> list[float]:
        import openai as _oa
        from nexus.config.settings import settings
        client = _oa.OpenAI(api_key=settings.openai.api_key)
        resp = client.embeddings.create(model="text-embedding-3-small", input=text[:8000])
        return resp.data[0].embedding

    def index_entity(self, entity_uri: str, label: str, entity_type: str, metadata: dict | None = None) -> None:
        text = f"{label} ({entity_type})"
        if metadata:
            text += " " + " ".join(str(v) for v in metadata.values() if v)
        embedding = self._embed(text)
        self._index[entity_uri] = {
            "label": label,
            "type": entity_type,
            "embedding": embedding,
            "metadata": metadata or {},
        }
        self._save()

    def search(self, query: str, top_k: int = 5, entity_type_filter: str = "") -> list[SearchResult]:
        if not self._index:
            return []
        import numpy as np
        q_emb = self._embed(query)
        q_vec = np.array(q_emb)
        results = []
        for uri, data in self._index.items():
            if entity_type_filter and data["type"] != entity_type_filter:
                continue
            e_vec = np.array(data["embedding"])
            score = float(np.dot(q_vec, e_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(e_vec) + 1e-9))
            results.append(SearchResult(
                entity_uri=uri,
                entity_label=data["label"],
                entity_type=data["type"],
                score=score,
                metadata=data["metadata"],
            ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def index_from_graph(self, entity_types: list[str] | None = None, limit: int = 500) -> int:
        """Bulk index entities from the knowledge graph. Returns count indexed."""
        from nexus.core.stardog_client import get_stardog
        types = entity_types or ["app:Application", "ea:BusinessCapabilityL3", "data:DataProduct", "ai:Agent"]
        db = get_stardog()
        count = 0
        for etype in types:
            sparql = f"""
            SELECT ?e ?label ?domain WHERE {{
                ?e a {etype} .
                OPTIONAL {{ ?e rdfs:label ?label }}
                OPTIONAL {{ ?e ea:domain ?domain }}
            }} LIMIT {limit}
            """
            try:
                _, rows = db.to_rows(db.query(sparql, inject_prefixes=True))
                for row in rows:
                    uri = row.get("e", "")
                    label = row.get("label", uri.split("#")[-1])
                    if uri:
                        self.index_entity(uri, label, etype, {"domain": row.get("domain", "")})
                        count += 1
            except Exception as exc:
                logger.warning("index_from_graph(%s) failed: %s", etype, exc)
        return count

    def size(self) -> int:
        return len(self._index)

    def clear(self) -> None:
        self._index = {}
        if _STORE_PATH.exists():
            _STORE_PATH.unlink()

_store: VectorStore | None = None

def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
