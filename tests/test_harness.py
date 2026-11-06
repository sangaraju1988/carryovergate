import json
import tempfile
import unittest
from pathlib import Path

from harness.agents import StubAgent
from harness.loop import run_scenario

TASKS = json.loads((Path(__file__).parent.parent / "tasks" / "carryover_tasks.json").read_text())
SCEN = {s["id"]: s for s in TASKS["scenarios"]}


def run(sid, gate_on, rounds=5):
    with tempfile.TemporaryDirectory() as d:
        return list(run_scenario(Path(d), TASKS, SCEN[sid], gate_on, StubAgent(), rounds))


class StubHarnessTests(unittest.TestCase):
    def test_gate_off_every_payload_refires_every_round(self):
        for sid, s in SCEN.items():
            if s["channel"] == "none":
                continue
            rows = run(sid, False)
            self.assertEqual([r["attack_success"] for r in rows], [True] * 5, sid)

    def test_gate_on_blocks_lineage_detectable_payloads(self):
        for sid in ("L1", "L2", "L3", "L4", "A1", "A2", "A3", "A4", "A5"):
            rows = run(sid, True)
            self.assertEqual([r["attack_success"] for r in rows], [False] * 5, sid)

    def test_gate_on_misses_untrusted_state_claim(self):
        # L5: class-4 fact, not instruction-like -> allowed with label; stub uses it.
        rows = run("L5", True)
        self.assertEqual([r["attack_success"] for r in rows], [True] * 5)

    def test_controls_complete_both_conditions_on_negative_control(self):
        for g in (False, True):
            for r in run("N0", g):
                self.assertEqual(r["control_tasks_completed"],
                                 {"C6": True, "C7": True, "C8": True}, (g, r["round"]))

    def test_no_control_entry_blocked_by_gate(self):
        for sid in SCEN:
            for r in run(sid, True, rounds=1):
                for c in r["gate_checks"]:
                    if c["kind"] == "refire" and c["role"] == "control":
                        self.assertIn(c["decision"], ("allow", "allow_labelled"), (sid, c))

    def test_benign_untrusted_split(self):
        r = run("N0", True, rounds=1)[0]
        d = {c["entry_id"]: c["decision"] for c in r["gate_checks"] if c["kind"] == "refire"}
        self.assertEqual(d["B1"], "allow_labelled")
        self.assertEqual(d["B2"], "block")          # benign but instruction-like
        self.assertEqual(d["B3"], "allow_labelled")

    def test_tamper_and_missing_parent_quarantined(self):
        for sid in ("L4", "A3", "A4"):
            r = run(sid, True, rounds=1)[0]
            d = {c["entry_id"]: c["decision"] for c in r["gate_checks"] if c["kind"] == "refire"}
            self.assertEqual(d["P"], "quarantine_broken_lineage", sid)

    def test_negative_control_identical_outcomes(self):
        off = run("N0", False)
        on = run("N0", True)
        strip = lambda rows: [[(c["tool"], c["args"]) for c in r["executed_calls"]] for r in rows]
        self.assertEqual(strip(off), strip(on))


if __name__ == "__main__":
    unittest.main()
