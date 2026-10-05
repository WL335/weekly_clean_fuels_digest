import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weekly_clean_fuels_digest.main import resolve_pending_transaction
from weekly_clean_fuels_digest.state_store import load_state, save_state


def test_legacy_state_load_preserves_keys_without_migration(tmp_path):
    config = {"paths": {"state_file": "state/state.json"}}
    path = tmp_path / "state" / "state.json"
    path.parent.mkdir()
    original = {
        "sent_items": {
            "legacy-email-key": {
                "sent_at": "2026-09-25T09:00:00-06:00",
                "title": "Example email",
                "program_id": "washington_cfs",
                "source_url": "https://example.com/news",
            }
        }
    }
    path.write_text(json.dumps(original), encoding="utf-8")

    state = load_state(config, tmp_path)

    assert state["sent_items"] == original["sent_items"]
    assert state["schema_version"] == 1
    assert state["identity_version"] == {"email": 1, "local_digest": 2}
    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_state_rejects_malformed_sent_items(tmp_path):
    config = {"paths": {"state_file": "state.json"}}
    path = tmp_path / "state.json"
    path.write_text('{"sent_items": []}', encoding="utf-8")

    with pytest.raises(RuntimeError, match="sent_items"):
        load_state(config, tmp_path)


def test_state_rejects_malformed_transaction_item(tmp_path):
    config = {"paths": {"state_file": "state.json"}}
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "send_transactions": {
                    "wcf-bad": {
                        "status": "sending",
                        "period_start": "2026-09-25T00:00:00-06:00",
                        "period_end": "2026-10-02T00:00:00-06:00",
                        "items": [{"title": "missing required identity fields"}],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Malformed item"):
        load_state(config, tmp_path)


def test_state_rejects_a_timezone_naive_transaction_timestamp(tmp_path):
    config = {"paths": {"state_file": "state.json"}}
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "send_transactions": {
                    "wcf-bad": {
                        "status": "sent",
                        "period_start": "2026-09-25T00:00:00",
                        "period_end": "2026-10-02T00:00:00-06:00",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="period_start"):
        load_state(config, tmp_path)


def test_state_rejects_a_timezone_naive_last_run(tmp_path):
    config = {"paths": {"state_file": "state.json"}}
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "last_run": {
                    "period_start": "2026-09-25T00:00:00-06:00",
                    "period_end": "2026-10-02T00:00:00",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="last_run.period_end"):
        load_state(config, tmp_path)


def test_resolve_pending_as_sent_records_item_suppression():
    state = {
        "sent_items": {},
        "send_transactions": {
            "wcf-pending": {
                "status": "sending",
                "items": [
                    {
                        "item_key": "item-1",
                        "title": "Example",
                        "program_id": "bc_lcfs",
                        "source_url": "https://example.com/bc",
                        "source_kind": "local_digest",
                        "source_item_id": "RLCF-009:20260925",
                    }
                ],
            }
        },
    }

    resolve_pending_transaction(state, "wcf-pending", "sent", "America/Regina")

    assert state["send_transactions"]["wcf-pending"]["status"] == "sent"
    assert "item-1" in state["sent_items"]
    assert state["sent_items"]["item-1"]["source_kind"] == "local_digest"


def test_resolve_pending_as_not_sent_is_retryable():
    state = {
        "sent_items": {},
        "send_transactions": {"wcf-pending": {"status": "sending", "items": []}},
    }

    resolve_pending_transaction(state, "wcf-pending", "not-sent", "America/Regina")

    assert state["send_transactions"]["wcf-pending"]["status"] == "resolved_not_sent"
    assert not state["sent_items"]
