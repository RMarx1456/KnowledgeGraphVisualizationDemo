"""Load extracted Turtle runs into one rdflib Graph and query it — worker module.

Loads the **latest run per source file** (from output/index.jsonl) so the graph
is coherent and current-namespace, rather than merging every historical run.
Shared by the SPARQL endpoint, the embedding index, and the RAG pipeline.

No CLI here — argument parsing lives in cli.py.
"""

import json
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import RDF, RDFS

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = ROOT / "output"
MANIFEST = OUTPUT_ROOT / "index.jsonl"


def latest_runs() -> list[Path]:
    """Return the newest .ttl per source filename, by timestamp."""
    if not MANIFEST.exists():
        return []
    newest: dict[str, dict] = {}
    with MANIFEST.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            cur = newest.get(r["source"])
            if cur is None or r["timestamp"] > cur["timestamp"]:
                newest[r["source"]] = r
    return [ROOT / r["path"] for r in newest.values()]


def load_graph(paths: list[Path] | None = None) -> Graph:
    """Parse the given .ttl files (default: latest run per source) into one Graph."""
    g = Graph()
    for ttl in (paths if paths is not None else latest_runs()):
        g.parse(ttl, format="turtle")
    return g


def schema_summary(graph: Graph) -> str:
    """A compact, LLM-facing description of the graph's vocabulary, so a model
    can write valid SPARQL: prefixes, predicates in use, and entity types."""
    preds = sorted({str(p) for p in set(graph.predicates())})
    types = sorted({str(o) for _, _, o in graph.triples((None, RDF.type, None))})

    # Only show prefixes whose namespace actually prefixes an IRI in the data,
    # not rdflib's dozens of default bindings (brick, csvw, dcat, ...).
    iris = preds + types + [str(s) for s in set(graph.subjects())]
    used = sorted(
        (p, str(ns)) for p, ns in graph.namespaces()
        if any(iri.startswith(str(ns)) for iri in iris)
    )
    prefixes = "\n".join(f"  PREFIX {p}: <{ns}>" for p, ns in used)

    lines = [f"Triples: {len(graph)}", "", "Prefixes:", prefixes, "", "Predicates in use:"]
    lines += [f"  {p}" for p in preds]
    if types:
        lines += ["", "Entity types (rdf:type):"] + [f"  {t}" for t in types]
    return "\n".join(lines)


def run_sparql(graph: Graph, query: str):
    """Execute a SPARQL query; returns an rdflib query Result."""
    return graph.query(query)


# --- Helpers for embedding + RAG -----------------------------------------

def label_for(graph: Graph, term) -> str:
    """Human-readable label: rdfs:label if present, else the slug de-slugged."""
    lbl = graph.value(term, RDFS.label)
    if lbl is not None:
        return str(lbl)
    s = str(term).rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    return s.replace("_", " ")


def triple_sentences(graph: Graph) -> list[dict]:
    """Each relational triple as an embeddable sentence + its IRIs.
    Skips rdfs:label / rdf:type (structural, not content)."""
    out = []
    for s, p, o in graph:
        if p in (RDFS.label, RDF.type):
            continue
        text = f"{label_for(graph, s)} {label_for(graph, p)} {label_for(graph, o)}"
        out.append({"text": text, "s": str(s), "p": str(p), "o": str(o)})
    return out


def neighborhood(graph: Graph, entities) -> set:
    """All relational triples (excluding rdfs:label) touching any given entity
    as subject or object — the 1-hop SPARQL-style expansion for hybrid RAG."""
    triples = set()
    for e in entities:
        for s, p, o in graph.triples((e, None, None)):
            if p != RDFS.label:
                triples.add((s, p, o))
        for s, p, o in graph.triples((None, None, e)):
            if p != RDFS.label:
                triples.add((s, p, o))
    return triples


def render_triples(graph: Graph, triples) -> str:
    """Readable, deduped lines: '<subject> — <predicate> → <object>'."""
    lines = sorted({
        f"{label_for(graph, s)} — {label_for(graph, p)} → {label_for(graph, o)}"
        for s, p, o in triples
    })
    return "\n".join(lines)
