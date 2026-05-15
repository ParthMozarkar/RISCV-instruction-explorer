"""
Tier 1 — Instruction Set Parsing
Reads instr_dict.json, groups instructions by extension, and prints a
summary table. Also identifies any instructions that span multiple extensions.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any


# ── Data loading ─────────────────────────────────────────────────────────────

INSTR_DICT_REMOTE = (
    "https://raw.githubusercontent.com/riscv/riscv-opcodes/master/instr_dict.json"
)
FALLBACK_PATHS = [
    Path("instr_dict.json"),
    Path("sample_instr_dict.json"),
    Path(__file__).parent.parent / "instr_dict.json",
    Path(__file__).parent.parent / "sample_instr_dict.json",
]


def load_instr_dict(path: str | None = None) -> dict[str, Any]:
    """Load instruction dictionary from a local file or the canonical remote URL.

    Resolution order:
    1. Explicit ``path`` argument (local file).
    2. ``RISCV_INSTR_DICT`` environment variable (local file path).
    3. Remote URL (requires network access).
    4. Fallback sample files shipped with this project.

    Returns the parsed JSON as a dict.
    """
    # 1. Explicit path
    if path:
        return _load_local(path)

    # 2. Environment variable
    env_path = os.environ.get("RISCV_INSTR_DICT")
    if env_path:
        return _load_local(env_path)

    # 3. Remote
    print(f"[tier1] Fetching instr_dict.json from {INSTR_DICT_REMOTE} …", file=sys.stderr)
    try:
        with urllib.request.urlopen(INSTR_DICT_REMOTE, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        print(f"[tier1] Fetched {len(data)} instructions.", file=sys.stderr)
        return data
    except Exception as exc:
        print(f"[tier1] Remote fetch failed ({exc}). Trying local fallbacks.", file=sys.stderr)

    # 4. Fallback sample files
    for fallback in FALLBACK_PATHS:
        if fallback.exists():
            print(f"[tier1] Using fallback: {fallback}", file=sys.stderr)
            return _load_local(str(fallback))

    raise FileNotFoundError(
        "Could not load instr_dict.json. Supply a local path via the "
        "--instr-dict flag or RISCV_INSTR_DICT env var."
    )


def _load_local(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    print(f"[tier1] Loaded {len(data)} instructions from {path}.", file=sys.stderr)
    return data


# ── Core analysis ─────────────────────────────────────────────────────────────

def group_by_extension(instr_dict: dict[str, Any]) -> dict[str, list[str]]:
    """Return {extension_tag: [instruction_name, …]} sorted by instruction count (desc)."""
    groups: dict[str, list[str]] = defaultdict(list)
    for instr_name, meta in instr_dict.items():
        extensions = meta.get("extension", [])
        if isinstance(extensions, str):
            extensions = [extensions]
        for ext in extensions:
            groups[ext].append(instr_name)
    # Sort each bucket alphabetically for determinism
    for ext in groups:
        groups[ext].sort()
    # Sort dict by count descending
    return dict(sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True))


def find_multi_extension_instructions(instr_dict: dict[str, Any]) -> dict[str, list[str]]:
    """Return {instruction_name: [ext1, ext2, …]} for instructions in >1 extension."""
    multi: dict[str, list[str]] = {}
    for instr_name, meta in instr_dict.items():
        extensions = meta.get("extension", [])
        if isinstance(extensions, str):
            extensions = [extensions]
        if len(extensions) > 1:
            multi[instr_name] = extensions
    return dict(sorted(multi.items()))


# ── Display helpers ───────────────────────────────────────────────────────────

def _col_widths(*cols: list[str]) -> list[int]:
    return [max(len(cell) for cell in col) for col in cols]


def print_summary_table(groups: dict[str, list[str]]) -> None:
    """Print a formatted summary table of extensions."""
    col_ext   = ["Extension"]      + list(groups.keys())
    col_count = ["# Instructions"] + [str(len(v)) for v in groups.values()]
    col_eg    = ["Example Mnemonic"] + [
        v[0].upper() if v else "—" for v in groups.values()
    ]

    w_ext, w_cnt, w_eg = _col_widths(col_ext, col_count, col_eg)
    sep = f"+-{'-' * w_ext}-+-{'-' * w_cnt}-+-{'-' * w_eg}-+"

    def row(a: str, b: str, c: str) -> str:
        return f"| {a:<{w_ext}} | {b:>{w_cnt}} | {c:<{w_eg}} |"

    print("\n" + "=" * len(sep))
    print("  RISC-V Extension Summary")
    print("=" * len(sep))
    print(sep)
    print(row(col_ext[0], col_count[0], col_eg[0]))
    print(sep.replace("-", "="))
    for ext, cnt, eg in zip(col_ext[1:], col_count[1:], col_eg[1:]):
        print(row(ext, cnt, eg))
    print(sep)
    print(f"\nTotal extensions : {len(groups)}")
    total_instrs = sum(len(v) for v in groups.values())
    print(f"Total entries    : {total_instrs} (instructions may be counted once per extension)")


def print_multi_extension_instructions(multi: dict[str, list[str]]) -> None:
    """Print instructions that appear in more than one extension."""
    print("\n" + "=" * 60)
    print("  Instructions belonging to multiple extensions")
    print("=" * 60)
    if not multi:
        print("  None found.")
        return
    for instr, exts in multi.items():
        print(f"  {instr.upper():<20} -> {', '.join(exts)}")
    print(f"\nTotal: {len(multi)} instruction(s) span multiple extensions.")


# ── Public entry point ────────────────────────────────────────────────────────

def run(path: str | None = None) -> tuple[dict[str, Any], dict[str, list[str]], dict[str, list[str]]]:
    """Execute Tier 1 analysis.

    Returns ``(instr_dict, extension_groups, multi_extension_instructions)``.
    """
    instr_dict = load_instr_dict(path)
    groups     = group_by_extension(instr_dict)
    multi      = find_multi_extension_instructions(instr_dict)

    print_summary_table(groups)
    print_multi_extension_instructions(multi)

    return instr_dict, groups, multi
