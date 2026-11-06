"""carryovergate: derivation-authority re-fire gate (stdlib only)."""
from .record import Authority, DerivationRecord, SourceChannel, POLICY_VERSION, USER_AUTHOR
from .store import LineageStore
from .decide import Action, Decision, GateResult, decide, in_mandate, PROVENANCE_LABEL
from .instruction import is_instruction_like, instruction_hits
from .calls import action_kind, check_tool_call, distinctive_tokens, trace_withheld

__all__ = [
    "Authority", "DerivationRecord", "SourceChannel", "POLICY_VERSION", "USER_AUTHOR",
    "LineageStore", "Action", "Decision", "GateResult", "decide", "in_mandate",
    "PROVENANCE_LABEL", "is_instruction_like", "instruction_hits", "action_kind",
    "check_tool_call", "distinctive_tokens", "trace_withheld",
]
