"""Visualize extracted RDF graphs with Raptor + Graphviz — worker module.

Pipeline:  output/<method>/<run>.ttl  --(rapper)-->  DOT  --(dot)-->  image

    rapper -i turtle -o dot <run>.ttl    # Raptor: Turtle -> Graphviz DOT
    dot -T<fmt>                           # Graphviz: DOT -> SVG/PNG

Images mirror the source run's filename under viz/<method>/, so a rendered graph
is trivially linked back to the exact run that produced it (same stem, different
folder + extension) — the image carries the same id/version/method/timestamp
provenance as the .ttl.

No CLI here by design — argument parsing lives in the top-level `cli.py` wrapper.
Driven via:  python cli.py visualize <selector>
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = ROOT / "output"
VIZ_ROOT = ROOT / "viz"
MANIFEST = OUTPUT_ROOT / "index.jsonl"


def require_tools():
    missing = [t for t in ("rapper", "dot") if shutil.which(t) is None]
    if missing:
        hint = {
            "rapper": "Raptor — install with: sudo apt-get install -y raptor2-utils",
            "dot": "Graphviz — install with: sudo apt-get install -y graphviz",
        }
        msg = "\n".join(f"  - {t} not found ({hint[t]})" for t in missing)
        sys.exit(f"Missing required tool(s):\n{msg}")


def load_manifest():
    if not MANIFEST.exists():
        return []
    with MANIFEST.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def method_of(ttl: Path) -> str:
    """Method is the 2nd field of '<ts>__<method>__<ver>__<id>.ttl', or the parent dir."""
    parts = ttl.stem.split("__")
    return parts[1] if len(parts) >= 2 else ttl.parent.name


def resolve_targets(arg: str, method_filter: str | None) -> list[Path]:
    records = load_manifest()

    if arg == "all":
        paths = [ROOT / r["path"] for r in records]
        if method_filter:
            paths = [p for p in paths if method_of(p) == method_filter]
        return paths

    if arg == "latest":
        recs = [r for r in records if not method_filter or r["method"] == method_filter]
        if not recs:
            sys.exit("No runs in the manifest yet — run an extraction first.")
        # filenames are timestamp-first, so sorting by path is chronological
        recs.sort(key=lambda r: r["path"])
        return [ROOT / recs[-1]["path"]]

    # a run-id?
    for r in records:
        if r["run_id"] == arg:
            return [ROOT / r["path"]]

    # otherwise treat as a path
    p = Path(arg)
    if p.exists():
        return [p]
    sys.exit(f"Could not resolve '{arg}' to a run-id, 'latest'/'all', or a file path.")


def render(ttl: Path, fmt: str) -> Path:
    dot = subprocess.run(
        ["rapper", "-i", "turtle", "-o", "dot", str(ttl)],
        check=True, capture_output=True, text=True,
    ).stdout

    out_dir = VIZ_ROOT / method_of(ttl)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ttl.stem}.{fmt}"

    subprocess.run(
        ["dot", f"-T{fmt}", "-o", str(out_path)],
        input=dot, text=True, check=True,
    )
    return out_path
