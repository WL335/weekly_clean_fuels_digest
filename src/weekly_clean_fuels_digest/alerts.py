"""Operator notification for a failed or missing weekly digest.

The digest itself is delivered through Gmail, so a Gmail credential or API
failure cannot be reported over that same channel. Every channel here is
therefore independent of the mail transport:

``failure_record``  ``runtime/state/last_failure.json`` — always written.
``popup``           ``msg.exe`` message box — visible immediately, but it needs
                    an interactive Windows session.
``desktop_marker``  date-stamped file on the Desktop — survives a closed session
                    and a missing ``msg.exe``.
``event_log``       Windows Application log via ``eventcreate.exe`` — best
                    effort, because writing it can require elevation.

Each channel reports its own outcome, so the run log states which notifications
the operator can actually expect to have seen. Nothing in this module raises:
alerting must never turn a reported failure into a crash.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

EVENT_LOG_SOURCE = "WeeklyCleanFuelsDigest"
EVENT_LOG_ID = 991
POPUP_TEXT_LIMIT = 220
EVENT_TEXT_LIMIT = 250
COMMAND_TIMEOUT_SECONDS = 30


@dataclass
class AlertSettings:
    """Notification switches, read from the ``alerts`` configuration section."""

    popup_enabled: bool = True
    desktop_marker_enabled: bool = True
    event_log_enabled: bool = True
    grace_hours: float = 6.0

    @classmethod
    def from_config(cls, config: dict) -> "AlertSettings":
        section = config.get("alerts") or {}
        if not isinstance(section, dict):
            section = {}
        return cls(
            popup_enabled=bool(section.get("popup_enabled", True)),
            desktop_marker_enabled=bool(section.get("desktop_marker_enabled", True)),
            event_log_enabled=bool(section.get("event_log_enabled", True)),
            grace_hours=float(section.get("grace_hours", 6)),
        )


@dataclass
class AlertOutcome:
    channel: str
    ok: bool
    detail: str = ""


def one_line(text: str, limit: int | None = None) -> str:
    collapsed = " ".join(text.split())
    return collapsed if limit is None else collapsed[:limit]


def failure_record_path(project_root: Path) -> Path:
    return project_root / "runtime" / "state" / "last_failure.json"


def clear_failure_record(project_root: Path) -> None:
    """Remove the failure record after a successful run."""
    path = failure_record_path(project_root)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:  # pragma: no cover - depends on local file permissions
        logging.warning("Could not remove %s: %s", path, exc)


def desktop_directory() -> Path | None:
    """First existing Desktop directory, including OneDrive-redirected ones."""
    candidates: list[Path] = []
    profile = os.environ.get("USERPROFILE")
    if profile:
        candidates.append(Path(profile) / "Desktop")
        candidates.append(Path(profile) / "OneDrive" / "Desktop")
    candidates.append(Path.home() / "Desktop")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def write_failure_record(project_root: Path, payload: dict) -> AlertOutcome:
    path = failure_record_path(project_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(path)
    except OSError as exc:
        return AlertOutcome("failure_record", False, str(exc))
    return AlertOutcome("failure_record", True, str(path))


POPUP_TITLE = "Weekly Clean Fuels Digest"
POPUP_TIMEOUT_SECONDS = 60


def powershell_popup_command(shell: str, message: str) -> list[str]:
    """Build a WinForms message box command, used when msg.exe is unavailable."""
    safe = one_line(message, POPUP_TEXT_LIMIT).replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        f"[System.Windows.Forms.MessageBox]::Show('{safe}','{POPUP_TITLE}','OK','Warning')"
        " | Out-Null"
    )
    return [shell, "-NoProfile", "-WindowStyle", "Hidden", "-Command", script]


def send_popup(message: str, runner=subprocess.run) -> AlertOutcome:
    """Show a message box through msg.exe, or through PowerShell if it is absent.

    msg.exe is missing on some Windows editions, so the PowerShell message box is
    the fallback that keeps this channel usable on the production machine. Both
    paths are subprocess calls with a timeout: a dialog nobody dismisses must not
    hang the run.
    """
    executable = shutil.which("msg.exe") or shutil.which("msg")
    if executable:
        command = [executable, "*", "/TIME:120", one_line(message, POPUP_TEXT_LIMIT)]
        channel = "msg.exe"
    else:
        shell = shutil.which("powershell.exe") or shutil.which("powershell")
        if not shell:
            return AlertOutcome(
                "popup", False, "neither msg.exe nor powershell.exe is available"
            )
        command = powershell_popup_command(shell, message)
        channel = "PowerShell message box (msg.exe is not installed)"
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            timeout=POPUP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        # The dialog was displayed; it simply was not dismissed in time.
        return AlertOutcome(
            "popup", True, f"{channel}: shown, not acknowledged within {POPUP_TIMEOUT_SECONDS}s"
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return AlertOutcome("popup", False, str(exc))
    if completed.returncode != 0:
        return AlertOutcome(
            "popup", False, f"exit {completed.returncode}: {one_line(completed.stderr or '')}"
        )
    return AlertOutcome("popup", True, f"{channel}: acknowledged")


def write_desktop_marker(
    title: str,
    message: str,
    stamp: datetime,
    directory: Path | None = None,
) -> AlertOutcome:
    target = directory or desktop_directory()
    if target is None:
        return AlertOutcome("desktop_marker", False, "no Desktop directory found")
    path = target / f"Weekly Digest ALERT {stamp.date().isoformat()}.txt"
    body = (
        f"{title}\n"
        f"{'=' * len(title)}\n\n"
        f"{stamp.isoformat()}\n\n"
        f"{message}\n\n"
        "Details: runtime\\logs\\weekly_digest.log\n"
        "This file stays until you delete it.\n"
    )
    try:
        path.write_text(body, encoding="utf-8")
    except OSError as exc:
        return AlertOutcome("desktop_marker", False, str(exc))
    return AlertOutcome("desktop_marker", True, str(path))


def write_event_log(
    message: str, level: str = "ERROR", runner=subprocess.run
) -> AlertOutcome:
    executable = shutil.which("eventcreate.exe") or shutil.which("eventcreate")
    if not executable:
        return AlertOutcome("event_log", False, "eventcreate.exe is not available")
    try:
        completed = runner(
            [
                executable,
                "/T",
                level,
                "/ID",
                str(EVENT_LOG_ID),
                "/L",
                "APPLICATION",
                "/SO",
                EVENT_LOG_SOURCE,
                "/D",
                one_line(message, EVENT_TEXT_LIMIT),
            ],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return AlertOutcome("event_log", False, str(exc))
    if completed.returncode != 0:
        return AlertOutcome(
            "event_log",
            False,
            f"exit {completed.returncode}: {one_line(completed.stderr or '')}",
        )
    return AlertOutcome(
        "event_log", True, f"source {EVENT_LOG_SOURCE}, event id {EVENT_LOG_ID}"
    )


def notify(
    *,
    title: str,
    message: str,
    settings: AlertSettings,
    stamp: datetime,
    subprocess_runner=subprocess.run,
    marker_directory: Path | None = None,
) -> list[AlertOutcome]:
    """Try every enabled channel; never raise."""
    outcomes: list[AlertOutcome] = []
    if settings.popup_enabled:
        outcomes.append(
            send_popup(f"{title}: {one_line(message)}", runner=subprocess_runner)
        )
    if settings.desktop_marker_enabled:
        outcomes.append(
            write_desktop_marker(title, message, stamp, directory=marker_directory)
        )
    if settings.event_log_enabled:
        outcomes.append(
            write_event_log(f"{title}: {one_line(message)}", runner=subprocess_runner)
        )
    return outcomes


def report_problem(
    *,
    project_root: Path,
    title: str,
    message: str,
    settings: AlertSettings,
    context: dict | None = None,
    timezone_name: str = "America/Regina",
    notify_operator: bool = True,
    write_record: bool = True,
    subprocess_runner=subprocess.run,
    marker_directory: Path | None = None,
) -> list[AlertOutcome]:
    """Record a problem and, when requested, tell the operator about it."""
    stamp = datetime.now(ZoneInfo(timezone_name))
    outcomes: list[AlertOutcome] = []
    if write_record:
        outcomes.append(
            write_failure_record(
                project_root,
                {
                    "detected_at": stamp.isoformat(),
                    "title": title,
                    "message": message,
                    "timezone": timezone_name,
                    "context": context or {},
                },
            )
        )
    if notify_operator:
        outcomes.extend(
            notify(
                title=title,
                message=message,
                settings=settings,
                stamp=stamp,
                subprocess_runner=subprocess_runner,
                marker_directory=marker_directory,
            )
        )
    for outcome in outcomes:
        state = "ok" if outcome.ok else "FAILED"
        logging.warning("Alert channel %s: %s (%s)", outcome.channel, state, outcome.detail)
    return outcomes


def report_failure(
    *,
    exc: BaseException,
    stage: str,
    settings: AlertSettings,
    project_root: Path,
    mode: str,
    exit_code: int,
    notify_operator: bool,
    context: dict | None = None,
    timezone_name: str = "America/Regina",
    subprocess_runner=subprocess.run,
    marker_directory: Path | None = None,
) -> int:
    """Report a failed run, then return ``exit_code`` for the caller to use."""
    detail = f"{type(exc).__name__}: {exc}".strip()
    title = (
        "Weekly Clean Fuels Digest failed"
        if mode == "send"
        else "Weekly Clean Fuels Digest preview failed"
    )
    message = f"Stage: {stage}\nMode: {mode}\nExit code: {exit_code}\n\n{detail}"
    outcomes = report_problem(
        project_root=project_root,
        title=title,
        message=message,
        settings=settings,
        context={"stage": stage, "mode": mode, "exit_code": exit_code, **(context or {})},
        timezone_name=timezone_name,
        notify_operator=notify_operator,
        subprocess_runner=subprocess_runner,
        marker_directory=marker_directory,
    )
    print(f"ERROR: {detail}", file=sys.stderr)
    if notify_operator:
        summary = ", ".join(
            f"{outcome.channel}={'ok' if outcome.ok else 'failed'}" for outcome in outcomes
        )
        print(f"Alert channels: {summary}", file=sys.stderr)
    return exit_code
