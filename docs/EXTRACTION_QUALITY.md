# De-noising & Shrinking Extracted Graphs — Methodology

A general, reusable methodology for turning a **noisy, oversized** extraction
(e.g. naive SVO triples over a real document) into a **clean, legible** knowledge
graph. Applies to any extraction method and any source — it surfaced while
processing `Commons2007IntroMHC.pdf`, where a 4,500-word paper yielded 334 mostly
unusable triples and a ~166″×228″ image. Use it whenever extraction "works"
mechanically but the graph isn't yet useful.

The two goals are independent and can be applied separately:

- **De-noise** — raise the *signal* of each triple (fewer junk nodes/edges).
- **Shrink** — reduce the *volume* shown (a legible view, not the whole wall).

---

## 1. De-noise — raise per-triple signal

In rough priority order (biggest payoff first):

- **Objects = head noun, not the whole subtree.** Taking a token's entire
  dependency subtree as the object text is fine for "Mario loves *coins*" but
  catastrophic on complex prose — whole clauses collapse into one mega-node
  (`a_task_of_order_two_operates_on_a_task_of_order_one...`). Take the **head
  noun** (or a bounded **noun chunk**) instead. *Single biggest win.*
- **Clean the source text before parsing.** Especially for PDF/OCR input:
  - **De-hyphenate** line-wrapped words (`System-\natic` → `Systematic`) — a
    line break must not split a token into two false entities.
  - **Strip non-content lines:** running headers/footers, page numbers, rule
    lines, figure/equation fragments, reference boilerplate.
  - **Remove control characters** (form-feed `\x0c`, etc.) — they also break
    downstream serializers (e.g. invalid XML in SVG). See `scripts/textload.py`.
  - Normalize whitespace and join sentences across page breaks.
- **Tighten predicate selection.** Require the head token to be a genuine
  content verb (`pos_ == "VERB"`), not a stray `AUX`, proper noun, or
  mid-sentence-capitalized fragment (`rel:System`, `rel:Follows`,
  `rel:phonemes`). Optionally restrict to lowercased surface forms — *without*
  lemmatizing (preserving the in-text relation is a separate rule, see
  `docs/DECISIONS.md`).
- **Filter degenerate triples.** Drop triples whose subject or object is empty,
  a single stop-word, pure punctuation/numerals, or absurdly long (e.g. object
  > N tokens — a sign a clause leaked in).
- **Deduplicate.** Collapse repeated `(s, p, o)` triples; optionally merge
  entities that differ only by case/whitespace/trivial morphology.

## 2. Shrink — show a legible subgraph

A correct graph with hundreds of nodes is still unreadable as one image. Reduce
*what is rendered*, not what is stored (keep the full `.ttl`; render a view):

- **Top-N by frequency / degree.** Rank entities by how often they appear (node
  degree) and render only the top N plus their immediate edges. The hubs are
  usually the document's real subject matter.
- **Per-section / per-page subgraphs.** Render one graph per source section or
  page instead of one giant canvas.
- **Ego graphs.** Pick a focus entity and render its k-hop neighborhood only.
- **Predicate / type filters.** Render only selected relations or entity types
  (e.g. just `rel:is` for an "is-a"/taxonomy view).
- **Prefer SVG over PNG** for large renders — vector scales and stays small;
  rasterizing a wall-sized canvas to PNG is slow and huge.

## 3. Order of operations

1. **Clean the source text** (§1) — everything downstream inherits its noise.
2. **Extract**, applying head-noun objects + predicate tightening (§1).
3. **Filter & dedupe** the triples (§1).
4. **Store the full graph** as a versioned `.ttl` run (see `docs/METHODOLOGY.md`).
5. **Render a shrunk view** (§2) for human consumption.

De-noising changes the emitted triples, so it is **version-affecting** — bump the
method `VERSION` (per `docs/METHODOLOGY.md` §2) when you apply §1 changes.
Shrinking is render-only and does **not** change the data or the version.

## 4. What *not* to do

- Don't lemmatize/normalize predicates to "clean" them — that imposes unwanted
  ontological commitments. Preserve the verbatim relation; normalize later as an
  explicit, opt-in step. See `docs/DECISIONS.md`.
- Don't delete the full graph to make it smaller — shrink the *view*, keep the
  artifact.
- Don't hand-edit a rendered image; fix the pipeline and re-render.
