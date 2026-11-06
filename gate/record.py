"""Derivation records and authority classes (spec §3).

A derivation record is written at store time by the store, never by the
agent's later account of an entry. Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from enum import Enum, IntEnum
from typing import Tuple

POLICY_VERSION = "carryovergate-policy-v0.1"


class Authority(IntEnum):
    """Authority classes. Lower number = more authority."""

    USER_AUTHORED = 1   # written by the user
    USER_APPROVED = 2   # from a source the user explicitly approved
    AGENT_DERIVED = 3   # agent output derived only from 1/2/3 entries, chain intact
    UNTRUSTED = 4       # web/tool content, third-party text, unknown import, broken chain


class SourceChannel(str, Enum):
    USER_MESSAGE = "user_message"
    AGENT_OUTPUT = "agent_output"
    RETRIEVED_TOOL_CONTENT = "retrieved_tool_content"
    SCHEDULED_TASK_CREATOR = "scheduled_task_creator"
    IMPORTED_FILE = "imported_file"


USER_AUTHOR = "user"


def derivation_hash(content: str, parent_hashes: Tuple[str, ...]) -> str:
    """sha256 over the entry content plus its parents' hashes (in link order)."""
    h = hashlib.sha256()
    h.update(content.encode("utf-8"))
    for p in parent_hashes:
        h.update(b"\x00")
        h.update(p.encode("ascii"))
    return h.hexdigest()


@dataclass(frozen=True)
class DerivationRecord:
    entry_id: str
    source_channel: SourceChannel
    author: str
    derivation_hash: str
    parent_links: Tuple[str, ...] = field(default_factory=tuple)
    policy_version: str = POLICY_VERSION
    authority: Authority = Authority.UNTRUSTED

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source_channel"] = self.source_channel.value
        d["authority"] = int(self.authority)
        d["parent_links"] = list(self.parent_links)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "DerivationRecord":
        return cls(
            entry_id=d["entry_id"],
            source_channel=SourceChannel(d["source_channel"]),
            author=d["author"],
            derivation_hash=d["derivation_hash"],
            parent_links=tuple(d.get("parent_links", ())),
            policy_version=d.get("policy_version", POLICY_VERSION),
            authority=Authority(int(d["authority"])),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)
