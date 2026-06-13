"""Triple extraction with spaCy (dependency-parse / rule-based).

Approach: parse each sentence, then read subject-verb-object triples off the
dependency tree. Handles plain transitive verbs ("Mario loves coins") and
copular sentences ("Cheese is pink" / "Water is a liquid"). Questions and
imperatives (no subject) intentionally yield nothing.

Usage:
    python scripts/spacy_extract.py [path/to/text.txt]
"""

import sys
from pathlib import Path

import spacy

from rdf_common import emit

DEFAULT_TEXT = Path(__file__).resolve().parent.parent / "TxtData" / "SmallHandwritten.txt"
METHOD = "spacy"
VERSION = "v1.1.0"  # v1.1.0: sibling RDF namespaces for clean qname rendering

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
                    predicate = token.lemma_
                    obj_text = " ".join(t.text for t in obj.subtree)
                    for subj in subjects:
                        triples.append((subject_phrase(subj), predicate, obj_text))
                # prepositional phrases: "lives in Italy" -> (X, live_in, Italy)
                elif obj.dep_ == "prep":
                    for pobj in obj.children:
                        if pobj.dep_ == "pobj":
                            predicate = f"{token.lemma_}_{obj.text}"
                            obj_text = " ".join(t.text for t in pobj.subtree)
                            for subj in subjects:
                                triples.append((subject_phrase(subj), predicate, obj_text))
    return triples


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TEXT
    text = path.read_text(encoding="utf-8")

    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text)

    triples = extract_triples(doc)
    out = emit(METHOD, VERSION, path.name, triples)

    print(f"# spaCy: {len(triples)} triple(s) from {path.name} -> {out}\n")
    print(out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
