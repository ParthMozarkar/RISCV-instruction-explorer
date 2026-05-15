"""
Tier 2 — Cross-Reference with the RISC-V ISA Manual
Scans the AsciiDoc sources in riscv/riscv-isa-manual and cross-references
the extensions found there against those present in instr_dict.json.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any


# ── Known ISA-manual extension list (offline fallback) ───────────────────────
# Derived from the src/ directory of riscv/riscv-isa-manual as of early 2025.
# Used when the remote repo is unreachable, so the program is still useful.
OFFLINE_MANUAL_EXTENSIONS: list[str] = [
    # Base ISA
    "RV32I", "RV64I", "RV128I",
    # Standard extensions
    "M", "A", "F", "D", "Q", "C", "B",
    "E", "H", "J", "L", "N", "P", "T", "V", "X",
    # Z-extensions
    "Zifencei", "Zicsr", "Zicntr", "Zihpm", "Zicond",
    "Zihintpause", "Zihintntl",
    "Zba", "Zbb", "Zbc", "Zbs",
    "Zbkb", "Zbkc", "Zbkx",
    "Zknd", "Zkne", "Zknh", "Zksed", "Zksh",
    "Zkn", "Zks", "Zkt", "Zkr", "Zk",
    "Ztso",
    "Zfh", "Zfhmin",
    "Zfinx", "Zdinx", "Zhinx", "Zhinxmin",
    "Zcb", "Zca", "Zcf", "Zcd",
    "Zawrs", "Zacas",
    "Smstateen", "Ssstateen",
    "Sscofpmf", "Sstc", "Svnapot", "Svpbmt", "Svinval",
    "Hypervisor", "Smaia", "Ssaia",
]


# ── Remote repo scanning ──────────────────────────────────────────────────────

MANUAL_REPO_API = "https://api.github.com/repos/riscv/riscv-isa-manual/contents/src"
MANUAL_REPO_RAW  = "https://raw.githubusercontent.com/riscv/riscv-isa-manual/main/src"

# Pattern to capture extension-like tokens in AsciiDoc:
#   • Stand-alone capital letters (M, F, D, A, C …)
#   • Zxxx names (Zba, Zicsr, Zifencei …)
#   • Sxxx names (Smstateen, Ssaia …)
#   • RV32I / RV64I style base names
EXTENSION_RE = re.compile(
    r"\b(?:"
    r"RV(?:32|64|128)[A-Z]+|"   # RV32I, RV64GC …
    r"Z[a-z][a-z0-9]*|"         # Zba, Zicsr …
    r"S[ms][a-z][a-z0-9]*|"     # Smstateen, Ssaia …
    r"Hypervisor|"
    r"[IMAFDQCBEJLNPTVX]"       # Single capital letters
    r")\b"
)


def _github_api_get(url: str) -> Any:
    """Perform a GitHub API GET, respecting rate limits."""
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    with urllib.request.urlopen(req, timeout=20) as resp:
        import json
        return json.loads(resp.read())


def fetch_manual_extensions_remote() -> set[str] | None:
    """Try to fetch AsciiDoc files from the ISA manual repo and extract extension names.

    Returns ``None`` if the request fails (network unavailable or rate-limited).
    """
    print("[tier2] Querying riscv-isa-manual src/ via GitHub API …", file=sys.stderr)
    try:
        entries = _github_api_get(MANUAL_REPO_API)
    except Exception as exc:
        print(f"[tier2] GitHub API unavailable ({exc}).", file=sys.stderr)
        return None

    adoc_files = [e for e in entries if e.get("name", "").endswith(".adoc")]
    print(f"[tier2] Found {len(adoc_files)} .adoc file(s) in src/.", file=sys.stderr)

    found: set[str] = set()
    for f in adoc_files:
        raw_url = f"{MANUAL_REPO_RAW}/{f['name']}"
        try:
            with urllib.request.urlopen(raw_url, timeout=20) as resp:
                content = resp.read().decode(errors="replace")
            for m in EXTENSION_RE.finditer(content):
                found.add(m.group(0))
        except Exception:
            pass  # best-effort; skip files we can't reach

    print(f"[tier2] Extracted {len(found)} extension token(s) from the manual.", file=sys.stderr)
    return found


def get_manual_extensions() -> tuple[set[str], str]:
    """Return the set of extension names found in the ISA manual, plus a source label.

    Tries the remote repo first; falls back to the offline list.
    """
    remote = fetch_manual_extensions_remote()
    if remote is not None:
        return remote, "remote (riscv-isa-manual repo)"
    print("[tier2] Using offline extension list (network unavailable).", file=sys.stderr)
    return set(OFFLINE_MANUAL_EXTENSIONS), "offline fallback list"


# ── Normalisation ─────────────────────────────────────────────────────────────

def _normalize_json_ext(raw: str) -> str:
    """Normalise an instr_dict extension tag to a canonical short name.

    Examples:
        rv_zba    → zba
        rv64_zba  → zba
        rv32_zknh → zknh
        rv_i      → i
        rv64_i    → i
        rv_v      → v
    """
    # Strip leading "rv_", "rv32_", "rv64_", "rv128_"
    norm = re.sub(r"^rv(?:32|64|128)?_", "", raw.lower())
    return norm


def _normalize_manual_ext(raw: str) -> str:
    """Normalise an ISA-manual extension token to a canonical short name.

    Examples:
        Zba       → zba
        RV32I     → i        (base integer)
        RV64GC    → i        (treat as base)
        M         → m
        Hypervisor→ h
    """
    t = raw.strip()
    # RV32I / RV64I / RV128I → "i" (base)
    if re.match(r"RV(?:32|64|128)[A-Z]+", t):
        return "i"
    if t == "Hypervisor":
        return "h"
    return t.lower()


def build_json_canonical(groups: dict[str, list[str]]) -> dict[str, str]:
    """Return {canonical_name → original_tag} for all JSON extension tags."""
    result: dict[str, str] = {}
    for tag in groups:
        canon = _normalize_json_ext(tag)
        # If there's a collision prefer the simpler (shorter) original tag
        if canon not in result or len(tag) < len(result[canon]):
            result[canon] = tag
    return result


def build_manual_canonical(raw_names: set[str]) -> dict[str, str]:
    """Return {canonical_name → original_token} for all manual extension tokens."""
    result: dict[str, str] = {}
    for name in raw_names:
        canon = _normalize_manual_ext(name)
        if canon not in result or len(name) < len(result[canon]):
            result[canon] = name
    return result


# ── Cross-reference logic ─────────────────────────────────────────────────────

def cross_reference(
    groups: dict[str, list[str]],
    manual_extensions: set[str],
) -> dict[str, Any]:
    """Compare JSON extensions against ISA-manual extensions.

    Returns a results dict with keys:
        matched_json       – JSON tags that appear in the manual
        json_only          – JSON tags NOT in the manual
        manual_only        – manual tokens NOT in the JSON
        json_canonical     – canonical-name → original JSON tag
        manual_canonical   – canonical-name → original manual token
    """
    json_can   = build_json_canonical(groups)
    manual_can = build_manual_canonical(manual_extensions)

    json_keys   = set(json_can)
    manual_keys = set(manual_can)

    matched   = json_keys & manual_keys
    json_only = json_keys - manual_keys
    man_only  = manual_keys - json_keys

    return {
        "matched_json":     {c: json_can[c]   for c in sorted(matched)},
        "json_only":        {c: json_can[c]   for c in sorted(json_only)},
        "manual_only":      {c: manual_can[c] for c in sorted(man_only)},
        "json_canonical":   json_can,
        "manual_canonical": manual_can,
    }


# ── Display ───────────────────────────────────────────────────────────────────

def print_cross_reference_report(results: dict[str, Any], manual_source: str) -> None:
    matched   = results["matched_json"]
    json_only = results["json_only"]
    man_only  = results["manual_only"]

    W = 70
    print("\n" + "=" * W)
    print("  Tier 2 — Cross-Reference Report")
    print(f"  Manual source: {manual_source}")
    print("=" * W)

    # ── Matched ──────────────────────────────────────────────────────────────
    print(f"\n✅  MATCHED ({len(matched)}) — present in both instr_dict.json and the ISA manual:")
    if matched:
        for canon, json_tag in matched.items():
            print(f"    {json_tag:<22}  (canonical: {canon})")
    else:
        print("    (none)")

    # ── JSON-only ─────────────────────────────────────────────────────────────
    print(f"\n⚠️   JSON-ONLY ({len(json_only)}) — in instr_dict.json but NOT mentioned in the manual:")
    if json_only:
        for canon, json_tag in json_only.items():
            print(f"    {json_tag:<22}  (canonical: {canon})")
    else:
        print("    (none)")

    # ── Manual-only ──────────────────────────────────────────────────────────
    print(f"\n📖  MANUAL-ONLY ({len(man_only)}) — mentioned in manual but NOT in instr_dict.json:")
    if man_only:
        for canon, man_token in man_only.items():
            print(f"    {man_token:<22}  (canonical: {canon})")
    else:
        print("    (none)")

    # ── Summary ──────────────────────────────────────────────────────────────
    total = len(matched) + len(json_only) + len(man_only)
    print("\n" + "-" * W)
    print(f"  Summary: {len(matched)} matched, "
          f"{len(json_only)} in JSON only, "
          f"{len(man_only)} in manual only "
          f"(union = {total} unique canonical names)")
    print("-" * W)
    print()
    print("  NOTE: Normalisation maps  rv_zba / rv64_zba → 'zba',  Zba → 'zba'.")
    print("  Residual mismatches are genuine gaps between the two sources.")


# ── Public entry point ────────────────────────────────────────────────────────

def run(groups: dict[str, list[str]]) -> dict[str, Any]:
    """Execute Tier 2 analysis.

    Args:
        groups: extension → [instruction, …] mapping from Tier 1.

    Returns:
        Cross-reference results dict.
    """
    manual_extensions, source = get_manual_extensions()
    results = cross_reference(groups, manual_extensions)
    print_cross_reference_report(results, source)
    return results
