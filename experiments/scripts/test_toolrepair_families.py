"""Construct-validity checks for ToolRepair-12 (trusted reference/defective tools only)."""

import ast
import unittest

import toolrepair_families as tr

BASE_IMPORTS = {"csv", "sys", "decimal"}


class FamilyContracts(unittest.TestCase):
    def test_twelve_uniquely_named_families(self):
        self.assertEqual(len(tr.FAMILIES), 12)
        self.assertEqual(len(tr.BY_NAME), 12)

    def test_splits_are_deterministic_and_disjoint(self):
        for f in tr.FAMILIES:
            split = {s: tr.inputs(f, s) for s in tr.SPLITS}
            self.assertEqual(split, {s: tr.inputs(f, s) for s in tr.SPLITS}, f.name)
            texts = [t for values in split.values() for t in values]
            self.assertEqual(len(texts), len(set(texts)), f.name + ": split inputs coincide")

    def test_reference_succeeds_on_every_split(self):
        for f in tr.FAMILIES:
            for split in tr.SPLITS:
                for text in tr.inputs(f, split):
                    self.assertTrue(tr.expected(f, text).strip(), f.name)

    def test_defect_is_observable_on_every_task_and_some_validation_input(self):
        for f in tr.FAMILIES:
            for text in tr.inputs(f, "task"):
                self.assertNotEqual(tr.run_trusted(f.buggy, text), (0, tr.expected(f, text)), f.name + ": task")
            self.assertTrue(
                any(tr.run_trusted(f.buggy, t) != (0, tr.expected(f, t)) for t in tr.inputs(f, "validation")),
                f.name + ": validators cannot detect the defect",
            )

    def test_tools_stay_inside_the_allowlisted_program_domain(self):
        for f in tr.FAMILIES:
            for source in (f.buggy, f.reference):
                modules = set()
                for node in ast.walk(ast.parse(source)):
                    if isinstance(node, ast.Import):
                        modules |= {a.name for a in node.names}
                    elif isinstance(node, ast.ImportFrom):
                        modules.add(node.module)
                self.assertLessEqual(modules, BASE_IMPORTS | f.extra_imports, f.name)

    def test_specification_never_names_the_defect(self):
        for f in tr.FAMILIES:
            self.assertNotIn("bug", f.spec.lower())
            self.assertNotIn(f.defect.lower(), f.spec.lower())


if __name__ == "__main__":
    unittest.main()
