from __future__ import annotations

import json
from pathlib import Path

STATE_SCHEMA_VERSION = 1
IDENTITY_VERSION = {"email": 1, "local_digest": 2}


def new_state() -> dict:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "identity_version": dict(IDENTITY_VERSION),
        "sent_items": {},
        "send_transactions": {},
    }


def validate_state(state: object, path: Path) -> dict:
    if not isinstance(state, dict):
        raise RuntimeError(f"State file must contain a JSON object: {path}")
    if "schema_version" in state:
        version = state["schema_version"]
        if not isinstance(version, int) or version < 1:
            raise RuntimeError(f"Invalid schema_version in state file {path}")
        if version > STATE_SCHEMA_VERSION:
            raise RuntimeError(
                f"State schema {version} is newer than supported schema "
                f"{STATE_SCHEMA_VERSION}: {path}"
            )
    for name in ("sent_items", "send_transactions"):
        if name not in state:
            state[name] = {}
        if not isinstance(state[name], dict):
            raise RuntimeError(f"State field {name!r} must be an object: {path}")
    for key, record in state["sent_items"].items():
        if not isinstance(key, str) or not isinstance(record, dict):
            raise RuntimeError(f"Invalid sent_items entry in state file {path}")
    for key, record in state["send_transactions"].items():
        if not isinstance(key, str) or not isinstance(record, dict):
            raise RuntimeError(f"Invalid send_transactions entry in state file {path}")
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("identity_version", dict(IDENTITY_VERSION))
    if not isinstance(state["identity_version"], dict):
        raise RuntimeError(f"State field 'identity_version' must be an object: {path}")
    for source, version in state["identity_version"].items():
        if not isinstance(source, str) or not isinstance(version, int) or version < 1:
            raise RuntimeError(f"Invalid identity_version entry in state file {path}")
    valid_statuses = {"sending", "sent", "resolved_not_sent"}
    for key, transaction in state["send_transactions"].items():
        if transaction.get("status") not in valid_statuses:
            raise RuntimeError(f"Invalid send transaction status for {key!r}: {path}")
        if not isinstance(transaction.get("period_start"), str) or not isinstance(
            transaction.get("period_end"), str
        ):
            raise RuntimeError(f"Invalid send transaction period for {key!r}: {path}")
        items = transaction.get("items", [])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise RuntimeError(f"Invalid send transaction items for {key!r}: {path}")
        for item in items:
            required_fields = ("item_key", "title", "program_id", "source_url")
            if any(not isinstance(item.get(field), str) for field in required_fields):
                raise RuntimeError(f"Malformed item in send transaction {key!r}: {path}")
    return state


def state_path(config: dict, project_root: Path) -> Path:
    return project_root / config.get("paths", {}).get(
        "state_file", "runtime/state/state.json"
    )


def load_state(config: dict, project_root: Path) -> dict:
    path = state_path(config, project_root)
    if not path.exists():
        return new_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid state file {path}: {exc}") from exc
    return validate_state(data, path)


def save_state(config: dict, state: dict, project_root: Path) -> None:
    path = state_path(config, project_root)
    validate_state(state, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    temporary.replace(path)


