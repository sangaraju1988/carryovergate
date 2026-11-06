"""Run the synthetic carryover tasks: every scenario x gate off/on x agent,
5 rounds each, appending rows to <run>/harness_progress.jsonl."""
import argparse
import json
from pathlib import Path

from harness.agents import OllamaAgent, StubAgent
from harness.loop import run_scenario


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--agents", default="stub,ollama")
    ap.add_argument("--model", default="qwen3:4b-instruct")
    ap.add_argument("--rounds", type=int, default=5)
    a = ap.parse_args()
    run = Path(a.run_dir)
    tasks = json.loads(Path("tasks/carryover_tasks.json").read_text())
    agents = []
    for name in a.agents.split(","):
        agents.append(StubAgent() if name == "stub" else OllamaAgent(model=a.model))
    out = run / "harness_progress.jsonl"
    with out.open("a") as fh:
        for agent in agents:
            for sc in tasks["scenarios"]:
                for gate_on in (False, True):
                    try:
                        for row in run_scenario(run / "harness_state", tasks, sc, gate_on, agent,
                                                a.rounds):
                            row["source"] = "carryover_harness"
                            fh.write(json.dumps(row) + "\n")
                            fh.flush()
                            print(f"{agent.name} {sc['id']} gate={'on' if gate_on else 'off'} "
                                  f"r{row['round']} attack={row['attack_success']} "
                                  f"controls={row['control_tasks_completed']}", flush=True)
                    except Exception as e:  # keep failures in the log
                        fh.write(json.dumps({"source": "carryover_harness", "agent": agent.name,
                                             "scenario": sc["id"], "gate": "on" if gate_on else "off",
                                             "error": repr(e)[:500]}) + "\n")
                        fh.flush()
                        print(f"ERROR {agent.name} {sc['id']}: {e!r}", flush=True)


if __name__ == "__main__":
    main()
