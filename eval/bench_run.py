"""Run one condition (gate off / on) of the Task-Tampering defense runner over
the pilot cases. One process per condition, so gate OFF never has the patch.

  python -m eval.bench_run --condition on --model ollama/qwen3:4b-instruct \
      --judge-model ollama/qwen3:8b --out runs/<id>/inspect [--no-injection]
"""
import argparse
import json
import os
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", choices=["off", "on"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--judge-model", required=True)
    ap.add_argument("--cases", default="eval/pilot_cases.json")
    ap.add_argument("--out", required=True, help="inspect log root for this run")
    ap.add_argument("--base-defense", default="none",
                    help="benchmark defense the gate sits alongside (DefenseEvalSolver ones)")
    ap.add_argument("--no-injection", action="store_true")
    ap.add_argument("--time-limit", type=int, default=540)
    ap.add_argument("--env", default=None, help="only this environment")
    a = ap.parse_args()

    if a.base_defense in ("camel_scoped", "progent", "progent_fullschema"):
        sys.exit("gate composes with DefenseEvalSolver defenses only in v0.1")

    os.environ["PIB_OUTPUT_DIR"] = str(Path(a.out).resolve() / f"gate_{a.condition}")
    os.environ["LLM_CHECK_MODEL"] = a.judge_model

    from prompt_injection_benchmark.scripts import run_defense as rd  # noqa: E402

    if a.condition == "on":
        from eval.gate_defense import install
        install(rd.VARIATIONS_DIR)

    sel = json.loads(Path(a.cases).read_text())["cases"]
    for env, cases in sel.items():
        if a.env and env != a.env:
            continue
        for case in cases:
            rd.run_defense_eval(
                defense=a.base_defense, model=a.model, env=env, case_filter=case,
                primitive_filter=None if a.no_injection else ["compound"],
                temperature=0.0, max_tasks=1, max_connections=1, retry_on_error=3,
                fail_on_error=False, resume=True, max_per_primitive=1, max_sample_retries=3,
                output_suffix="no_injection" if a.no_injection else None,
                no_injection=a.no_injection, time_limit=a.time_limit,
            )


if __name__ == "__main__":
    main()
