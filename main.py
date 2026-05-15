#!/usr/bin/env python3
"""
RISC-V Instruction Set Explorer
================================
Entry point for all three challenge tiers.

Usage:
    python main.py                        # run all tiers (auto-fetch or fallback)
    python main.py --instr-dict PATH      # use a local instr_dict.json
    python main.py --tier 1               # only run Tier 1
    python main.py --tier 1 --tier 2      # run Tier 1 and 2
    python main.py --output-dir DIR       # directory for graph output files
"""

import argparse
import sys
import time
from pathlib import Path

# Allow running from the project root without installing the package
sys.path.insert(0, str(Path(__file__).parent / "src"))

import tier1
import tier2
import tier3


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="RISC-V Instruction Set Explorer — RISC-V Mentorship Challenge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--instr-dict",
        metavar="PATH",
        default=None,
        help="Path to a local instr_dict.json (default: auto-fetch from GitHub).",
    )
    p.add_argument(
        "--tier",
        action="append",
        type=int,
        choices=[1, 2, 3],
        metavar="N",
        dest="tiers",
        help="Which tier(s) to run (default: all). Repeat for multiple: --tier 1 --tier 2.",
    )
    p.add_argument(
        "--output-dir",
        default="output",
        metavar="DIR",
        help="Directory for graph output files (default: output/).",
    )
    return p.parse_args()


def banner(text: str) -> None:
    line = "━" * 68
    print(f"\n{line}")
    print(f"  {text}")
    print(line)


def main() -> None:
    args   = parse_args()
    tiers  = sorted(set(args.tiers)) if args.tiers else [1, 2, 3]
    t_start = time.perf_counter()

    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║         RISC-V Instruction Set Explorer  ·  Mentorship 2025      ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    instr_dict: dict = {}
    groups:     dict = {}

    # ── Tier 1 ────────────────────────────────────────────────────────────────
    if 1 in tiers:
        banner("Tier 1 — Instruction Set Parsing")
        instr_dict, groups, multi = tier1.run(args.instr_dict)

    # ── Tier 2 ────────────────────────────────────────────────────────────────
    if 2 in tiers:
        banner("Tier 2 — Cross-Reference with the ISA Manual")
        if not groups:
            # Tier 1 wasn't run; load data now
            print("[main] Loading instruction data for Tier 2 …", flush=True)
            instr_dict, groups, _ = tier1.run(args.instr_dict)
        tier2.run(groups)

    # ── Tier 3 ────────────────────────────────────────────────────────────────
    if 3 in tiers:
        banner("Tier 3 (Bonus) — Extension Sharing Graph")
        if not groups:
            print("[main] Loading instruction data for Tier 3 …", flush=True)
            instr_dict, groups, _ = tier1.run(args.instr_dict)
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        tier3.run(instr_dict, groups, args.output_dir)

    elapsed = time.perf_counter() - t_start
    print(f"\n✔  Completed in {elapsed:.2f}s\n")


if __name__ == "__main__":
    main()
