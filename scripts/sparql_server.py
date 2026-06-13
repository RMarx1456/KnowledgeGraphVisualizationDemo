"""SPARQL 1.1 HTTP endpoint over the extracted RDF, via rdflib-endpoint — worker module.

Serves the latest-run graph (from graphstore) as a queryable SPARQL endpoint with
a built-in web UI. Free, local, CPU-only — no API key. Run it through cli.py:

    python cli.py serve            # http://localhost:8000  (UI + /sparql)

No CLI/argparse here — cli.py owns host/port arguments and the uvicorn call.
"""

import graphstore

EXAMPLE_QUERY = """PREFIX ex: <http://example.org/kg/entity/>
PREFIX rel: <http://example.org/kg/relation/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 50"""


def build_app(graph=None):
    """Return an ASGI app exposing the graph as a SPARQL endpoint."""
    from rdflib_endpoint import SparqlEndpoint  # lazy: keeps import cost off other commands

    graph = graph if graph is not None else graphstore.load_graph()
    return SparqlEndpoint(
        graph=graph,
        title="Knowledge Graph SPARQL endpoint",
        description="SPARQL 1.1 over spaCy-extracted RDF triples.",
        version="1.0.0",
        example_query=EXAMPLE_QUERY,
        enable_update=False,
    )
