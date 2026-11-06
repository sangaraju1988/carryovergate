"""Deterministic "instruction-like content" detector (spec §3, class-4 row).

Frozen for v0.1 before the pilot ran: pattern list below is policy, not a
tunable. Changing it requires bumping POLICY_VERSION and re-running.
Stdlib only; no model calls.
"""
from __future__ import annotations

import re
from typing import List

_ACTION_VERBS = (
    r"send|forward|add|register|delete|remove|transfer|refund|approve|grant|merge|deploy|"
    r"update|change|set|pay|release|email|share|create|revoke|trigger|reply|resolve|"
    r"cc|bcc|include|wire|upload|post|publish|disable|enable|rotate|close|escalate"
)

_PATTERNS = [
    # classic override phrasing
    r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instructions?|previous|above|prior|rules?|policy)\b",
    # obligations addressed to the reader/agent
    r"\byou (must|should|need to|are required to|have to|will need to)\b",
    r"\b(make sure|be sure|remember|don'?t forget|do not forget) (to|you|that)\b",
    # polite imperatives with an action verb
    rf"\b(please|kindly)\s+(\w+\s+){{0,2}}({_ACTION_VERBS})\b",
    rf"\b(could|can|would|will) you\s+(please\s+)?(also\s+)?({_ACTION_VERBS})\b",
    # redirections
    rf"\b(instead|rather than)\b.{{0,60}}\b({_ACTION_VERBS}|use)\b",
    # messages posing as system/agent directives
    r"\b(system|assistant|agent|ai|admin)\s*(note|instruction|message|override|directive|notice)s?\b",
    r"\bnote to (the )?(assistant|agent|ai|model|bot)\b",
    r"\bnew (instructions?|procedure|process|policy|rule)\b",
    r"\b(when|whenever|if) (you|the agent|the assistant)\b",
    # persistence / re-fire phrasing (latent + autonomous channels)
    r"\b(at|on) (the )?(start|beginning) of (every|each|any) (session|run|conversation|day)\b",
    rf"\b(always|from now on|going forward|every time|each time)\b.{{0,60}}\b({_ACTION_VERBS}|use)\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _PATTERNS]


def instruction_hits(text: str) -> List[str]:
    """Return the patterns that match (empty list = not instruction-like)."""
    if not text:
        return []
    return [p.pattern for p in _COMPILED if p.search(text)]


def is_instruction_like(text: str) -> bool:
    return bool(instruction_hits(text))
