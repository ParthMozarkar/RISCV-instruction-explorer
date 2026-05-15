"""
Unit tests for the RISC-V Instruction Set Explorer.
Run with:  python -m pytest tests/ -v
       or: python -m unittest discover tests/
"""

import sys
import os
import json
import tempfile
import unittest
from pathlib import Path

# Ensure src/ is on the path when running from the project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import tier1
import tier2
import tier3


# ────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────

MINIMAL_DICT = {
    "add":      {"extension": ["rv_i"],        "mask": "0xfe00707f", "match": "0x33"},
    "sub":      {"extension": ["rv_i"],        "mask": "0xfe00707f", "match": "0x40000033"},
    "mul":      {"extension": ["rv_m"],        "mask": "0xfe00707f", "match": "0x2000033"},
    "sh1add":   {"extension": ["rv_zba"],      "mask": "0xfe00707f", "match": "0x20002033"},
    "sh2add":   {"extension": ["rv_zba"],      "mask": "0xfe00707f", "match": "0x20004033"},
    "zext.h":   {"extension": ["rv_zbb", "rv64_zbb"], "mask": "0xfff0707f", "match": "0x800004033"},
    "rev8":     {"extension": ["rv_zbb", "rv64_zbb"], "mask": "0xfff0707f", "match": "0x6b805013"},
    "aes64ks1i":{"extension": ["rv64_zknd", "rv64_zkne"], "mask": "0xff00707f", "match": "0x31001013"},
    "csrrw":    {"extension": ["rv_zicsr"],    "mask": "0x707f", "match": "0x1073"},
    "fence.i":  {"extension": ["rv_zifencei"], "mask": "0xffffffff", "match": "0x100f"},
}


# ────────────────────────────────────────────────────────────────────────────
# Tier 1 tests
# ────────────────────────────────────────────────────────────────────────────

class TestTier1Parsing(unittest.TestCase):

    def setUp(self):
        self.groups = tier1.group_by_extension(MINIMAL_DICT)
        self.multi  = tier1.find_multi_extension_instructions(MINIMAL_DICT)

    # -- group_by_extension ---------------------------------------------------

    def test_all_extensions_present(self):
        expected = {"rv_i", "rv_m", "rv_zba", "rv_zbb", "rv64_zbb",
                    "rv64_zknd", "rv64_zkne", "rv_zicsr", "rv_zifencei"}
        self.assertEqual(set(self.groups.keys()), expected)

    def test_rv_i_contains_correct_instructions(self):
        self.assertIn("add", self.groups["rv_i"])
        self.assertIn("sub", self.groups["rv_i"])
        self.assertEqual(len(self.groups["rv_i"]), 2)

    def test_rv_m_contains_mul(self):
        self.assertIn("mul", self.groups["rv_m"])

    def test_rv_zba_count(self):
        self.assertEqual(len(self.groups["rv_zba"]), 2)

    def test_multi_extension_instruction_appears_in_both_groups(self):
        # zext.h is in rv_zbb and rv64_zbb
        self.assertIn("zext.h", self.groups["rv_zbb"])
        self.assertIn("zext.h", self.groups["rv64_zbb"])

    def test_groups_sorted_by_count_descending(self):
        counts = [len(v) for v in self.groups.values()]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_each_extension_list_sorted_alphabetically(self):
        for ext, instrs in self.groups.items():
            self.assertEqual(instrs, sorted(instrs), msg=f"Failed for {ext}")

    def test_string_extension_field_handled(self):
        """extension field may be a bare string rather than a list."""
        d = {"nop": {"extension": "rv_i", "mask": "0x0", "match": "0x0"}}
        groups = tier1.group_by_extension(d)
        self.assertIn("rv_i", groups)
        self.assertIn("nop", groups["rv_i"])

    def test_missing_extension_field_handled(self):
        """Instructions without an extension field should be skipped silently."""
        d = {"mystery": {"mask": "0x0", "match": "0x0"}}
        groups = tier1.group_by_extension(d)
        self.assertEqual(groups, {})

    # -- find_multi_extension_instructions ------------------------------------

    def test_multi_extension_detection(self):
        self.assertIn("zext.h",     self.multi)
        self.assertIn("rev8",       self.multi)
        self.assertIn("aes64ks1i",  self.multi)

    def test_single_extension_not_in_multi(self):
        self.assertNotIn("add",     self.multi)
        self.assertNotIn("sh1add",  self.multi)
        self.assertNotIn("csrrw",   self.multi)

    def test_multi_extension_values_are_lists(self):
        for instrs_exts in self.multi.values():
            self.assertIsInstance(instrs_exts, list)

    def test_multi_extension_values_have_length_gt_one(self):
        for instrs_exts in self.multi.values():
            self.assertGreater(len(instrs_exts), 1)

    def test_multi_count(self):
        # zext.h, rev8, aes64ks1i → 3 multi-extension instructions
        self.assertEqual(len(self.multi), 3)

    # -- load_instr_dict (local file) -----------------------------------------

    def test_load_local_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(MINIMAL_DICT, f)
            tmp_path = f.name
        try:
            data = tier1.load_instr_dict(tmp_path)
            self.assertEqual(set(data.keys()), set(MINIMAL_DICT.keys()))
        finally:
            os.unlink(tmp_path)

    def test_load_nonexistent_file_raises(self):
        with self.assertRaises((FileNotFoundError, OSError)):
            tier1.load_instr_dict("/nonexistent/path/instr_dict.json")


