"""carryovergate as a defense condition inside the Task-Tampering defense runner.

The benchmark (github.com/amazon-science/task-tampering-prompt-injection,
CC BY-NC 4.0) is used as an installed dependency. No benchmark code is copied
here. We install the gate by wrapping `prompt_injection_benchmark.core.solver.
agent_tools`, which the benchmark's own `DefenseEvalSolver` calls on the raw
MCP tool list right after injections are configured. So:

- gate OFF = the benchmark runner, unmodified.
- gate ON  = the same runner, the same base defense, with every agent-facing
  tool wrapped by the gate (innermost: base defenses like spotlight/sandwich
  wrap outside it).

Mapping of the benchmark (single session, injections in tool-read content) onto
the gate's re-fire model, fixed before the pilot (see PREREGISTRATION.md):
- The user's request is a class-1 entry (`user_request`).
- Every tool result is recalled content: each long string leaf is stored as a
  class-4 entry (source_channel=retrieved_tool_content, author = the nearest
  author-like field). The recall check is the class-4 READ row: instruction-
  like leaves are withheld (BLOCK / quarantine), the rest is shown with the
  provenance label.
- Every agent tool call is an agent_output entry whose control parent is
  `user_request` and whose data parents are withheld leaves its arguments trace
  to. Class 3 side effects need the mandate; class 4 side effects are blocked.
- Mandate: the case's `required_tools` field (the tools the benign task needs).
  This stands in for a user who pre-approved exactly their task's tools. It is
  case metadata, not attack metadata, but it is privileged information a real
  deployment would have to get from the user. Flagged in README/REPORT.
"""
from __future__ import annotations

import json
import time
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gate import (
    Action, Decision, LineageStore, PROVENANCE_LABEL, SourceChannel, USER_AUTHOR,
    action_kind, check_tool_call, decide,
)

LEAF_MIN_CHARS = 40
AUTHOR_KEYS = ("author", "from", "sender", "user", "username", "created_by", "requester",
               "buyer", "seller", "submitted_by", "owner")
QUARANTINE_MARK = "[carryovergate: untrusted entry {eid} withheld — instruction-like content]"


class GateSession:
    """Per-sample gate state."""

    def __init__(self, user_task: str, mandate: frozenset, case_id: str):
        self.store = LineageStore()
        self.store.add("user_request", user_task, SourceChannel.USER_MESSAGE, USER_AUTHOR)
        self.mandate = mandate
        self.case_id = case_id
        self.withheld: List[str] = []
        self.visible_text = user_task
        self.n_calls = 0
        self.log: List[dict] = []

    # ---- recall side ------------------------------------------------------
    def gate_result_text(self, text: str, call_id: str) -> str:
        try:
            data = json.loads(text)
            is_json = True
        except (ValueError, TypeError):
            data, is_json = None, False
        if is_json and isinstance(data, (dict, list)):
            new = self._walk(data, call_id, "", None)
            body = json.dumps(new, ensure_ascii=False, indent=1)
        else:
            paras = text.split("\n\n")
            out = []
            for i, p in enumerate(paras):
                out.append(self._leaf(p, f"{call_id}#p{i}", None))
            body = "\n\n".join(out)
        return f"[carryovergate: tool content, {PROVENANCE_LABEL}]\n{body}"

    def _walk(self, v: Any, call_id: str, path: str, author: Optional[str]) -> Any:
        if isinstance(v, dict):
            a = author
            for k in AUTHOR_KEYS:
                if isinstance(v.get(k), str):
                    a = v[k]
                    break
            return {k: self._walk(x, call_id, f"{path}/{k}", a) for k, x in v.items()}
        if isinstance(v, list):
            return [self._walk(x, call_id, f"{path}/{i}", author) for i, x in enumerate(v)]
        if isinstance(v, str):
            return self._leaf(v, f"{call_id}{path}", author)
        return v

    def _leaf(self, s: str, eid: str, author: Optional[str]) -> str:
        if len(s) < LEAF_MIN_CHARS:
            self.visible_text += "\n" + s
            return s
        if eid in self.store.entries:  # same path seen twice in one result
            eid = f"{eid}~{len(self.store.entries)}"
        self.store.add(eid, s, SourceChannel.RETRIEVED_TOOL_CONTENT, author or "unknown",
                       parent_links=["user_request"])
        r = decide(self.store, eid, Action.READ)
        self._log("recall", r, extra={"chars": len(s), "text": s})
        if r.decision.executes:
            self.visible_text += "\n" + s
            return s
        self.withheld.append(eid)
        return QUARANTINE_MARK.format(eid=eid)

    # ---- action side ------------------------------------------------------
    def check_call(self, tool: str, action: Optional[str], kwargs: Dict[str, Any]):
        self.n_calls += 1
        call_id = f"call{self.n_calls}"
        full = f"{tool}.{action}" if action else tool
        t0 = time.perf_counter_ns()
        r, parents = check_tool_call(
            self.store, call_id, full, kwargs, control_parent="user_request",
            mandate=self.mandate, withheld_ids=self.withheld,
            visible_text=self.visible_text, action=action_kind(tool, action),
        )
        total = time.perf_counter_ns() - t0
        self._log("call", r, extra={"tool": full, "data_parents": parents,
                                    "check_ns_incl_record": total})
        return call_id, r

    def _log(self, kind: str, r, extra: dict):
        d = r.to_dict()
        d.pop("record", None)
        d["hits"] = [h[:60] for h in d.pop("instruction_hits")]
        d["kind"] = kind
        d.update(extra)
        self.log.append(d)


