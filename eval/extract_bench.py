"""Turn the benchmark's .eval logs into progress.jsonl rows (one per sample).
Every attempt file is read; for each (condition, env, sample) the last scored
attempt is kept and failed attempts are counted, not hidden."""
import json
import zipfile
from pathlib import Path
from typing import Dict, List


def read_eval(path: Path) -> List[dict]:
    out = []
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return [{"_file": str(path), "_bad_zip": True}]
    with zf:
        for n in zf.namelist():
            if n.startswith("samples/"):
                s = json.loads(zf.read(n))
                s["_file"] = str(path)
                out.append(s)
    return out


def rows_for(inspect_root: Path) -> List[dict]:
    rows: Dict[tuple, dict] = {}
    failed: Dict[tuple, int] = {}
    for f in sorted(inspect_root.glob("gate_*/defense_evaluation/evals/*/*/*/*.eval")):
        cond = f.parts[-7].replace("gate_", "")
        env_label = f.parts[-2]
        injected = not env_label.endswith("_no_injection")
        for s in read_eval(f):
            if s.get("_bad_zip"):
                continue
            key = (cond, env_label, s["id"])
            ps = (s.get("scores") or {}).get("ProgrammaticScorer")
            if not ps:
                failed[key] = failed.get(key, 0) + 1
                if key not in rows:
                    rows[key] = _row(cond, env_label, injected, s, None)
                continue
            rows[key] = _row(cond, env_label, injected, s, ps.get("metadata") or {})
    out = []
    for key, r in sorted(rows.items()):
        r["failed_attempts"] = failed.get(key, 0)
        out.append(r)
    return out


def _norm(t: str) -> str:
    return " ".join(t.replace("\\n", " ").split()).lower()


def _injection_snippets(md: dict) -> List[str]:
    """Normalised lines (>=30 chars) of the injected text: ground truth used only
    by the scorer side, never by the gate."""
    out = []
    for v in (md.get("injection_config") or {}).values():
        for line in str(v).replace("\\n", "\n").split("\n"):
            n = _norm(line)
            if len(n) >= 30:
                out.append(n[:80])
    return out


def _label_leaves(glog: List[dict], snippets: List[str]) -> List[dict]:
    out = []
    for g in glog:
        g = dict(g)
        if g.get("kind") == "recall":
            text = _norm(g.pop("text", ""))
            g["contains_injection"] = bool(snippets) and any(sn in text for sn in snippets)
        out.append(g)
    return out


def _row(cond, env_label, injected, s, sm):
    md = s.get("metadata") or {}
    glog = _label_leaves(md.get("carryovergate_log") or [], _injection_snippets(md) if injected else [])
    err = s.get("error")
    return {
        "source": "task_tampering",
        "condition": cond,
        "environment": md.get("environment", env_label.replace("_no_injection", "")),
        "case_id": md.get("case_id"),
        "sample_id": s["id"],
        "injected": injected,
        "variation_id": md.get("variation_id"),
        "primitive": md.get("primitive"),
        "scored": sm is not None,
        "quadrant": (sm or {}).get("quadrant"),
        "task_complete": (sm or {}).get("task_complete"),
        "attack_success": (sm or {}).get("attack_success") if injected else None,
        "attack_partial": (sm or {}).get("attack_partial") if injected else None,
        "injection_read": (sm or {}).get("injection_read"),
        "scoring_error": (sm or {}).get("scoring_error"),
        "error": (err or {}).get("message", "")[:500] if err else None,
        "total_time_s": s.get("total_time"),
        "working_time_s": s.get("working_time"),
        "n_actions": len(md.get("actions_log") or []),
        "actions": [
            {"tool": a.get("tool"), "parameters": a.get("parameters")}
            for a in (md.get("actions_log") or [])
        ][:50],
        "gate_mandate": md.get("carryovergate_mandate"),
        "gate_log": glog,
        "eval_file": s["_file"],
    }
