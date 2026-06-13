"""Shared RDF layer: turn extracted triples into an rdflib.Graph and emit terse Turtle.

Every extraction method funnels through here, so all output is the same RDF
shape and directly comparable. (Currently spaCy is the only method.)

Conventions:
    ex:    <http://example.org/kg/>       entities (subjects/objects)
    rel:   <http://example.org/kg/rel/>    predicates
    kg:    <http://example.org/kg/class/>  entity types (via rdf:type)

Entity and predicate labels are slugified into local names; the original text is
preserved on each entity as an rdfs:label so nothing is lost.
"""

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

OUTPUT_ROOT = Path(__file__).resolve().parent.parent / "output"

# Sibling namespaces (none is a string-prefix of another), so qname-based tools
# like Raptor's `rapper` render clean prefixes (rel:be, not ex:rel/be).
EX = Namespace("http://example.org/kg/entity/")
REL = Namespace("http://example.org/kg/relation/")
KG = Namespace("http://example.org/kg/class/")


def _slug(text: str) -> str:
    """Make a safe, readable local name: 'the red car' -> 'the_red_car'."""
    s = re.sub(r"[^\w]+", "_", text.strip(), flags=re.UNICODE)
    return s.strip("_") or "_blank"


def entity_uri(label: str) -> URIRef:
    return EX[_slug(label)]


def predicate_uri(label: str) -> URIRef:
    return REL[_slug(label)]


def build_graph(triples, types=None) -> Graph:
    """triples: iterable of (subject, predicate, object) label strings.
    types:   optional {entity_label: TYPE} mapping for methods that type entities."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("rel", REL)
    g.bind("kg", KG)

    types = types or {}
    labelled = set()

    def ensure_entity(label):
        uri = entity_uri(label)
        if uri not in labelled:
            g.add((uri, RDFS.label, Literal(label)))
            labelled.add(uri)
        if label in types:
            g.add((uri, RDF.type, KG[_slug(types[label])]))
        return uri

    for s, p, o in triples:
        g.add((ensure_entity(s), predicate_uri(p), ensure_entity(o)))

    return g


def to_turtle(triples, types=None) -> str:
    """Convenience: build the graph and return terse Turtle text."""
    return build_graph(triples, types).serialize(format="turtle")


# --- Run identity & output convention -------------------------------------
# Each run is ID'd, versioned, method-named, and timestamped. Outputs live in a
# per-method folder (the namespace) under output/, with a sortable filename:
#     <UTC-timestamp>__<method>__<version>__<run-id>.ttl
# A matching line is appended to output/index.jsonl for search/retrieval.

@dataclass(frozen=True)
class RunMeta:
    method: str        # extraction method, e.g. "spacy"
    version: str       # method/script version, e.g. "v1.0.0"
    run_id: str        # unique short id for this run
    timestamp: str     # ISO-8601 UTC, e.g. "2026-06-12T19:15:00Z"
    source: str        # input filename
    triples: int       # number of triples extracted

    @property
    def stamp_basic(self) -> str:
        """Filesystem- and sort-safe timestamp: 20260612T191500Z."""
        return self.timestamp.replace("-", "").replace(":", "")

    @property
    def filename(self) -> str:
        return f"{self.stamp_basic}__{self.method}__{self.version}__{self.run_id}.ttl"


def new_run(method: str, version: str, source: str, triples: int) -> RunMeta:
    return RunMeta(
        method=method,
        version=version,
        run_id=uuid4().hex[:8],
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        source=source,
        triples=triples,
    )


def _header(meta: RunMeta) -> str:
    """Turtle comment block so the file self-describes its run identity."""
    return (
        f"# @run-id    {meta.run_id}\n"
        f"# @method    {meta.method}\n"
        f"# @version   {meta.version}\n"
        f"# @timestamp {meta.timestamp}\n"
        f"# @source    {meta.source}\n"
        f"# @triples   {meta.triples}\n\n"
    )


def write_run(turtle: str, meta: RunMeta) -> Path:
    """Write Turtle to output/<method>/<filename> and append to the manifest.
    Returns the path to the written .ttl file."""
    method_dir = OUTPUT_ROOT / meta.method
    method_dir.mkdir(parents=True, exist_ok=True)

    path = method_dir / meta.filename
    path.write_text(_header(meta) + turtle, encoding="utf-8")

    record = {**asdict(meta), "path": str(path.relative_to(OUTPUT_ROOT.parent))}
    with (OUTPUT_ROOT / "index.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    return path


def emit(method: str, version: str, source: str, triples, types=None) -> Path:
    """One call from a method script: serialize -> write -> index. Returns path."""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    triples = list(triples)
    turtle = to_turtle(triples, types)
    meta = new_run(method, version, source, len(triples))
    return write_run(turtle, meta)
