"""Lineage store: classifies authority at store time, verifies chains at re-fire time."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, Optional, Tuple

from .record import (
    Authority,
    DerivationRecord,
    SourceChannel,
    USER_AUTHOR,
    POLICY_VERSION,
    derivation_hash,
)


@dataclass
class StoredEntry:
    content: str
    record: DerivationRecord


class LineageStore:
    """In-memory map entry_id -> (content, derivation record).

    `approved_sources` is the set of authors/sources the user explicitly
    approved (class 2). It is configuration, not something the agent can write.
    """

    def __init__(self, approved_sources: Iterable[str] = ()):
        self.entries: Dict[str, StoredEntry] = {}
        self.approved_sources: FrozenSet[str] = frozenset(approved_sources)

    # ---- store time -------------------------------------------------------
    def classify(
        self,
        source_channel: SourceChannel,
        author: str,
        parent_links: Tuple[str, ...],
    ) -> Authority:
        """Authority class computed from channel, author and parents (spec §3)."""
        if source_channel in (SourceChannel.USER_MESSAGE, SourceChannel.SCHEDULED_TASK_CREATOR) \
                and author == USER_AUTHOR:
            return Authority.USER_AUTHORED
        if source_channel in (SourceChannel.RETRIEVED_TOOL_CONTENT, SourceChannel.IMPORTED_FILE):
            if author in self.approved_sources:
                return Authority.USER_APPROVED
            return Authority.UNTRUSTED
        if source_channel in (SourceChannel.AGENT_OUTPUT, SourceChannel.SCHEDULED_TASK_CREATOR):
            # Agent-written entry (or a schedule the agent created): authority is
            # inherited from parents. Needs >=1 parent, all present, all class <=3.
            if not parent_links:
                return Authority.UNTRUSTED
            worst = Authority.USER_AUTHORED
            for pid in parent_links:
                parent = self.entries.get(pid)
                if parent is None:
                    return Authority.UNTRUSTED
                worst = max(worst, parent.record.authority)
            if worst >= Authority.UNTRUSTED:
                return Authority.UNTRUSTED
            return Authority.AGENT_DERIVED
        # user_message from a non-user author (e.g. pasted third-party text)
        return Authority.UNTRUSTED

    def add(
        self,
        entry_id: str,
        content: str,
        source_channel: SourceChannel,
        author: str,
        parent_links: Iterable[str] = (),
    ) -> DerivationRecord:
        if entry_id in self.entries:
            raise ValueError(f"duplicate entry_id {entry_id!r}")
        parents = tuple(parent_links)
        parent_hashes = tuple(
            self.entries[p].record.derivation_hash if p in self.entries else "missing:" + p
            for p in parents
        )
        rec = DerivationRecord(
            entry_id=entry_id,
            source_channel=source_channel,
            author=author,
            derivation_hash=derivation_hash(content, parent_hashes),
            parent_links=parents,
            policy_version=POLICY_VERSION,
            authority=self.classify(source_channel, author, parents),
        )
        self.entries[entry_id] = StoredEntry(content=content, record=rec)
        return rec

    def load(self, entry_id: str, content: str, record: DerivationRecord) -> None:
        """Load a persisted entry as-is (no reclassification): re-fire checks it."""
        self.entries[entry_id] = StoredEntry(content=content, record=record)

    # ---- re-fire time -----------------------------------------------------
    def verify_chain(self, entry_id: str, _seen: Optional[set] = None) -> Optional[str]:
        """Return None if the chain is intact, else a reason string."""
        # `_seen` is kept for call compatibility but unused: the walk tracks the
        # current recursion path (cycle detection) separately from nodes already
        # verified (a shared ancestor reached from another branch is not a cycle).
        return self._verify(entry_id, path=set(), verified=set())

    def _verify(self, entry_id: str, path: set, verified: set) -> Optional[str]:
        if entry_id in path:
            return f"cycle at {entry_id}"
        if entry_id in verified:
            return None
        e = self.entries.get(entry_id)
        if e is None:
            return f"missing entry {entry_id}"
        parent_hashes = []
        for p in e.record.parent_links:
            pe = self.entries.get(p)
            if pe is None:
                return f"missing parent {p} of {entry_id}"
            parent_hashes.append(pe.record.derivation_hash)
        if derivation_hash(e.content, tuple(parent_hashes)) != e.record.derivation_hash:
            return f"hash mismatch on {entry_id}"
        path.add(entry_id)
        for p in e.record.parent_links:
            why = self._verify(p, path, verified)
            if why:
                return why
        path.discard(entry_id)
        verified.add(entry_id)
        return None

    def recheck_authority(self, entry_id: str) -> Authority:
        """Re-derive the class now; never better than what was stored."""
        e = self.entries[entry_id]
        r = e.record
        now = self.classify(r.source_channel, r.author, r.parent_links)
        return max(now, r.authority)
