"""Triple extraction with spaCy (dependency-parse / rule-based) — worker module.

Approach: parse each sentence, then read subject-verb-object triples off the
dependency tree. Handles plain transitive verbs ("Mario loves coins") and
copular sentences ("Cheese is pink" / "Water is a liquid"). Questions and
imperatives (no subject) intentionally yield nothing.

No CLI here by design — argument parsing lives in the top-level `cli.py` wrapper.
Driven via:  python cli.py extract <textfile>
"""

from pathlib import Path

import spacy

from rdf_common import emit
from textload import load_text

METHOD = "spacy"
VERSION = "v1.2.0"  # v1.2.0: predicates use verbatim surface text, not lemmas
# v1.1.0: sibling RDF namespaces for clean qname rendering

# Dependency labels that mark the "object" half of a triple.
OBJECT_DEPS = {
    "dobj",   # direct object:        Mario loves [coins]
    "attr",   # copular noun:         Cheese is [a food]
    "acomp",  # adjectival complement: Water is [spicy]
    "pobj",   # prepositional object: kept via the preposition below
    "dative", # indirect object
    "oprd",   # object predicate
}


def subject_phrase(token):
    """Return the subtree text for a subject token (so 'the red car' stays whole)."""
    return " ".join(t.text for t in token.subtree)


def extract_triples(doc):
    triples = []
    for sent in doc.sents:
        # Skip questions — they ask, they don't assert.
        if sent.text.strip().endswith("?"):
            continue

        for token in sent:
            if token.pos_ not in ("VERB", "AUX"):
                continue
            subjects = [c for c in token.children if c.dep_ in ("nsubj", "nsubjpass")]
            if not subjects:
                continue  # no subject => imperative/fragment, skip

            for obj in token.children:
                if obj.dep_ in OBJECT_DEPS:
                    # Use the verbatim surface form, NOT token.lemma_: lemmatizing
                    # collapses "is"->"be", "loves"->"love" etc., which imposes an
                    # unwanted ontological normalization. Preserve the in-text relation.
                    predicate = token.text
                    obj_text = " ".join(t.text for t in obj.subtree)
                    for subj in subjects:
                        triples.append((subject_phrase(subj), predicate, obj_text))
                # prepositional phrases: "lives in Italy" -> (X, lives_in, Italy)
                elif obj.dep_ == "prep":
                    for pobj in obj.children:
                        if pobj.dep_ == "pobj":
                            predicate = f"{token.text}_{obj.text}"
                            obj_text = " ".join(t.text for t in pobj.subtree)
                            for subj in subjects:
                                triples.append((subject_phrase(subj), predicate, obj_text))
    return triples


def run_spacy(path: Path) -> Path:
    """Extract triples from a text file and emit a provenanced Turtle run.
    Returns the path to the written .ttl. Called by the cli.py `extract` command."""
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(load_text(path))
    triples = extract_triples(doc)
    return emit(METHOD, VERSION, path.name, triples)
