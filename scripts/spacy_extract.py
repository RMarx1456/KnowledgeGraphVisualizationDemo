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
VERSION = "v1.3.0"  # v1.3.0: negation marked (not_ prefix) + passive voice normalized
# v1.2.0: predicates use verbatim surface text, not lemmas
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
    """Return the subtree text for a token (so 'the red car' stays whole)."""
    return " ".join(t.text for t in token.subtree)


def _negation(token) -> str:
    """A 'not_' prefix when the verb is negated ('is not', 'does not love').
    We mark negation as a distinct predicate rather than drop the triple, so the
    graph records 'A brother is NOT a plant' instead of silently asserting the
    opposite. Predicate stays verbatim otherwise (no lemmatizing)."""
    return "not_" if any(c.dep_ == "neg" for c in token.children) else ""


def _agent(token):
    """The 'by'-agent of a passive clause: the pobj under an `agent`/`by` child."""
    for c in token.children:
        if c.dep_ == "agent" or (c.dep_ == "prep" and c.text.lower() == "by"):
            for gc in c.children:
                if gc.dep_ == "pobj":
                    return gc
    return None


def extract_triples(doc):
    triples = []
    for sent in doc.sents:
        # Skip questions — they ask, they don't assert.
        if sent.text.strip().endswith("?"):
            continue

        for token in sent:
            if token.pos_ not in ("VERB", "AUX"):
                continue

            neg = _negation(token)
            active_subjects = [c for c in token.children if c.dep_ == "nsubj"]
            passive_patients = [c for c in token.children if c.dep_ == "nsubjpass"]

            # Passive: "Coins get collected by Mario" -> (Mario, collected, Coins).
            # Restores active direction so passive restatements land on the same edge
            # as their active form. Verb stays verbatim ('collected', not 'collect').
            agent = _agent(token)
            if passive_patients and agent is not None:
                predicate = neg + token.text
                for patient in passive_patients:
                    triples.append((subject_phrase(agent), predicate, subject_phrase(patient)))

            if not active_subjects:
                continue

            for obj in token.children:
                if obj.dep_ in OBJECT_DEPS:
                    # Verbatim surface form, NOT token.lemma_ (lemmatizing collapses
                    # "is"->"be", "loves"->"love" — an unwanted ontological choice).
                    predicate = neg + token.text
                    obj_text = " ".join(t.text for t in obj.subtree)
                    for subj in active_subjects:
                        triples.append((subject_phrase(subj), predicate, obj_text))
                # prepositional phrases: "lives in Italy" -> (X, lives_in, Italy).
                # 'by' is handled as the passive agent above, so skip it here.
                elif obj.dep_ == "prep" and obj.text.lower() != "by":
                    for pobj in obj.children:
                        if pobj.dep_ == "pobj":
                            predicate = neg + f"{token.text}_{obj.text}"
                            obj_text = " ".join(t.text for t in pobj.subtree)
                            for subj in active_subjects:
                                triples.append((subject_phrase(subj), predicate, obj_text))
    return triples


def run_spacy(path: Path) -> Path:
    """Extract triples from a text file and emit a provenanced Turtle run.
    Returns the path to the written .ttl. Called by the cli.py `extract` command."""
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(load_text(path))
    triples = extract_triples(doc)
    return emit(METHOD, VERSION, path.name, triples)
