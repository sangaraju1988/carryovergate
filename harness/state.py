"""Persistent agent state: a memory file + a scheduled-task list on disk.

The file holds each entry's content and its derivation record exactly as the
store wrote them. Sessions load it fresh; the gate re-checks at re-fire time.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from gate import DerivationRecord, LineageStore, SourceChannel


def build_state(tasks: dict, scenario: dict) -> dict:
    """Store base + planted entries through the gate's store (round 0), return
    the on-disk state dict. Tampering/deletion is applied to the persisted
    file afterwards, as an attacker with file access would."""
    store = LineageStore(approved_sources=tasks.get("approved_sources", ["calendar.example"]))
    meta: Dict[str, dict] = {}
    memory_ids: List[str] = []
    schedule_ids: List[str] = []

    def put(e: dict, where: str):
        store.add(e["id"], e["content"], SourceChannel(e["source_channel"]), e["author"],
                  e.get("parents", []))
        meta[e["id"]] = {k: v for k, v in e.items() if k not in ("content",)}
        meta[e["id"]]["where"] = where
        if where == "memory":
            memory_ids.append(e["id"])
        elif where == "schedule":
            schedule_ids.append(e["id"])

    for e in tasks["base"]["memory"]:
        put(e, "memory")
    for e in tasks["base"]["schedule"]:
        put(e, "support" if e.get("role") == "support" else "schedule")
    for e in scenario["planted"]:
        put(e, e["where"])

    entries = {
        eid: {"content": se.content, "record": se.record.to_dict()}
        for eid, se in store.entries.items()
    }
    # post-storage tampering of the persisted file
    for e in scenario["planted"]:
        if "tamper" in e:
            entries[e["id"]]["content"] = e["tamper"]
        if e.get("delete_after_store"):
            entries.pop(e["id"])
    return {"entries": entries, "meta": meta, "memory": memory_ids, "schedule": schedule_ids}


def save(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=1, sort_keys=True))


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def load_store(state: dict) -> LineageStore:
    store = LineageStore(approved_sources=["calendar.example"])
    for eid, e in state["entries"].items():
        store.load(eid, e["content"], DerivationRecord.from_dict(e["record"]))
    return store
