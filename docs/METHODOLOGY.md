# Triple-Extraction Output Methodology

How extraction runs are produced, named, and stored in this project. This is the
contract every extraction method must follow so that outputs are **ID'd,
versioned, method-named, and timestamped** — and therefore easily retrievable,
searchable, and sortable. Visualization is built *on top of* these artifacts and
is intentionally out of scope here.

## 1. Pipeline

Every method follows the same path:

```
text  ──►  method-specific extraction  ──►  (subject, predicate, object) [+ types]
      ──►  rdf_common.build_graph / to_turtle  ──►  terse Turtle
      ──►  rdf_common.emit  ──►  output/<method>/<filename>.ttl  +  output/index.jsonl
```

All methods share `scripts/rdf_common.py`, so the RDF shape is identical and
cross-method comparison is apples-to-apples. A method script only has to produce
triples (and optional entity types) and call `emit(...)`.

## 2. The four required attributes

| Attribute   | Where it lives                                  | Example                       |
|-------------|-------------------------------------------------|-------------------------------|
| **ID**      | filename + header + manifest                    | `0f240588` (8-hex, unique/run)|
| **Version** | filename + header + manifest (`VERSION` const)  | `v1.0.0`                       |
| **Method**  | folder name + filename + header + manifest      | `spacy`, `triplex`             |
| **Timestamp** | filename + header + manifest (UTC)            | `2026-06-12T19:15:00Z`         |

The redundancy is deliberate: you can recover a run's identity from the path
alone, from the file's own header, or from the manifest — whichever is at hand.

## 3. Folder layout (method = namespace)

```
output/
├── index.jsonl                # append-only manifest, one JSON object per run
└── spacy/                     # one folder per method (the "namespace")
    ├── 20260612T191500Z__spacy__v1.0.0__0f240588.ttl
    └── 20260612T193002Z__spacy__v1.0.0__a1b2c3d4.ttl
```

`spacy` is the only method today; any future method gets its own sibling folder
under `output/` automatically (`emit()` creates it). See `docs/DECISIONS.md` for
why the project is spaCy-only for now.

## 4. Filename grammar

```
<timestamp>__<method>__<version>__<run-id>.ttl
20260612T191500Z__spacy__v1.0.0__0f240588.ttl
```

- **Separator** is `__` (double underscore); fields never contain it.
- **`<timestamp>`** — ISO-8601 UTC in *basic* form (`YYYYMMDDThhmmssZ`), no
  colons or dashes so it is filesystem-safe. Placed **first** so a plain
  lexicographic sort (`ls`, file managers) is also chronological.
- **`<method>`** — lowercase method id; matches the parent folder.
- **`<version>`** — method/script version, `v` + semver. Bump when the
  extraction logic or RDF mapping changes in a way that affects output.
- **`<run-id>`** — first 8 hex chars of a UUID4; disambiguates runs that share a
  timestamp and gives every artifact a stable handle.

## 5. Self-describing Turtle header

Each `.ttl` begins with a comment block repeating the run identity, so the file
stands alone even if moved or renamed:

```turtle
# @run-id    0f240588
# @method    spacy
# @version   v1.0.0
# @timestamp 2026-06-12T19:15:00Z
# @source    SmallHandwritten.txt
# @triples   3
```

`#` lines are Turtle comments and are ignored by RDF parsers / RDFLib.

## 6. Manifest: `output/index.jsonl`

One JSON object per run, appended (never rewritten). JSON Lines so it is
greppable, `jq`-able, and sortable with standard tools:

```json
{"method":"spacy","version":"v1.0.0","run_id":"0f240588","timestamp":"2026-06-12T19:15:00Z","source":"SmallHandwritten.txt","triples":3,"path":"output/spacy/20260612T191500Z__spacy__v1.0.0__0f240588.ttl"}
```

### Common queries

```bash
# every spaCy run, newest last (sorted by the timestamp-first filename)
ls output/spacy/

# all runs of one method, newest first
jq -c 'select(.method=="spacy")' output/index.jsonl | sort -r

# find a run by id and print its file path
jq -r 'select(.run_id=="0f240588") | .path' output/index.jsonl

# runs that produced zero triples (regressions to inspect)
jq -c 'select(.triples==0)' output/index.jsonl
```

## 7. Adding a new method

1. Write a worker module `scripts/<method>_extract.py` exposing a function (e.g.
   `run_<method>(path) -> Path`) that produces `(s, p, o)` triples and, if
   available, a `{label: TYPE}` map. **No argument parsing in the module** — that
   belongs in `cli.py` (see `docs/DECISIONS.md`).
2. Define `METHOD = "<method>"` and `VERSION = "vX.Y.Z"`.
3. Call `emit(METHOD, VERSION, source_name, triples, types)` — naming, headers,
   folders, and the manifest are handled for you.
4. Wire it into the wrapper: import the function in `cli.py` and add a subparser
   (or extend `extract`) that dispatches to it. Visualization needs no changes —
   `cli.py visualize` already works for any method's `.ttl`.

## 8. RDF namespaces

| Prefix | IRI                                   | Used for                          |
|--------|---------------------------------------|-----------------------------------|
| `ex:`  | `http://example.org/kg/entity/`       | entities (subjects / objects)     |
| `rel:` | `http://example.org/kg/relation/`     | predicates                        |
| `kg:`  | `http://example.org/kg/class/`        | entity types via `rdf:type` (unused by spaCy; for typed methods) |

The three are deliberately **siblings** — no IRI is a string-prefix of another —
so qname-based tools (e.g. Raptor's `rapper`) render `rel:be` rather than
`ex:rel/be`. Entity/predicate text is slugified into local names; the original
string is kept on each entity as `rdfs:label`.

## 9. Visualization

Rendering is a separate stage built on top of the `.ttl` artifacts (run any time,
nothing to re-extract): **Raptor** converts Turtle to Graphviz DOT, then
**Graphviz** renders an image.

```
output/<method>/<run>.ttl  --(rapper)-->  DOT  --(dot)-->  viz/<method>/<run>.<fmt>
```

The `scripts/visualize.py` worker writes the image to `viz/<method>/` using the
**same filename stem** as the source run (different folder + extension), so every
image is trivially linked back to the exact run — keeping the
ID/version/method/timestamp identity intact. It is driven through `cli.py`:

```bash
# render as part of extraction (image shares the new run's provenance)
python cli.py extract <textfile> --image [--format png]

# render an existing run
python cli.py visualize                       # latest run (svg)
python cli.py visualize latest --method spacy # latest run of a method
python cli.py visualize all                   # every run in the manifest
python cli.py visualize <run-id>              # a specific run by id
python cli.py visualize path/to/run.ttl       # a specific file
python cli.py visualize latest --format png
```

Requires `rapper` (`sudo apt-get install -y raptor2-utils`) and `dot`
(`sudo apt-get install -y graphviz`). `viz/` is regenerable from the `.ttl`
files and is git-ignored.

## 10. See also

- `docs/EXTRACTION_QUALITY.md` — methodology for **de-noising** (raising
  per-triple signal) and **shrinking** (rendering a legible subgraph) when an
  extraction is noisy or too large to view.
- `docs/DECISIONS.md` — why spaCy over an LLM, verbatim predicates, the thin
  CLI wrapper, and the RAG architecture.
