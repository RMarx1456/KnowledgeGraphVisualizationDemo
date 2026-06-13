# Knowledge Graph Visualization Demo — Triple Extraction

Extract `(subject, predicate, object)` triples from text and emit them as
**terse Turtle** via a shared RDFLib layer (`scripts/rdf_common.py`). Each run is
ID'd, versioned, method-named, and timestamped — see
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) for the output convention.

The current (and only) method is **spaCy**. An LLM approach (SciPhi/Triplex) was
evaluated and dropped; see [`docs/DECISIONS.md`](docs/DECISIONS.md) for why.
Visualization of the Turtle is planned but not yet built.

The test text is deliberately small: 3 plain statements plus 2 questions and 1
command — so it doubles as a check on whether an approach hallucinates triples
from non-statements.

```
Mario loves coins.
Cheese is pink.
Water is spicy.

What is a flashdrive?
How do I make lemonade?
Stop immediately!
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
sudo apt-get install -y raptor2-utils graphviz   # for visualization
```

No GPU, no model download beyond the ~12 MB `en_core_web_sm` — runs on any CPU.
Full, step-by-step instructions and troubleshooting: [`docs/SETUP.md`](docs/SETUP.md).

## Usage

The tool is driven by a single wrapper, **`cli.py`**, which parses arguments and
dispatches to the worker modules in `scripts/` (arg-parsing is kept out of the
worker code — see [`docs/DECISIONS.md`](docs/DECISIONS.md)).

```bash
# extract triples from a text file -> a provenanced Turtle run
python cli.py extract TxtData/SmallHandwritten.txt

# ...and also render the graph image (off by default to save space)
python cli.py extract TxtData/SmallHandwritten.txt --image
python cli.py extract TxtData/SmallHandwritten.txt --image --format png
```

With `--image`, the picture is written with the **same filename/provenance** as
its `.ttl` (same timestamp, method, version, and run-id).

## Method — spaCy (dependency-parse / rule-based)

`scripts/spacy_extract.py` parses each sentence and reads triples off the
dependency tree (subject → verb → object/complement). Lightweight, instant,
fully local. Turtle output (written under `output/spacy/`):

```turtle
ex:Cheese rdfs:label "Cheese" ;
    rel:be ex:pink .
ex:Mario rdfs:label "Mario" ;
    rel:love ex:coins .
ex:Water rdfs:label "Water" ;
    rel:be ex:spicy .
```

Questions and the imperative are correctly skipped. Trade-off: it only finds
what the grammar rules cover, predicates come out as raw lemmas (`be`, `love`)
rather than a normalized schema, and entities are untyped (no `rdf:type`).

## Output convention (summary)

Each run lands in a per-method folder with a sortable, self-describing filename:

```
output/
├── index.jsonl                                          # append-only manifest
└── spacy/
    └── 20260612T191500Z__spacy__v1.0.0__0f240588.ttl   # <ts>__<method>__<ver>__<id>
```

Full spec, manifest schema, and example `jq` queries:
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Visualization (Raptor + Graphviz)

Besides `extract --image`, you can render an **existing** run at any time.
**Raptor** (`rapper`) converts Turtle → Graphviz DOT, then **Graphviz** (`dot`)
renders it. Images mirror the source run's filename under `viz/<method>/`, so
each graph links straight back to the run that produced it.

```bash
python cli.py visualize                       # latest run -> SVG
python cli.py visualize latest --method spacy --format png
python cli.py visualize all                   # every run in the manifest
python cli.py visualize <run-id>              # a specific run
python cli.py visualize path/to/run.ttl       # a specific file
```

Resources render as blue ellipses, literals as boxes, predicates as edge labels
(`rel:be`, `rel:love`). `viz/` is regenerable from the `.ttl` files, so it's
git-ignored. See [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) §9 for details.

## Why not a local LLM?

Briefly: this box's AMD **Radeon R9 380X** (`gfx803`) isn't supported by modern
ROCm/PyTorch, so SciPhi/Triplex could only run on CPU after a 7.6 GB download,
and its bundled model code is incompatible with current `transformers`. spaCy is
faster, lighter, and runs on this hardware (and on machines that can't run the
LLM at all). Full rationale: [`docs/DECISIONS.md`](docs/DECISIONS.md).
