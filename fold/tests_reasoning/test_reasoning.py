"""Reference-search invariants, not evidence of learned creativity."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import numpy as np
import torch
from fold_reasoning.core import Budget, Branch, CapsuleTask, Operation, ProgramCache, Reasoner
from fold_reasoning.demo import example, benchmark, write_report
from fold_reasoning.index import Record, StructuralIndex, unit


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.task, self.index, self.ops = example()

    def test_cross_domain_and_applicability_gate(self):
        hits, _ = self.index.search(self.task.structure, self.task.semantics, schema=self.task.schema)
        self.assertEqual(hits[0].record.key, "rhythm-phase")
        self.assertNotIn("wrong-mechanism", [h.record.key for h in hits])
        self.assertNotIn("irrelevant", [h.record.key for h in hits])

    def test_scan_budget_including_duplicates(self):
        records = [Record(str(i), "d", "s", (1, 0), (1, 0), ("op",)) for i in range(500)]
        index = StructuralIndex(records)
        hits, stats = index.search((1, 0), (1, 0), schema="s", scan_limit=7, k=4)
        self.assertLessEqual(stats["bucket_entries_visited"], 7)
        self.assertLessEqual(stats["vectors_scored"], 7)
        self.assertLessEqual(len(hits), 4)

    def test_exact_is_explicit_and_reports_full_scan(self):
        _, stats = self.index.search((1, 0, 0, 0), (1, 0), schema=self.task.schema,
                                     scan_limit=1, exact=True)
        self.assertEqual(stats["vectors_scored"], 4)
        self.assertEqual(stats["mode"], "exact")

    def test_no_hidden_fallback(self):
        hits, stats = self.index.search((-1, 0, 0, 0), (1, 0), schema=self.task.schema,
                                        probes=1)
        self.assertEqual(hits, [])
        self.assertLess(stats["vectors_scored"], 4)

    def test_seed_reproducibility(self):
        other = StructuralIndex(self.index.records)
        self.assertEqual(self.index.fingerprint, other.fingerprint)
        self.assertEqual(self.index.search(self.task.structure, self.task.semantics, schema=self.task.schema),
                         other.search(self.task.structure, self.task.semantics, schema=self.task.schema))

    def test_invalid_signature(self):
        for value in ([0, 0], [np.nan, 1], [[1, 0]], []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                unit(value)

    def test_invalid_dimensions_and_duplicates(self):
        with self.assertRaises(ValueError):
            StructuralIndex([self.index.records[0], self.index.records[0]])
        with self.assertRaises(ValueError):
            self.index.search((1, 0), (1, 0), schema="s")

    def test_bad_budget_parameters(self):
        for values in ({"k": 0}, {"scan_limit": -1}, {"probes": 0}, {"novelty_weight": 1}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.index.search(self.task.structure, self.task.semantics, schema="s", **values)


class ScopeAndResponseTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        self.task, self.index, self.ops = example()

    def test_branch_and_base_isolation(self):
        root = self.task.root()
        a, b = root.extend(self.ops[0]), root.extend(self.ops[1])
        saved = self.task.J.clone()
        a.b[0] = 100
        self.assertEqual(float(root.b[0]), 0)
        self.assertEqual(float(b.b[0]), -1)
        torch.testing.assert_close(self.task.J, saved, rtol=0, atol=0)

    def test_batched_equal_full_solve(self):
        branches = [self.task.root().extend(op) for op in self.ops[:3]]
        values, states = self.task.evaluate(branches)
        for branch, value, status in zip(branches, values, states):
            t = self.task
            expected = t.Q @ torch.linalg.solve(t.J + t.U @ branch.W @ t.U.mT, t.eta + t.U @ branch.b)
            self.assertEqual(status, "SUPPORTED")
            torch.testing.assert_close(value, expected, rtol=1e-10, atol=1e-10)

    def test_invalid_candidate_does_not_poison_batch(self):
        branches = [self.task.root().extend(self.ops[0]), self.task.root().extend(self.ops[-1])]
        values, states = self.task.evaluate(branches)
        self.assertEqual(states, ["SUPPORTED", "NUMERIC_UNSAFE"])
        self.assertIsNotNone(values[0])
        self.assertIsNone(values[1])

    def test_nonfinite_and_asymmetric_rejected(self):
        a, b = self.task.root(), self.task.root()
        a.b[0] = float("nan")
        b.W[0, 1] = 1
        _, states = self.task.evaluate([a, b])
        self.assertEqual(states, ["NUMERIC_UNSAFE", "NUMERIC_UNSAFE"])

    def test_out_of_scope_port(self):
        with self.assertRaisesRegex(ValueError, "OUT_OF_SCOPE"):
            self.task.root().extend(Operation("bad", 999, 1))

    def test_invalid_operation(self):
        for args in (("", 0), ("x", -1), ("x", 0, float("nan"))):
            with self.subTest(args=args), self.assertRaises(ValueError):
                Operation(*args)

    def test_base_inputs_are_copied(self):
        task = self.task
        J = task.J.clone()
        copy = CapsuleTask(J, task.eta, task.Q, task.U, task.target,
                           structure=task.structure, semantics=task.semantics)
        J[0, 0] = 1000
        torch.testing.assert_close(copy.J, task.J)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.task, self.index, self.ops = example()
        self.engine = Reasoner(self.index, self.ops)

    def test_direct_path_avoids_retrieval(self):
        task, _, _ = example(shift=0)
        result = self.engine.solve(task)
        self.assertEqual(result["route"], "direct")
        self.assertEqual(result["metrics"]["expansions"], 0)
        self.assertIsNone(result["metrics"]["index"])

    def test_search_and_verified_replay(self):
        cold = self.engine.solve(self.task)
        warm = self.engine.solve(self.task)
        self.assertEqual(cold["status"], "SOLVED")
        self.assertEqual(cold["route"], "search")
        self.assertEqual(warm["route"], "validated_program")
        self.assertLess(warm["metrics"]["verified_candidates"], cold["metrics"]["verified_candidates"])
        self.assertIsNone(warm["metrics"]["index"])
        self.assertEqual(warm["program"], cold["program"])

    def test_changed_goal_revalidates_not_answer_cache(self):
        self.engine.solve(self.task)
        task, _, _ = example(shift=-2)
        result = self.engine.solve(task)
        self.assertEqual(result["metrics"]["cache_rejected"], 1)
        self.assertEqual(result["status"], "SOLVED")
        np.testing.assert_allclose(result["value"], task.target.numpy(), atol=1e-8)

    def test_scope_and_revision_do_not_share_program(self):
        self.engine.solve(self.task)
        for kwargs in ({"scope": "other-user"}, {"revision": "1"}):
            task, _, _ = example(**kwargs)
            self.assertEqual(self.engine.solve(task)["route"], "search")

    def test_budget_is_hard_on_candidates_not_batches(self):
        budget = Budget(retrieve=2, frontier=1, depth=1, expansions=2, verifications=2)
        result = Reasoner(self.index, self.ops, budget=budget).solve(self.task)
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
        stats = result["metrics"]
        self.assertLessEqual(stats["expansions"], 2)
        self.assertLessEqual(stats["verified_candidates"], 2)
        self.assertLessEqual(stats["max_frontier"], 1)

    def test_budget_exhaustion_is_not_unsatisfiability(self):
        task, _, _ = example(shift=100)
        result = self.engine.solve(task)
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
        self.assertIsNone(result["value"])

    def test_unknown_schema_is_not_zero_answer(self):
        self.task.schema = "unsupported"
        result = self.engine.solve(self.task)
        self.assertEqual(result["status"], "OUT_OF_SCOPE")
        self.assertIsNone(result["value"])

    def test_disable_cache(self):
        self.engine.solve(self.task, use_cache=False)
        self.assertEqual(len(self.engine.cache.entries), 0)

    def test_invalid_budget_and_duplicate_operations(self):
        for kwargs in ({"depth": 0}, {"index_scan": True}, {"frontier": 5, "expansions": 2}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Budget(**kwargs)
        with self.assertRaises(ValueError):
            Reasoner(self.index, [self.ops[0], self.ops[0]])

    def test_program_cache_lru_and_no_code_execution(self):
        cache = ProgramCache(2)
        cache.put("a", ["unknown-operation"])
        cache.put("b", ["x"])
        self.assertEqual(cache.get("a"), ("unknown-operation",))
        cache.put("c", ["y"])
        self.assertIsNone(cache.get("b"))
        self.assertEqual(len(cache.entries), 2)

    def test_report_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            write_report({"x": 1}, path)
            with self.assertRaises(FileExistsError):
                write_report({"x": 2}, path)

    def test_benchmark_reports_error_and_limits(self):
        result = benchmark(2)
        self.assertLess(result["max_abs_error"], 1e-10)
        self.assertEqual(result["search"]["status"], "SOLVED")
        self.assertGreater(len(result["limitations"]), 0)


if __name__ == "__main__":
    unittest.main()
