"""Mock side-effecting tools. They only log; nothing leaves the machine."""
from __future__ import annotations

TOOLS = {
    "email.send": {
        "description": "Send an email.",
        "params": {"to": "string", "subject": "string", "body": "string", "cc": "string"},
        "required": ["to", "subject", "body"],
    },
    "payments.transfer": {
        "description": "Transfer money to an account.",
        "params": {"account": "string", "amount": "number", "memo": "string"},
        "required": ["account", "amount"],
    },
    "files.backup": {
        "description": "Back up a folder.",
        "params": {"path": "string"},
        "required": ["path"],
    },
    "files.delete": {
        "description": "Delete a folder.",
        "params": {"path": "string"},
        "required": ["path"],
    },
    "share.publish": {
        "description": "Publish a folder to a sharing destination.",
        "params": {"path": "string", "destination": "string"},
        "required": ["path", "destination"],
    },
}


def fn_name(tool: str) -> str:
    return tool.replace(".", "_")


def tool_from_fn(name: str) -> str:
    for t in TOOLS:
        if fn_name(t) == name:
            return t
    return name


def ollama_tool_schemas() -> list:
    out = []
    for t, spec in TOOLS.items():
        props = {k: {"type": v} for k, v in spec["params"].items()}
        props["source_entry"] = {"type": "string",
                                 "description": "id of the memory entry or scheduled task you are acting on"}
        out.append({"type": "function", "function": {
            "name": fn_name(t), "description": spec["description"],
            "parameters": {"type": "object", "properties": props, "required": spec["required"]},
        }})
    return out
