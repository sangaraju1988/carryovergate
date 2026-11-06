"""Tool-call derivation: turn an agent tool call into a derivation-recorded
entry and run it through the decision table.

Interpretation fixed for v0.1 (documented in README, frozen before the pilot):
- Control parent: the entry that instructed the work (the user's request, a
  recalled memory entry, or a due scheduled task).
- Data parents: entries the call's argument values are copied from. Only
  *withheld* (quarantined/blocked) entries are linked as data parents: a class-4
  entry the gate already allowed with a provenance label is readable data, and
  copying a value out of it is part of reading it. A value is traced to a
  withheld entry only if it appears there and nowhere the agent was allowed to see.
- The call is an agent_output entry, so its class is inherited from its parents
  (3 if all parents are 1-3, else 4); the decision table then applies.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Tuple

from .decide import Action, GateResult, decide
from .record import SourceChannel
from .store import LineageStore

_READ_VERBS = re.compile(
    r"^(read|list|search|get|view|find|check|lookup|status|show|fetch|query|describe|inspect)"
    r"(_|$)",
    re.IGNORECASE,
)

# token = run of chars that can carry an identifier, address, key or URL
_TOKEN = re.compile(r"[A-Za-z0-9@._:/+\-=]{8,}")


def action_kind(tool: str, action: Optional[str] = None) -> Action:
    """READ if the action verb is a read verb, else SIDE_EFFECT (fail-closed)."""
    verb = action if action else (tool.split(".", 1)[1] if "." in tool else tool)
    return Action.READ if _READ_VERBS.match(verb or "") else Action.SIDE_EFFECT


def _strings(v: Any) -> Iterable[str]:
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _strings(x)


def distinctive_tokens(args: Dict[str, Any]) -> List[str]:
    out = []
    for s in _strings(args):
        for t in _TOKEN.findall(s):
            t = t.strip(".,:;/-")
            if len(t) >= 8 and t not in out:
                out.append(t)
    return out


def trace_withheld(
    store: LineageStore,
    args: Dict[str, Any],
    withheld_ids: Iterable[str],
    visible_text: str,
) -> List[str]:
    """Withheld entry ids that the call's argument values can only have come from."""
    toks = [t for t in distinctive_tokens(args) if t not in visible_text]
    if not toks:
        return []
    hits = []
    for eid in withheld_ids:
        e = store.entries.get(eid)
        if e is not None and any(t in e.content for t in toks):
            hits.append(eid)
    return hits


def check_tool_call(
    store: LineageStore,
    call_id: str,
    tool: str,
    args: Dict[str, Any],
    control_parent: str,
    mandate: FrozenSet[str] = frozenset(),
    withheld_ids: Iterable[str] = (),
    visible_text: str = "",
    action: Optional[Action] = None,
) -> Tuple[GateResult, List[str]]:
    """Record the call and decide. Returns (result, data_parents_linked)."""
    kind = action or action_kind(tool)
    data_parents = trace_withheld(store, args, withheld_ids, visible_text)
    content = json.dumps({"tool": tool, "args": args}, sort_keys=True, default=str)
    store.add(
        call_id,
        content,
        SourceChannel.AGENT_OUTPUT,
        author="agent",
        parent_links=[control_parent, *data_parents],
    )
    return decide(store, call_id, kind, tool=tool, mandate=mandate), data_parents
