"""v0.2 full run: harness re-run (fixed gate), Part A (all 90 cases, base defense
`none`, gate off/on x injected/no-injection), Part B (H3: each primary base
defense alone vs with the gate, injected only), optional exploratory extension.

Every pass is resumable. The benchmark's resume=True skips scored samples, and
the harness pass is re-run whole if it is incomplete. After each completed pass,
progress.jsonl is rebuilt from all logs, run.json is updated, and the two are
committed (and pushed unless --no-push). Raw inspect logs stay local.

  .venv/bin/python -m eval.run_full --benchmark-repo ../task-tampering-prompt-injection
  ... --run-id full-v02-<ts> --skip-harness          # resume a run, skip the harness
  ... --skip-bench   (skip Part A)   --skip-h3 (skip Part B)   --h3-extension (add exploratory set)
"""
import argparse
import datetime as dt
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from gate import POLICY_VERSION

PILOT_BENCHMARK_COMMIT = "804b00dd03051c00e5e3000982bbf7ce2b9d9ad5"
PRIMARY_H3 = ["spotlight", "sandwich", "trust_hierarchy", "drift_full_guided"]   # PREREGISTRATION-v0.2.md
EXTENSION_H3 = ["trust_hierarchy_env", "drift_isolation", "drift_full"]          # exploratory only
FROZEN_PATHS = ["gate", "harness", "tasks"]

CAVEATS = [
    "Judge for the benchmark's LLM-judged checks is mistral-nemo-12b (local), not the paper's claude-sonnet-4-20250514; the agent is a 4B open-weight model. Absolute ASR here is NOT comparable to the paper's published residuals (9.5% / 12.1% / 15.4%).",
    "One injection variant per case (`original`, labelled compound) on all 90 cases. Each condition was run once; with one run per condition, gate effects and run-to-run variance cannot be fully separated, and differences of a few samples are within noise.",
    "The benchmark is single-session. The gate is applied where its decision table applies inside one session: tool-read content is treated as recalled class-4 entries (READ row) and every tool call as an agent-derived entry (side-effect rows). Cross-session re-fire is exercised only by the synthetic harness.",
    "Benchmark adapter mandate: class-3 side-effecting calls are allowed only for tools in the case's `required_tools` field. That stands in for a user who pre-approved exactly their task's tools; a deployment would need the user to supply it.",
    "The gate does not adjudicate truth: a false fact with clean-looking content passes through with a provenance label. It stops instruction-like content and tool calls outside the mandate.",
    "H1's 'largest drop on tool-policy' clause is untestable: the benchmark labels no observation/state/tool-policy split, and no mapping was invented.",
    "No no-injection runs under composed defenses (D + gate): the composition's utility tax on clean runs is unmeasured in v0.2. Part A's clean-run numbers are for base defense `none` only.",
    "The gate composes only with the benchmark's DefenseEvalSolver defenses; camel_scoped, progent and progent_fullschema use their own solvers and were not run.",
    "Primary DRIFT representative is drift_full_guided (the benchmark's documented default full-DRIFT variant), recorded as a deviation in PREREGISTRATION-v0.2.md before any run; drift_full is exploratory.",
    "Model serving as in the pilot: agent qwen3:4b-instruct weights with num_ctx 32768; judge mistral-nemo:12b with num_ctx 16384; inspect_ai attempt_timeout=180 s (transport only); per-sample time limit 540 s.",
    "Dependency pins needed for the benchmark's pinned inspect_ai/mcp: openai>=2,<3 and pydantic>=2.12,<2.13.",
    "Synthetic harness memory is fixed after planting (agents have no memory-write tool). Tasks are synthetic and fictional. Harness numbers in this run are from the fixed (post-KB1) gate.",
]


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def git(*args, check=True):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check).stdout.strip()


def sh(cmd, log: Path, env=None) -> int:
    with log.open("a") as fh:
        fh.write(f"\n[{now()}] $ {' '.join(cmd)}\n")
        fh.flush()
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env)
        fh.write(f"[exit {p.returncode}]\n")
    return p.returncode


def preflight_repo(meta: dict) -> None:
    """Refuse to run on a failing gate, or on a gate changed since the v0.2 preregistration."""
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                       capture_output=True, text=True)
    tail = (p.stderr or p.stdout).strip().splitlines()[-3:]
    meta["unit_tests"] = {"exit": p.returncode, "tail": tail, "at": now()}
    if p.returncode != 0:
        sys.exit(f"unit tests failed, refusing to run: {tail}")
    prereg = git("log", "-1", "--format=%H", "--", "PREREGISTRATION-v0.2.md")
    if not prereg:
        sys.exit("PREREGISTRATION-v0.2.md is not committed; commit it before any v0.2 run")
    meta["prereg_v02_commit"] = prereg
    dirty = git("status", "--porcelain", "--", *FROZEN_PATHS)
    changed = git("diff", "--name-only", prereg, "HEAD", "--", *FROZEN_PATHS)
    if dirty or changed:
        sys.exit(f"gate/harness/tasks changed since the v0.2 preregistration: {dirty or changed}")


