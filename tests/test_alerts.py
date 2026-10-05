import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weekly_clean_fuels_digest import alerts


class FakeCompleted:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


class RecordingRunner:
    """Stands in for subprocess.run so no real notification is ever sent."""

    def __init__(self, returncode=0, stderr="", raises=None):
        self.calls = []
        self.returncode = returncode
        self.stderr = stderr
        self.raises = raises

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if self.raises is not None:
            raise self.raises
        return FakeCompleted(self.returncode, self.stderr)


def test_settings_defaults_and_overrides():
    defaults = alerts.AlertSettings.from_config({})
    assert defaults.popup_enabled is True
    assert defaults.desktop_marker_enabled is True
    assert defaults.event_log_enabled is True
    assert defaults.grace_hours == 6.0

    overridden = alerts.AlertSettings.from_config(
        {"alerts": {"popup_enabled": False, "grace_hours": 2}}
    )
    assert overridden.popup_enabled is False
    assert overridden.event_log_enabled is True
    assert overridden.grace_hours == 2.0


def test_desktop_marker_writes_a_readable_file(tmp_path):
    stamp = datetime(2026, 10, 3, 9, 0, tzinfo=ZoneInfo("America/Regina"))

    outcome = alerts.write_desktop_marker(
        "Digest failed", "Stage: rendering", stamp, directory=tmp_path
    )

    assert outcome.ok is True
    body = (tmp_path / "Weekly Digest ALERT 2026-10-03.txt").read_text(encoding="utf-8")
    assert "Digest failed" in body
    assert "Stage: rendering" in body


def test_popup_reports_a_failed_delivery(monkeypatch):
    runner = RecordingRunner(returncode=1, stderr="no session")
    monkeypatch.setattr(alerts.shutil, "which", lambda name: "C:/Windows/System32/msg.exe")

    outcome = alerts.send_popup("digest failed", runner=runner)

    assert outcome.ok is False
    assert "no session" in outcome.detail
    assert runner.calls[0][0][0].endswith("msg.exe")
    assert "*" in runner.calls[0][0]


def test_missing_tools_are_reported_without_raising(monkeypatch):
    monkeypatch.setattr(alerts.shutil, "which", lambda name: None)

    assert alerts.send_popup("text", runner=RecordingRunner()).ok is False
    assert alerts.write_event_log("text", runner=RecordingRunner()).ok is False


def test_popup_falls_back_to_a_powershell_message_box(monkeypatch):
    runner = RecordingRunner()
    monkeypatch.setattr(
        alerts.shutil,
        "which",
        lambda name: "powershell.exe" if "powershell" in name else None,
    )

    outcome = alerts.send_popup("digest failed", runner=runner)

    assert outcome.ok is True
    assert "msg.exe is not installed" in outcome.detail
    command = runner.calls[0][0]
    assert command[0] == "powershell.exe"
    assert "MessageBox" in command[-1]
    assert "digest failed" in command[-1]


def test_popup_escapes_apostrophes_for_powershell(monkeypatch):
    runner = RecordingRunner()
    monkeypatch.setattr(
        alerts.shutil,
        "which",
        lambda name: "powershell.exe" if "powershell" in name else None,
    )

    alerts.send_popup("the operator's digest failed", runner=runner)

    assert "operator''s" in runner.calls[0][0][-1]


def test_a_timed_out_popup_without_display_proof_is_not_a_notification(monkeypatch, tmp_path):
    """A stalled process proves nothing: only the proof file shows it was displayed."""

    def timing_out(command, **kwargs):
        raise alerts.subprocess.TimeoutExpired(command, alerts.POPUP_TIMEOUT_SECONDS)

    monkeypatch.setattr(
        alerts.shutil,
        "which",
        lambda name: "powershell.exe" if "powershell" in name else None,
    )
    monkeypatch.setattr(alerts, "popup_proof_path", lambda: tmp_path / "popup.marker")

    outcome = alerts.send_popup("digest failed", runner=timing_out)

    assert outcome.ok is False
    assert "before the dialog was displayed" in outcome.detail


def test_a_timed_out_popup_with_display_proof_counts_as_shown(monkeypatch, tmp_path):
    proof = tmp_path / "popup.marker"

    def timing_out(command, **kwargs):
        # The script reached the point of displaying the dialog, then hung.
        proof.write_text("shown", encoding="utf-8")
        raise alerts.subprocess.TimeoutExpired(command, alerts.POPUP_TIMEOUT_SECONDS)

    monkeypatch.setattr(
        alerts.shutil,
        "which",
        lambda name: "powershell.exe" if "powershell" in name else None,
    )
    monkeypatch.setattr(alerts, "popup_proof_path", lambda: proof)

    outcome = alerts.send_popup("digest failed", runner=timing_out)

    assert outcome.ok is True
    assert "not acknowledged" in outcome.detail


