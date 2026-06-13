# Decision Records

Short, dated records of notable choices in this project. Newest first.

---

## 2026-06-12 — Thin CLI wrapper; arg-parsing separated from worker code

**Status:** Accepted

**Context.** As the project grew (extraction + visualization), we needed a
single entry point. The question was where argument-parsing should live.

**Decision.** A thin top-level **`cli.py`** is the only place with
`argparse`/argument logic. It dispatches to plain functions in the worker
modules under `scripts/`:

- `spacy_extract.run_spacy(path) -> Path`
- `visualize.render(ttl, fmt) -> Path`, `visualize.resolve_targets(...)`
- `rdf_common.emit(...)`

Worker modules contain **no** argument parsing and **no** `if __name__ ==
"__main__"` CLI block. They are importable, testable units; `cli.py` is the
presentation/dispatch layer.

**Why.** Keeps argument logic out of the files that do the work, avoids a
monolith, and makes the worker functions reusable and easy to test in isolation.

**Consequences.** The tool is driven via `python cli.py <command> ...` (e.g.
`extract`, `visualize`); direct `python scripts/<module>.py` invocation is no
longer the interface. Adding a new method/command means adding a worker function
plus a small subparser in `cli.py`.

---

## 2026-06-12 — Drop the SciPhi/Triplex (LLM) approach; spaCy only

**Status:** Accepted

**Context.** We evaluated two triple-extraction approaches against
`TxtData/SmallHandwritten.txt`:

1. **spaCy** — dependency-parse, rule-based extraction. CPU-only, ~12 MB model.
2. **SciPhi/Triplex** — a ~3.8 B Phi-3-mini fine-tune (HuggingFace), schema-guided.

Both were wired through the same RDFLib layer so their Turtle output is
comparable.

**What we found.**

- **spaCy worked immediately and correctly.** On the test text it produced the 3
  valid triples and correctly ignored the 2 questions and the 1 imperative
  ("Stop immediately!") — the deliberate traps in the input. Fast, lightweight,
  fully local.
- **Triplex was not viable on this hardware.** The machine's GPU is an AMD
  **Radeon R9 380X** ("Tonga", ISA `gfx803`), which modern ROCm and the
  PyTorch ROCm wheels do **not** support (they target `gfx900`/Vega and newer).
  So Triplex could only run on CPU.
- On CPU it required a **7.6 GB** weight download, and then failed to run at all:
  the model ships custom `modeling_phi3.py` (loaded via `trust_remote_code`) that
  targets an older `transformers` and breaks on the current cache API
  (`AttributeError: 'DynamicCache' object has no attribute 'seen_tokens'`). A
  native-Phi3 workaround was possible but added more fragility for no clear gain
  on a text this simple.

**Decision.** Use **spaCy** as the extraction method for this proof of concept.
Remove the Triplex script, its downloaded weights, and the heavy Python deps
(`torch`, `transformers`, `accelerate`, `einops`).

**Why this is the right call for now.**

- Runs on **this** device, and on others that can't run a multi-GB local LLM.
- Fast and lightweight — good fit for a proof of concept and for iteration.
- Correct on the test input, including the non-statement traps.

**Trade-offs we accept.** spaCy only extracts what its grammar rules cover,
predicates are raw verb lemmas (`be`, `love`) rather than a normalized schema,
and entities are untyped (no `rdf:type`). If richer, schema-typed extraction is
needed later, the preferred path is a **hosted LLM API** (no local GPU/ROCm
dependency) plugged into the same `emit()` convention — not local weights on this
machine.

**Consequences / follow-ups.**

- `scripts/triplex_extract.py` removed; HF model cache deleted (~7.2 GB freed).
- `requirements.txt` trimmed to `rdflib` + `spacy`.
- The output convention (`docs/METHODOLOGY.md`) is method-agnostic, so adding a
  future method later requires no change to the storage scheme.