def rebuild_progress(run: Path) -> int:
    from eval.extract_bench import rows_for
    rows = []
    hp = run / "harness_progress.jsonl"
    if hp.exists():
        rows += [json.loads(l) for l in hp.read_text().splitlines() if l.strip()]
    if (run / "inspect").exists():
        rows += rows_for(run / "inspect")
    with (run / "progress.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    return len(rows)


def scored_count(run: Path, cond: str, base: str, injected: bool) -> tuple:
    n = s = 0
    pp = run / "progress.jsonl"
    if not pp.exists():
        return 0, 0
    for l in pp.read_text().splitlines():
        r = json.loads(l)
        if r.get("source") == "task_tampering" and r["condition"] == cond \
                and r.get("base_defense", "none") == base and r["injected"] == injected:
            n += 1
            s += bool(r["scored"])
    return s, n


def save(run: Path, meta: dict) -> None:
    (run / "run.json").write_text(json.dumps(meta, indent=1))


def checkpoint(run: Path, meta: dict, label: str, push: bool, extra=()) -> None:
    """Commit run.json + progress.jsonl (+ extra files) so a crash loses no scored work."""
    files = [run / "run.json", run / "progress.jsonl", *extra]
    hp = run / "harness_progress.jsonl"
    if hp.exists():
        files.append(hp)
    files = [str(f) for f in files if Path(f).exists()]
    git("add", *files)
    if not git("diff", "--cached", "--name-only"):
        return
    git("commit", "-q", "-m", f"v0.2 {meta['run_id']}: {label}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    rec = {"label": label, "commit": git("rev-parse", "HEAD"), "at": now(), "pushed": False}
    if push:
        p = subprocess.run(["git", "push", "-q", "origin", "HEAD:master"], capture_output=True, text=True)
        rec["pushed"] = p.returncode == 0
        if p.returncode != 0:
            rec["push_error"] = p.stderr.strip()[-300:]
    meta.setdefault("checkpoints", []).append(rec)
    save(run, meta)


def write_report_files(run: Path):
    from eval.report import write_report
    write_report(run, quiet=True)
    return [run / "REPORT.md", run / "metrics.json"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark-repo", required=True)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--model", default="qwen3-4b-instruct-32k")
    ap.add_argument("--judge-model", default="mistral-nemo-12b-16k")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--attempt-timeout", type=int, default=180)
    ap.add_argument("--time-limit", type=int, default=540)
    ap.add_argument("--skip-harness", action="store_true")
    ap.add_argument("--skip-bench", action="store_true", help="skip Part A")
    ap.add_argument("--skip-h3", action="store_true", help="skip Part B primary")
    ap.add_argument("--h3-extension", action="store_true", help="run the exploratory extension set")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()

    run_id = a.run_id or "full-v02-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%MZ")
    run = Path("runs") / run_id
    (run / "logs").mkdir(parents=True, exist_ok=True)
    push = not a.no_push
    cases = json.loads(Path("eval/full_cases.json").read_text())
    bench_commit = git("-C", a.benchmark_repo, "rev-parse", "HEAD")

    meta = {
        "run_id": run_id, "report_shape": "v0.2", "started_at": now(),
        "model": f"ollama/{a.model}", "judge_model": f"ollama/{a.judge_model}",
        "llm_check_votes": os.environ.get("LLM_CHECK_VOTES", "3"), "temperature": 0.0,
        "attempt_timeout_s": a.attempt_timeout, "time_limit_s": a.time_limit,
        "benchmark_repo": "github.com/amazon-science/task-tampering-prompt-injection",
        "benchmark_commit": bench_commit,
        "benchmark_commit_matches_pilot": bench_commit == PILOT_BENCHMARK_COMMIT,
        "carryovergate_commit": git("rev-parse", "HEAD"),
        "policy_version": POLICY_VERSION, "case_seed": None, "cases": cases["cases"],
        "n_cases": sum(len(v) for v in cases["cases"].values()),
        "primary_h3_defenses": PRIMARY_H3, "extension_h3_defenses": EXTENSION_H3,
        "harness_rounds": a.rounds, "harness_agents": ["stub", f"ollama:{a.model}"],
        "primary_harness_agent": f"ollama:{a.model}",
        "platform": platform.platform(), "python": sys.version.split()[0],
        "caveats": CAVEATS, "known_bugs": [], "steps": [],
    }
    prev = run / "run.json"
    if prev.exists():
        old = json.loads(prev.read_text())
        for k in ("started_at", "steps", "checkpoints", "judge_preflights", "known_bugs",
                  "harness_complete", "observed_rates"):
            if k in old:
                meta[k] = old[k]
        meta["resumes"] = old.get("resumes", []) + [{
            "at": now(), "carryovergate_commit": meta["carryovergate_commit"],
            "flags": {k: getattr(a, k) for k in ("skip_harness", "skip_bench", "skip_h3", "h3_extension")}}]
    if not meta["benchmark_commit_matches_pilot"]:
        print(f"WARNING: benchmark checkout is {bench_commit}, not the pilot's {PILOT_BENCHMARK_COMMIT}. "
              f"Recorded in run.json; record it in PREREGISTRATION-v0.2.md deviations too.")
    preflight_repo(meta)
    save(run, meta)
    py = sys.executable

    # ---- harness (fixed gate) -------------------------------------------------
    if not a.skip_harness and not meta.get("harness_complete"):
        hp = run / "harness_progress.jsonl"
        if hp.exists():
            hp.unlink()  # not resumable: re-run whole
        s = time.time()
        rc = sh([py, "-m", "eval.run_harness", "--run-dir", str(run), "--agents", "stub,ollama",
                 "--model", a.model, "--rounds", str(a.rounds)], run / "logs" / "harness.log")
        n = sum(1 for l in hp.read_text().splitlines() if l.strip()) if hp.exists() else 0
        errs = sum(1 for l in hp.read_text().splitlines() if '"error"' in l) if hp.exists() else 0
        meta["harness_complete"] = rc == 0 and n == 220 and errs == 0
        meta["steps"].append({"step": "harness", "exit": rc, "rows": n, "error_rows": errs,
                              "seconds": round(time.time() - s, 1), "at": now()})
        rebuild_progress(run)
        save(run, meta)
        checkpoint(run, meta, "harness re-run (fixed gate)", push)

    # ---- benchmark passes ----------------------------------------------------
    passes = []
    if not a.skip_bench:
        for cond in ("off", "on"):
            for clean in (False, True):
                passes.append(("A", f"A_{cond}_{'clean' if clean else 'injected'}", cond, "none", clean))
    if not a.skip_h3:
        for d in PRIMARY_H3:
            for cond in ("off", "on"):
                passes.append(("B", f"B_{d}_{cond}", cond, d, False))
    if a.h3_extension:
        for d in EXTENSION_H3:
            for cond in ("off", "on"):
                passes.append(("X", f"X_{d}_{cond}", cond, d, False))

    if passes:
        from eval.run_pilot import judge_preflight
        pf = judge_preflight(f"ollama/{a.judge_model}")
        pf["at"] = now()
        meta.setdefault("judge_preflights", []).append(pf)
        meta["judge_preflight"] = meta["judge_preflights"][0]
        save(run, meta)
        if not pf["ok"]:
            sys.exit(f"judge preflight FAILED (malformed output): {pf}")

    env = dict(os.environ, LLM_CHECK_VOTES=meta["llm_check_votes"])
    part_done = {"A": False, "B": False, "X": False}
    for part, name, cond, base, clean in passes:
        cmd = [py, "-m", "eval.bench_run", "--condition", cond, "--base-defense", base,
               "--model", f"ollama/{a.model}", "--judge-model", f"ollama/{a.judge_model}",
               "--cases", "eval/full_cases.json", "--out", str(run / "inspect"),
               "--attempt-timeout", str(a.attempt_timeout), "--time-limit", str(a.time_limit)]
        if clean:
            cmd.append("--no-injection")
        before, _ = scored_count(run, cond, base, not clean)
        s = time.time()
        rc = sh(cmd, run / "logs" / f"{name}.log", env=env)
        secs = round(time.time() - s, 1)
        rebuild_progress(run)
        scored, rows = scored_count(run, cond, base, not clean)
        new = scored - before
        step = {"step": name, "part": part, "condition": cond, "base_defense": base,
                "injected": not clean, "exit": rc, "scored": scored, "rows": rows,
                "expected": meta["n_cases"], "complete": scored == meta["n_cases"],
                "seconds": secs, "newly_scored": new,
                "s_per_new_sample": round(secs / new, 1) if new else None, "at": now()}
        meta["steps"].append(step)
        if new:
            meta.setdefault("observed_rates", []).append({"step": name, "s_per_sample": step["s_per_new_sample"]})
        save(run, meta)
        checkpoint(run, meta, f"pass {name} ({scored}/{meta['n_cases']} scored)", push)
        print(f"[{now()}] {name}: exit {rc}, {scored}/{meta['n_cases']} scored, {secs}s", flush=True)
        remaining = [p for p in passes if p[0] == part and passes.index(p) > passes.index((part, name, cond, base, clean))]
        if not remaining:
            part_done[part] = True
            meta["finished_at"] = now()
            meta["wall_clock_s"] = round(sum(st.get("seconds", 0) for st in meta["steps"]), 1)
            save(run, meta)
            extra = write_report_files(run)
            checkpoint(run, meta, f"Part {part} complete; REPORT.md regenerated", push, extra=extra)

    if not passes and not a.skip_harness:
        meta["wall_clock_s"] = round(sum(st.get("seconds", 0) for st in meta["steps"]), 1)
        save(run, meta)
        extra = write_report_files(run)
        checkpoint(run, meta, "REPORT.md regenerated", push, extra=extra)


if __name__ == "__main__":
    main()