def test_event_log_uses_the_project_source_and_id(monkeypatch):
    runner = RecordingRunner()
    monkeypatch.setattr(
        alerts.shutil, "which", lambda name: "C:/Windows/System32/eventcreate.exe"
    )

    outcome = alerts.write_event_log("digest failed", runner=runner)

    assert outcome.ok is True
    command = runner.calls[0][0]
    assert alerts.EVENT_LOG_SOURCE in command
    assert str(alerts.EVENT_LOG_ID) in command


def test_report_problem_records_without_notifying(tmp_path):
    outcomes = alerts.report_problem(
        project_root=tmp_path,
        title="Digest failed",
        message="Stage: rendering",
        settings=alerts.AlertSettings(),
        notify_operator=False,
    )

    assert [outcome.channel for outcome in outcomes] == ["failure_record"]
    payload = json.loads(
        (tmp_path / "runtime" / "state" / "last_failure.json").read_text(encoding="utf-8")
    )
    assert payload["title"] == "Digest failed"
    assert payload["context"] == {}


def test_report_failure_returns_the_exit_code_and_tries_every_channel(
    tmp_path, monkeypatch
):
    runner = RecordingRunner()
    monkeypatch.setattr(alerts.shutil, "which", lambda name: "C:/tool.exe")
    desktop = tmp_path / "desktop"
    desktop.mkdir()

    code = alerts.report_failure(
        exc=RuntimeError("boom"),
        stage="rendering",
        settings=alerts.AlertSettings(),
        project_root=tmp_path,
        mode="send",
        exit_code=1,
        notify_operator=True,
        subprocess_runner=runner,
        marker_directory=desktop,
    )

    assert code == 1
    record = json.loads(
        (tmp_path / "runtime" / "state" / "last_failure.json").read_text(encoding="utf-8")
    )
    assert record["context"]["stage"] == "rendering"
    assert record["message"].startswith("Stage: rendering")
    assert list(desktop.glob("Weekly Digest ALERT *.txt"))
    assert len(runner.calls) == 2  # popup plus event log


def test_clear_failure_record_is_tolerant_of_a_missing_file(tmp_path):
    alerts.clear_failure_record(tmp_path)

    path = alerts.failure_record_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    alerts.clear_failure_record(tmp_path)

    assert not path.exists()


def test_notified_ignores_the_evidence_record():
    """The failure record preserves evidence; it is not a notification."""
    assert alerts.notified([alerts.AlertOutcome("failure_record", True, "path")]) is False
    assert alerts.notified([alerts.AlertOutcome("popup", False, "no session")]) is False
    assert (
        alerts.notified(
            [
                alerts.AlertOutcome("failure_record", True, "path"),
                alerts.AlertOutcome("desktop_marker", True, "path"),
            ]
        )
        is True
    )


def write_digest_config(path: Path) -> None:
    """Minimal valid configuration with every notification channel disabled."""
    path.write_text(
        yaml.safe_dump(
            {
                "mailbox": {"sender": "a@example.com", "recipient": "a@example.com"},
                "schedule": {"timezone": "America/Regina"},
                "ai": {"model": "gpt-5-nano"},
                "programs": [
                    {
                        "id": "p1",
                        "name": "Program One",
                        "country": "United States",
                        "sender": "s@example.com",
                        "country_order": 1,
                        "program_order": 1,
                    }
                ],
                "alerts": {
                    "popup_enabled": False,
                    "desktop_marker_enabled": False,
                    "event_log_enabled": False,
                },
            }
        ),
        encoding="utf-8",
    )


def test_a_provider_credential_error_is_reported(tmp_path, monkeypatch):
    """RefreshError is none of OSError/ValueError/RuntimeError.

    It used to escape the run handler entirely, which left a Gmail credential
    failure as a bare traceback with no notification.
    """
    from google.auth.exceptions import RefreshError

    from weekly_clean_fuels_digest import main as digest_main

    config_path = tmp_path / "config.yaml"
    write_digest_config(config_path)
    monkeypatch.setattr(digest_main, "ROOT", tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        digest_main,
        "parse_args",
        lambda: argparse.Namespace(
            config=config_path,
            send=True,
            start=None,
            end=None,
            include_processed=False,
            resolve_pending=None,
            resolution=None,
        ),
    )

    def raise_refresh_error(config):
        raise RefreshError("invalid_client: unauthorized")

    monkeypatch.setattr(digest_main, "gmail_service", raise_refresh_error)

    code = digest_main.main()

    assert code == 1
    record = json.loads(
        (tmp_path / "runtime" / "state" / "last_failure.json").read_text(encoding="utf-8")
    )
    assert record["context"]["stage"] == "Gmail connection"
    assert record["context"]["mode"] == "send"
    assert "RefreshError" in record["message"]