# ────────────────────────────────────────────────────────────────────────────
# Tier 2 tests
# ────────────────────────────────────────────────────────────────────────────

class TestTier2Normalisation(unittest.TestCase):

    # -- JSON normalisation ---------------------------------------------------

    def test_rv_prefix_stripped(self):
        self.assertEqual(tier2._normalize_json_ext("rv_i"),      "i")
        self.assertEqual(tier2._normalize_json_ext("rv_m"),      "m")
        self.assertEqual(tier2._normalize_json_ext("rv_zba"),    "zba")
        self.assertEqual(tier2._normalize_json_ext("rv_zicsr"),  "zicsr")

    def test_rv64_prefix_stripped(self):
        self.assertEqual(tier2._normalize_json_ext("rv64_i"),    "i")
        self.assertEqual(tier2._normalize_json_ext("rv64_zba"),  "zba")
        self.assertEqual(tier2._normalize_json_ext("rv64_zknd"), "zknd")

    def test_rv32_prefix_stripped(self):
        self.assertEqual(tier2._normalize_json_ext("rv32_zknh"), "zknh")

    def test_rv128_prefix_stripped(self):
        self.assertEqual(tier2._normalize_json_ext("rv128_i"),   "i")

    def test_already_bare(self):
        # A tag without rv_ prefix should come through lowercased only
        self.assertEqual(tier2._normalize_json_ext("zba"), "zba")

    # -- Manual normalisation -------------------------------------------------

    def test_Zba_normalised(self):
        self.assertEqual(tier2._normalize_manual_ext("Zba"),       "zba")

    def test_Zicsr_normalised(self):
        self.assertEqual(tier2._normalize_manual_ext("Zicsr"),     "zicsr")

    def test_single_letter_M(self):
        self.assertEqual(tier2._normalize_manual_ext("M"),         "m")

    def test_RV32I_maps_to_i(self):
        self.assertEqual(tier2._normalize_manual_ext("RV32I"),     "i")

    def test_RV64GC_maps_to_i(self):
        self.assertEqual(tier2._normalize_manual_ext("RV64GC"),    "i")

    def test_Hypervisor_maps_to_h(self):
        self.assertEqual(tier2._normalize_manual_ext("Hypervisor"), "h")

    def test_Smstateen_normalised(self):
        self.assertEqual(tier2._normalize_manual_ext("Smstateen"), "smstateen")

    # -- cross_reference logic ------------------------------------------------

    def _make_groups(self):
        return tier1.group_by_extension(MINIMAL_DICT)

    def test_matched_includes_zba(self):
        groups   = self._make_groups()
        manual   = {"Zba", "Zbb", "Zicsr", "M", "RV32I"}
        results  = tier2.cross_reference(groups, manual)
        self.assertIn("zba",   results["matched_json"])

    def test_json_only_detected(self):
        groups   = self._make_groups()
        # Provide a manual that doesn't mention zifencei
        manual   = {"Zba", "Zbb", "Zicsr"}
        results  = tier2.cross_reference(groups, manual)
        self.assertIn("zifencei", results["json_only"])

    def test_manual_only_detected(self):
        groups   = self._make_groups()
        manual   = {"Zba", "Zbb", "Zicsr", "D", "F", "Q"}  # D, F, Q not in JSON
        results  = tier2.cross_reference(groups, manual)
        self.assertIn("d", results["manual_only"])
        self.assertIn("f", results["manual_only"])

    def test_empty_manual_everything_json_only(self):
        groups   = self._make_groups()
        results  = tier2.cross_reference(groups, set())
        self.assertEqual(results["matched_json"], {})
        self.assertEqual(results["manual_only"],  {})
        self.assertGreater(len(results["json_only"]), 0)

    def test_results_keys_present(self):
        groups   = self._make_groups()
        results  = tier2.cross_reference(groups, set())
        for key in ("matched_json", "json_only", "manual_only",
                    "json_canonical", "manual_canonical"):
            self.assertIn(key, results)

    # -- Offline fallback list ------------------------------------------------

    def test_offline_list_is_nonempty(self):
        self.assertGreater(len(tier2.OFFLINE_MANUAL_EXTENSIONS), 10)

    def test_offline_list_contains_key_extensions(self):
        ol = tier2.OFFLINE_MANUAL_EXTENSIONS
        for ext in ("Zba", "Zbb", "Zicsr", "Zifencei", "M", "A", "F", "D"):
            self.assertIn(ext, ol, msg=f"Expected '{ext}' in offline list")


