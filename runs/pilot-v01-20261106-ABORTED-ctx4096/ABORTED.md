# Aborted run — kept as a failed log

Started 2026-11-06 22:10 UTC. Stopped by hand at about 22:28 UTC, during the first
benchmark pass (gate off, injected).

## Why it was stopped

1. **Context overflow.** Benchmark sample `devops/A2_original` errored with
   `request (5449 tokens) exceeds the available context size (4096 tokens)`
   (see `logs/bench_off_injected.log`). Ollama served `qwen3:4b-instruct` with its
   4096-token default context. Benchmark trajectories exceed it, so many samples would
   have gone unscored.
2. **Broken judge (found while fixing 1).** The benchmark's LLM judge calls use
   `max_tokens=8`. Through inspect_ai, `qwen3:8b` (a thinking model) returned an
   **empty completion** on three yes/no probes, which the benchmark parses as NO.
   Every LLM-judged check would have scored NO.

No gate code or policy was changed. The fix is model serving and scorer configuration
only; see "Deviations" in `PREREGISTRATION.md`. No results from this run are reported.
What it contains: the synthetic-harness rows (`harness_progress.jsonl`, complete, run
at 4096 context) and three benchmark samples (A1 scored, A2 errored, A3 partial).
