"""
Tier 3 (Bonus) — Extension Sharing Graph
Computes which extensions share at least one instruction and renders
both a text-based adjacency representation and a DOT / Mermaid graph.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any


# ── Graph construction ────────────────────────────────────────────────────────

def build_sharing_graph(
    instr_dict: dict[str, Any],
) -> dict[tuple[str, str], list[str]]:
    """Return an edge dict keyed by (ext_a, ext_b) → [shared_instructions].

    Only instructions that appear in *more than one* extension create edges.
    Extension pairs are stored in sorted order so (a,b) == (b,a).
    """
    edges: dict[tuple[str, str], list[str]] = defaultdict(list)
    for instr, meta in instr_dict.items():
        exts = meta.get("extension", [])
        if isinstance(exts, str):
            exts = [exts]
        if len(exts) < 2:
            continue
        exts_sorted = sorted(exts)
        for i in range(len(exts_sorted)):
            for j in range(i + 1, len(exts_sorted)):
                key = (exts_sorted[i], exts_sorted[j])
                edges[key].append(instr)
    return dict(edges)


def build_adjacency(
    groups: dict[str, list[str]],
    instr_dict: dict[str, Any],
) -> dict[str, set[str]]:
    """Build a full adjacency set per extension node (all nodes, even isolated)."""
    adj: dict[str, set[str]] = {ext: set() for ext in groups}
    sharing = build_sharing_graph(instr_dict)
    for (a, b), instrs in sharing.items():
        if instrs:
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
    return adj


# ── Text-based graph ──────────────────────────────────────────────────────────

def print_text_graph(
    groups: dict[str, list[str]],
    instr_dict: dict[str, Any],
) -> None:
    """Print an ASCII adjacency list and a simple edge table."""
    sharing = build_sharing_graph(instr_dict)
    adj     = build_adjacency(groups, instr_dict)

    W = 72
    print("\n" + "=" * W)
    print("  Tier 3 — Extension Sharing Graph")
    print("=" * W)

    # ── Adjacency list ────────────────────────────────────────────────────────
    print("\n  [ Adjacency List: extensions connected by ≥1 shared instruction ]\n")
    if not any(adj.values()):
        print("  No shared instructions found — no edges in graph.")
    else:
        for ext in sorted(adj):
            neighbours = sorted(adj[ext])
            if neighbours:
                print(f"  {ext}")
                for nb in neighbours:
                    shared = sharing.get(tuple(sorted([ext, nb])), [])
                    instrs = ", ".join(i.upper() for i in sorted(shared))
                    print(f"    └─── {nb}  [{instrs}]")

    # ── Edge table ────────────────────────────────────────────────────────────
    print("\n  [ Shared-Instruction Edge Table ]\n")
    if not sharing:
        print("  (empty — no multi-extension instructions detected)")
    else:
        hdr = f"  {'Extension A':<20}  {'Extension B':<20}  {'Shared Instructions'}"
        sep = "  " + "-" * (len(hdr) - 2)
        print(hdr)
        print(sep)
        for (a, b), instrs in sorted(sharing.items()):
            ilist = ", ".join(i.upper() for i in sorted(instrs))
            print(f"  {a:<20}  {b:<20}  {ilist}")

    print()
    isolated = [ext for ext in groups if not adj.get(ext)]
    if isolated:
        print(f"  Isolated nodes (no shared instructions): {', '.join(sorted(isolated))}")
    print()


# ── DOT export ────────────────────────────────────────────────────────────────

def export_dot(
    groups: dict[str, list[str]],
    instr_dict: dict[str, Any],
    output_path: str = "output/extension_graph.dot",
) -> None:
    """Write a GraphViz DOT file of the sharing graph."""
    sharing = build_sharing_graph(instr_dict)
    adj     = build_adjacency(groups, instr_dict)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    lines = ["graph ExtensionSharingGraph {", '    rankdir=LR;', '    node [shape=box fontname="monospace"];']

    # Nodes
    for ext in sorted(groups):
        size = len(groups[ext])
        lines.append(f'    "{ext}" [label="{ext}\\n({size} instrs)"];')

    # Edges
    for (a, b), instrs in sorted(sharing.items()):
        label = "\\n".join(i.upper() for i in sorted(instrs))
        lines.append(f'    "{a}" -- "{b}" [label="{label}" fontsize=9];')

    lines.append("}")

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  [tier3] DOT graph written to: {output_path}")


# ── Mermaid export ────────────────────────────────────────────────────────────

def export_mermaid(
    groups: dict[str, list[str]],
    instr_dict: dict[str, Any],
    output_path: str = "output/extension_graph.mmd",
) -> None:
    """Write a Mermaid diagram of the sharing graph."""
    sharing = build_sharing_graph(instr_dict)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    lines = ["graph LR"]

    # Sanitise node IDs (Mermaid dislikes dots and slashes in bare ids)
    def mmd_id(name: str) -> str:
        return name.replace(".", "_").replace("/", "_").replace("-", "_")

    # All nodes
    for ext in sorted(groups):
        size  = len(groups[ext])
        nid   = mmd_id(ext)
        lines.append(f'    {nid}["{ext}<br/>{size} instrs"]')

    # Edges
    for (a, b), instrs in sorted(sharing.items()):
        label = ", ".join(i.upper() for i in sorted(instrs))
        lines.append(f'    {mmd_id(a)} -- "{label}" --> {mmd_id(b)}')

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  [tier3] Mermaid diagram written to: {output_path}")


# ── Public entry point ────────────────────────────────────────────────────────

def run(
    instr_dict: dict[str, Any],
    groups: dict[str, list[str]],
    output_dir: str = "output",
) -> None:
    """Execute Tier 3 graph analysis."""
    print_text_graph(groups, instr_dict)
    export_dot(groups, instr_dict,    f"{output_dir}/extension_graph.dot")
    export_mermaid(groups, instr_dict, f"{output_dir}/extension_graph.mmd")