# ────────────────────────────────────────────────────────────────────────────
# Tier 3 tests
# ────────────────────────────────────────────────────────────────────────────

class TestTier3Graph(unittest.TestCase):

    def setUp(self):
        self.groups  = tier1.group_by_extension(MINIMAL_DICT)
        self.sharing = tier3.build_sharing_graph(MINIMAL_DICT)
        self.adj     = tier3.build_adjacency(self.groups, MINIMAL_DICT)

    # -- build_sharing_graph --------------------------------------------------

    def test_zbb_zkbb64_edge_exists(self):
        edge = tuple(sorted(["rv_zbb", "rv64_zbb"]))
        self.assertIn(edge, self.sharing)

    def test_zbb_zkbb64_shared_instructions(self):
        edge   = tuple(sorted(["rv_zbb", "rv64_zbb"]))
        shared = self.sharing[edge]
        self.assertIn("zext.h", shared)
        self.assertIn("rev8",   shared)

    def test_zknd_zkne_edge_exists(self):
        edge = tuple(sorted(["rv64_zknd", "rv64_zkne"]))
        self.assertIn(edge, self.sharing)

    def test_no_self_loops(self):
        for a, b in self.sharing:
            self.assertNotEqual(a, b)

    def test_edges_are_sorted_pairs(self):
        for a, b in self.sharing:
            self.assertLessEqual(a, b, msg=f"Edge ({a},{b}) not sorted")

    def test_single_extension_instructions_create_no_edges(self):
        # add is only in rv_i; no edge should connect rv_i to itself
        single_ext_edges = [
            (a, b) for (a, b) in self.sharing
            if (a == "rv_i" or b == "rv_i") and a != b
        ]
        # There are no multi-extension instrs shared between rv_i and anything
        self.assertEqual(single_ext_edges, [])

    # -- build_adjacency ------------------------------------------------------

    def test_all_extensions_in_adjacency(self):
        for ext in self.groups:
            self.assertIn(ext, self.adj)

    def test_adjacency_is_symmetric(self):
        for ext, neighbours in self.adj.items():
            for nb in neighbours:
                self.assertIn(ext, self.adj.get(nb, set()),
                              msg=f"Asymmetry: {ext} -> {nb} but not reverse")

    def test_isolated_node_has_empty_neighbour_set(self):
        # rv_i has no shared instructions with any other ext in our fixture
        self.assertEqual(self.adj.get("rv_i", set()), set())

    # -- export functions ─────────────────────────────────────────────────────

    def test_dot_export_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            out = f"{td}/test.dot"
            tier3.export_dot(self.groups, MINIMAL_DICT, out)
            self.assertTrue(Path(out).exists())

    def test_dot_export_contains_graph_keyword(self):
        with tempfile.TemporaryDirectory() as td:
            out = f"{td}/test.dot"
            tier3.export_dot(self.groups, MINIMAL_DICT, out)
            content = Path(out).read_text()
            self.assertIn("graph", content.lower())
            self.assertIn("rv_zbb", content)

    def test_mermaid_export_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            out = f"{td}/test.mmd"
            tier3.export_mermaid(self.groups, MINIMAL_DICT, out)
            self.assertTrue(Path(out).exists())

    def test_mermaid_export_starts_with_graph(self):
        with tempfile.TemporaryDirectory() as td:
            out = f"{td}/test.mmd"
            tier3.export_mermaid(self.groups, MINIMAL_DICT, out)
            first_line = Path(out).read_text().splitlines()[0]
            self.assertTrue(first_line.startswith("graph"))


# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