_SESSIONS: Dict[str, "GateSession"] = {}


def _key(state) -> str:
    return f"{state.uuid}:{state.sample_id}:{state.epoch}"


def _text_of(result) -> Tuple[str, str]:
    if isinstance(result, str):
        return result, "str"
    if isinstance(result, list) and result and all(hasattr(x, "text") for x in result):
        return "\n".join(x.text for x in result), "list"
    return "", "other"


def gate_wrap(tool_fn, tool_name: str):
    @wraps(tool_fn)
    async def wrapped(**kwargs):
        from inspect_ai.solver._task_state import sample_state
        from inspect_ai._util.content import ContentText

        state = sample_state()
        gs: GateSession = _SESSIONS[_key(state)]
        call_id, r = gs.check_call(tool_name, kwargs.get("action"), kwargs)
        state.metadata["carryovergate_log"] = gs.log
        if not r.decision.executes:
            if r.decision == Decision.ASK_USER:
                msg = (f"[carryovergate] {tool_name}.{kwargs.get('action')} needs user approval "
                       f"(outside the pre-approved mandate). No user is available, so it was "
                       f"NOT executed.")
            else:
                msg = (f"[carryovergate] {tool_name}.{kwargs.get('action')} BLOCKED: {r.reason}. "
                       f"Not executed.")
            return msg
        result = await tool_fn(**kwargs)
        text, shape = _text_of(result)
        if shape == "other":
            return result
        gated = gs.gate_result_text(text, call_id)
        state.metadata["carryovergate_log"] = gs.log
        return [ContentText(text=gated)] if shape == "list" else gated
    return wrapped


def load_mandate(variations_dir: Path, env: str, case_id: str) -> frozenset:
    data = json.loads((variations_dir / env / f"{case_id}.json").read_text())
    tc = data["test_cases"][0]
    return frozenset(tc.get("required_tools", []))


def install(variations_dir: Path) -> None:
    """Patch the benchmark so DefenseEvalSolver hands the agent gated tools."""
    import prompt_injection_benchmark.core.solver as core_solver
    from inspect_ai.solver._task_state import sample_state
    from inspect_ai.tool._tool_def import ToolDef

    original = core_solver.agent_tools
    if getattr(original, "_carryovergate", False):
        return

    def gated_agent_tools(tools: list) -> list:
        kept = original(tools)
        state = sample_state()
        if state is None:
            return kept
        md = state.metadata
        mandate = load_mandate(variations_dir, md["environment"], md["case_id"])
        _SESSIONS[_key(state)] = GateSession(state.input_text, mandate, md["case_id"])
        md["carryovergate_mandate"] = sorted(mandate)
        md["carryovergate_log"] = []
        out = []
        for t in kept:
            td = t if isinstance(t, ToolDef) else ToolDef(t)
            td.tool = gate_wrap(td.tool, td.name)
            out.append(td)
        return out

    gated_agent_tools._carryovergate = True
    core_solver.agent_tools = gated_agent_tools
