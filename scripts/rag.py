"""Hybrid RAG over the RDF graph — worker module.

Retrieval (free, local, no API key):
  1. SEMANTIC seed — embed the question, find the top-k most similar triples
     (embed_index / fastembed).
  2. GRAPH expansion — take the entities in those seed triples and pull their
     1-hop neighborhood from the graph (graphstore.neighborhood — the SPARQL-side
     of the hybrid).
  3. Assemble the seed + neighborhood triples into a readable context block.

Generation (optional, gated on ANTHROPIC_API_KEY):
  4a. With a key — send schema + context + question to Claude (claude-opus-4-8)
      and return a grounded prose answer.
  4b. Without a key — return the assembled context itself (the prompt that would
      go to the LLM). Useful on its own and proves retrieval works.

No CLI here — argument parsing lives in cli.py.
"""

import os

from rdflib import URIRef

import embed_index
import graphstore

MODEL = "claude-opus-4-8"

SYSTEM = """You answer questions strictly from the supplied knowledge-graph triples.
Use only the facts in CONTEXT. If the context doesn't contain the answer, say so
plainly — do not invent facts. Cite the specific triples you relied on."""


def retrieve(question: str, k: int = 5, graph=None) -> dict:
    """Hybrid retrieval. Returns seed triples, expanded context text, and entities."""
    graph = graph if graph is not None else graphstore.load_graph()

    seeds = embed_index.search(question, k=k)
    entities = set()
    for d in seeds:
        entities.add(URIRef(d["s"]))
        entities.add(URIRef(d["o"]))

    expanded = graphstore.neighborhood(graph, entities)
    context = graphstore.render_triples(graph, expanded)
    return {"seeds": seeds, "entities": entities, "context": context, "graph": graph}


def _build_prompt(question: str, retrieved: dict) -> str:
    schema = graphstore.schema_summary(retrieved["graph"])
    seed_lines = "\n".join(f"  ({d['score']:.2f}) {d['text']}" for d in retrieved["seeds"])
    return (
        f"SCHEMA:\n{schema}\n\n"
        f"Most relevant triples to the question (semantic seeds):\n{seed_lines}\n\n"
        f"CONTEXT (seed entities' neighborhood):\n{retrieved['context']}\n\n"
        f"QUESTION: {question}"
    )


def answer(question: str, k: int = 5, graph=None) -> dict:
    """Run retrieval; generate with Claude if a key is set, else return context.
    Returns {'mode', 'text', 'retrieved'}."""
    retrieved = retrieve(question, k=k, graph=graph)
    prompt = _build_prompt(question, retrieved)

    if not os.getenv("ANTHROPIC_API_KEY"):
        text = (
            "[retrieval-only — no ANTHROPIC_API_KEY set; this is the context that "
            "would be sent to the LLM]\n\n" + prompt
        )
        return {"mode": "retrieval-only", "text": text, "retrieved": retrieved}

    import anthropic  # lazy: only needed when generating

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in msg.content if b.type == "text"), "")
    return {"mode": "generated", "text": text, "retrieved": retrieved}
