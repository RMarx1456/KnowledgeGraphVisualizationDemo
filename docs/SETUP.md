# Setup

How to set up this tool from a fresh checkout. Everything runs on **CPU** — no
GPU is required or used (see `docs/DECISIONS.md` for why).

## 1. Prerequisites

- **Python 3.10+** with `venv` (`sudo apt-get install -y python3-venv` if missing)
- **System tools for visualization:**
  - **Raptor** — `rapper`, converts Turtle → Graphviz DOT
  - **Graphviz** — `dot`, renders DOT → SVG/PNG

```bash
sudo apt-get update
sudo apt-get install -y raptor2-utils graphviz
```

Verify:

```bash
rapper --version   # e.g. 2.0.16
dot -V             # e.g. dot - graphviz version 2.43.0
```

> Visualization is optional. If you only need the RDF (`cli.py extract` without
> `--image`), you can skip Raptor/Graphviz.

## 2. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt        # rdflib + spacy
python -m spacy download en_core_web_sm # ~12 MB English model
```

This installs only lightweight, CPU-only packages. The venv ends up around
~470 MB (mostly spaCy + its model).

## 3. Verify the install

```bash
# Extract triples from the sample text -> a provenanced Turtle run
python cli.py extract TxtData/SmallHandwritten.txt

# Same, and also render a graph image (needs Raptor + Graphviz)
python cli.py extract TxtData/SmallHandwritten.txt --image
```

Expected: a `.ttl` under `output/spacy/` (and, with `--image`, a matching image
under `viz/spacy/`). See `docs/METHODOLOGY.md` for the naming convention and
`README.md` for the full command reference.

## 4. Layout after setup

```
cli.py                 # wrapper runner (all argument parsing lives here)
scripts/
  spacy_extract.py     # worker: spaCy extraction
  visualize.py         # worker: Raptor + Graphviz rendering
  rdf_common.py        # worker: RDF/Turtle + run naming + manifest
TxtData/               # input text
output/<method>/*.ttl  # extracted runs (tracked) + index.jsonl manifest
viz/<method>/*         # rendered images (git-ignored; regenerable)
docs/                  # METHODOLOGY, DECISIONS, SETUP (this file)
.venv/                 # virtualenv (git-ignored)
```

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `Missing required tool(s): rapper ...` | `sudo apt-get install -y raptor2-utils` |
| `Missing required tool(s): dot ...` | `sudo apt-get install -y graphviz` |
| `Can't find model 'en_core_web_sm'` | `python -m spacy download en_core_web_sm` (venv active) |
| `ModuleNotFoundError: spacy/rdflib` | activate the venv, then `pip install -r requirements.txt` |

## 6. Recreating from scratch

The `.venv/` and `viz/` directories are git-ignored and fully regenerable:

```bash
rm -rf .venv
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && python -m spacy download en_core_web_sm
# re-render any images you want:
python cli.py visualize all
```
