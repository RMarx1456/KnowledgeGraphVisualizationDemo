"""Semantic index over RDF triples with fastembed (ONNX, CPU, no torch) — worker module.

Each relational triple is embedded as a short sentence ("Mario loves coins"); a
query is embedded the same way and matched by cosine similarity. Vectors persist
to output/rag_index/ so we embed once, not per question.

This is the *semantic* half of the hybrid RAG retriever (the graph/SPARQL half is
neighborhood expansion in graphstore + the SPARQL endpoint). No API key needed.

No CLI here — argument parsing lives in cli.py.
"""

import json
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

import graphstore

INDEX_DIR = graphstore.OUTPUT_ROOT / "rag_index"
VECTORS = INDEX_DIR / "vectors.npy"
DOCS = INDEX_DIR / "docs.jsonl"
MODEL_NAME = "BAAI/bge-small-en-v1.5"  # small, CPU-friendly, 384-dim

_model: TextEmbedding | None = None


def _embedder() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def _normalize(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.clip(norm, 1e-12, None)


def build_index(graph=None) -> int:
    """Embed every relational triple in the graph and persist. Returns count."""
    graph = graph if graph is not None else graphstore.load_graph()
    docs = graphstore.triple_sentences(graph)
    if not docs:
        raise SystemExit("No triples to index — run an extraction first.")

    vectors = np.asarray(list(_embedder().embed(d["text"] for d in docs)), dtype=np.float32)
    vectors = _normalize(vectors)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(VECTORS, vectors)
    with DOCS.open("w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps(d) + "\n")
    return len(docs)


def load_index() -> tuple[np.ndarray, list[dict]]:
    if not VECTORS.exists() or not DOCS.exists():
        raise SystemExit("No embedding index yet — build it first (cli.py index).")
    vectors = np.load(VECTORS)
    with DOCS.open(encoding="utf-8") as fh:
        docs = [json.loads(line) for line in fh if line.strip()]
    return vectors, docs


def search(question: str, k: int = 5) -> list[dict]:
    """Top-k triples most semantically similar to the question.
    Each result dict is a triple doc plus a 'score'."""
    vectors, docs = load_index()
    q = _normalize(np.asarray(list(_embedder().query_embed([question]))[0], dtype=np.float32))
    scores = vectors @ q
    top = np.argsort(scores)[::-1][:k]
    return [{**docs[i], "score": float(scores[i])} for i in top]
