# Decision Records

Short, dated records of notable choices in this project. Newest first.

---

## 2026-06-12 — NonBijectiveText stress test: negation, passive, comments, entity identity

**Status:** Accepted (spaCy method v1.3.0)

**Context.** `TxtData/NonBijectiveText.txt` deliberately maps **many surface forms
to the same underlying relation/entity** ("non-bijective"), and adds negations,
`#`-comments, assembly code, and symbol garbage. Run through the v1.2.0
extractor, it exposed four issues: (1) negation was **silently inverted** — "Cheese
is **not** metal" became `Cheese — is → metal`; (2) passive restatements
("Coins get collected by mario") produced **no triple**; (3) `#`-comments and
garbage became facts; (4) case/synonym variants (`Mario`/`mario`,
`adores`/`loves`) would never merge.

**Decisions (the user's calls).**

1. **Negation — handle first.** Implemented: a `neg` dependency marks the
   predicate with a **`not_` prefix** (`rel:not_is`). We *preserve* the negation
   as a first-class relation rather than drop the triple or assert its opposite.
   Predicate is otherwise verbatim (no lemmatizing).
2. **Comment / code / symbol stripping — deliberately NOT done.** Downstream
   applications may treat `#`-comments, assembly (`INT 80H`), and symbol tokens
   as **separate meaningful constructs**, so the loader/extractor keeps them.
   They surface as ordinary (often noisy) triples — intentional, not a bug.
3. **Passive voice — normalize.** Implemented: `X gets V-ed by Y` →
   `(Y, V, X)` via `nsubjpass` + the `by`-agent, restoring active direction so a
   passive restatement lands on the same edge as its active form. The verb stays
   verbatim (`collected`, not `collect`).
4. **Entity & synonym canonicalization — the ontologist's job, not the parser's.**
   The core "non-bijective" merge (`Mario` ≡ `mario`; `adores` ≈ `loves`) is
   **not automated**. It requires schema design, relation/term choices, and human
   judgment — substantially **manual ontology modeling**, not dependency parsing.
   The extractor stays faithful (distinct surface forms → distinct nodes); any
   merging is a separate, explicit, human-driven step. We may experiment later,
   but expect it to remain ontologist-led.

**Why.** Negation and passive are *correctness/direction* fixes with no
ontological baggage. Keeping comments/code and not merging entities are both about
**not imposing commitments the project hasn't made** — consistent with the
verbatim-predicate rule above.

**Consequences.** spaCy method bumped to **v1.3.0**. Known remaining limitations
(out of scope, see `docs/EXTRACTION_QUALITY.md`): full-subtree objects still form
run-on mega-nodes; missing sentence punctuation causes segmentation errors (e.g.
"Luigi adores Mario" merged with the next line, so `adores` was dropped).

---

## 2026-06-12 — RAG over the RDF: hybrid retrieval, rdflib-endpoint, Claude API

**Status:** Accepted

**Context.** Goal: make the extracted RDF queryable by an LLM for
retrieval-augmented generation, with a SPARQL endpoint.

**Decisions.**

- **Hybrid retrieval** — combine semantic vector search (find entry-point
  entities) with **SPARQL** graph expansion (pull their neighborhoods). The user
  chose "both" over pure text-to-SPARQL or pure vector RAG.
- **SPARQL endpoint: `rdflib-endpoint`** — serves the existing rdflib graph
  (loaded from `output/spacy/*.ttl`) as a SPARQL 1.1 HTTP endpoint via FastAPI.
  Pure Python, CPU-only, right-sized for hundreds of triples. (Oxigraph reserved
  for if/when we outgrow rdflib.)
- **Generation: Claude API, `claude-opus-4-8`** — hosted, no local GPU; keeps
  with the "hosted LLM API, not local weights" decision above. Uses the
  `anthropic` SDK with tool use (a `sparql_query` tool) and adaptive thinking.
- **Embeddings: `fastembed` (ONNX), not `sentence-transformers`.** The vector
  side needs an embedding model, but `sentence-transformers` pulls in **torch** —
  the exact heavy dependency we removed (see the Triplex decision above).
  `fastembed` runs small quantized models on **onnxruntime** (CPU, no torch),
  preserving the lightweight footprint. Anthropic has no embeddings endpoint, so
  a local embedder is required regardless; `fastembed` is the light one.

**Why.** Hybrid gives both semantic recall and exact graph structure; the stack
stays CPU-only and torch-free; generation reuses the already-chosen Claude API.

**Generation is optional and gated.** The user cannot obtain a paid API key
right now (financial). So **retrieval runs fully free/local** (SPARQL endpoint +
`fastembed` embeddings, CPU/ONNX, no key); only the final Claude generation step
needs `ANTHROPIC_API_KEY`. Without a key, the `ask` command returns the assembled
retrieval context (the prompt that *would* go to the LLM) — a useful free
fallback, and the same command yields prose once a key exists. No hard dependency
on the paid API. See the `no-paid-apis-now` memory.

**Consequences.** New deps: `rdflib-endpoint`, `fastembed`, `anthropic` (+
`numpy` for in-memory cosine search at this scale — no separate vector DB yet).
`anthropic` is imported lazily so the toolchain runs without a key. Worker
modules stay parser-free; the RAG/endpoint commands are dispatched from `cli.py`
(see the CLI-wrapper decision above).

---

## 2026-06-12 — Predicates use verbatim in-text relation, not spaCy lemmas

**Status:** Accepted (spaCy method v1.2.0)

**Context.** The spaCy extractor originally built predicates from `token.lemma_`.
spaCy's lemmatizer maps copulas and inflections onto a shared base form —
notably `is`/`are`/`was` → `be`, and `loves` → `love`. So "Cheese is pink"
became `rel:be`.

**Problem.** Lemmatization silently imposes an ontological normalization we did
not choose. Collapsing surface forms to a lemma is a modeling commitment
(especially around copulas and top-level/upper-ontology behavior) that doesn't
belong in a faithful extraction step. The graph should record the relation **as
written**, leaving any normalization to a later, explicit step.

**Decision.** Build predicates from `token.text` (the verbatim surface form), not
`token.lemma_`. "Cheese is pink" → `rel:is`; "Mario loves coins" → `rel:loves`.
No mapping of any kind is applied to the relation.

**Consequences.** Predicate IRIs now reflect exact in-text wording
(`rel:is`, `rel:loves`). Output changed, so the spaCy method version was bumped
to **v1.2.0**. If normalized/canonical predicates are ever wanted, that should be
a separate, opt-in transform over the faithful triples — never baked into
extraction.

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

**Trade-offs we accept.** spaCy only extracts what its grammar rules cover, and
entities are untyped (no `rdf:type`). (Predicates use the verbatim surface text,
not lemmas — see the 2026-06-12 predicate-text decision above.) If richer,
schema-typed extraction is
needed later, the preferred path is a **hosted LLM API** (no local GPU/ROCm
dependency) plugged into the same `emit()` convention — not local weights on this
machine.

**Consequences / follow-ups.**

- `scripts/triplex_extract.py` removed; HF model cache deleted (~7.2 GB freed).
- `requirements.txt` trimmed to `rdflib` + `spacy`.
- The output convention (`docs/METHODOLOGY.md`) is method-agnostic, so adding a
  future method later requires no change to the storage scheme.
