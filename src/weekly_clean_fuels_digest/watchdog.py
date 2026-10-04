"""Independent check that the expected weekly digest actually went out.

This runs from its own scheduled task (Saturday morning by default) and uses no
mail transport, so a broken Gmail credential, a Gmail outage, or a crash between
"provider accepted the mail" and "state was saved" cannot hide the failure.

Design rules:

* Read-only with respect to the digest state. Alert bookkeeping lives in
  ``runtime/state/watchdog.json`` so the digest's own state schema is never at
  risk, and so a bug here cannot corrupt delivery bookkeeping.
* One alert per missed period, keyed by the Friday date of the period, so a
  repeated check does not nag.
* A period is judged by "did the digest for *that period* go out", not by "was
  there any activity in the last seven days": a manual test send must not mask a
  missing scheduled delivery.
* Exit codes: ``0`` nothing wrong, ``2`` configuration problem, ``3`` the
  expected digest is missing (or blocked by a pending transaction).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .alerts import AlertSettings, report_problem
from .main import load_config, setup_logging
from .state_store import load_state

ROOT = Path(__file__).resolve().parents[2]

STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_PENDING = "pending"
STATUS_UNINITIALIZED = "uninitialized"

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_ALERT = 3

DEFAULT_SCHEDULE_TIME = "09:00"
DEFAULT_GRACE_HOURS = 6.0


@dataclass
class Verdict:
    status: str
    message: str
    period_end: datetime | None = None
    expected_send_at: datetime | None = None
    alert_required: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that the digest for the expected period was sent."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "config.yaml",
        help="YAML configuration file.",
    )
    parser.add_argument(
        "--now",
        help="Override the current local time with an ISO 8601 value (testing).",
    )
    parser.add_argument(
        "--grace-hours", type=float, help="Override alerts.grace_hours."
    )
    parser.add_argument(
        "--force-alert",
        action="store_true",
        help="Notify again even if this period was already reported.",
    )
    parser.add_argument(
        "--test-alert",
        action="store_true",
        help="Send a test notification through the enabled channels, then exit.",
    )
    return parser.parse_args()


def expected_period_end(now: datetime) -> datetime:
    """Most recent Friday 00:00 at or before ``now``, matching the digest window."""
    days_since_friday = (now.weekday() - 4) % 7
    day = now.date() - timedelta(days=days_since_friday)
    return datetime.combine(day, dt_time.min, tzinfo=now.tzinfo)


def scheduled_send_time(period_end: datetime, schedule_time: str) -> datetime:
    """The configured send time on the day the reporting period ends."""
    try:
        hour, minute = (int(part) for part in str(schedule_time).split(":")[:2])
    except (TypeError, ValueError):
        logging.warning(
            "Unreadable schedule.time %r; assuming %s.", schedule_time, DEFAULT_SCHEDULE_TIME
        )
        hour, minute = 9, 0
    return period_end + timedelta(hours=hour, minutes=minute)


def parse_timestamp(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def evaluate(
    state: dict,
    *,
    now: datetime,
    schedule_time: str = DEFAULT_SCHEDULE_TIME,
    grace_hours: float = DEFAULT_GRACE_HOURS,
) -> Verdict:
    """Decide whether this period's digest is accounted for."""
    period_end = expected_period_end(now)
    expected_send_at = scheduled_send_time(period_end, schedule_time)
    deadline = expected_send_at + timedelta(hours=grace_hours)

    transactions = state.get("send_transactions") or {}
    if not isinstance(transactions, dict):
        transactions = {}
    matching = [
        transaction
        for transaction in transactions.values()
        if isinstance(transaction, dict)
        and parse_timestamp(transaction.get("period_end")) == period_end
    ]

    if any(transaction.get("status") == "sent" for transaction in matching):
        return Verdict(
            STATUS_OK,
            f"Digest for the period ending {period_end.date()} was sent.",
            period_end,
            expected_send_at,
        )

    last_run = state.get("last_run") or {}
    if isinstance(last_run, dict) and parse_timestamp(last_run.get("period_end")) == period_end:
        return Verdict(
            STATUS_OK,
            f"Last recorded send covers the period ending {period_end.date()}.",
            period_end,
            expected_send_at,
        )

    if now < deadline:
        return Verdict(
            STATUS_OK,
            f"Still inside the grace window until {deadline.isoformat()}.",
            period_end,
            expected_send_at,
        )

    if any(transaction.get("status") == "sending" for transaction in matching):
        return Verdict(
            STATUS_PENDING,
            "An unresolved send transaction is blocking automatic delivery; "
            "resolve it with --resolve-pending <DIGEST_ID> --resolution sent|not-sent.",
            period_end,
            expected_send_at,
            True,
        )

    if not transactions and not (state.get("sent_items") or {}) and not last_run:
        return Verdict(
            STATUS_UNINITIALIZED,
            "No send history found yet, so there is nothing to compare against.",
            period_end,
            expected_send_at,
        )

    return Verdict(
        STATUS_MISSING,
        f"No successful send recorded for the period ending {period_end.date()}.",
        period_end,
        expected_send_at,
        True,
    )


def watchdog_state_path(project_root: Path) -> Path:
    return project_root / "runtime" / "state" / "watchdog.json"


def load_watchdog_state(project_root: Path) -> dict:
    path = watchdog_state_path(project_root)
    if not path.exists():
        return {"alerted_periods": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Ignoring unreadable %s: %s", path, exc)
        return {"alerted_periods": {}}
    if not isinstance(data, dict) or not isinstance(data.get("alerted_periods"), dict):
        logging.warning("Ignoring malformed %s; starting fresh.", path)
        return {"alerted_periods": {}}
    return data


def save_watchdog_state(project_root: Path, data: dict) -> bool:
    path = watchdog_state_path(project_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(path)
    except OSError as exc:
        logging.error("Could not write %s: %s", path, exc)
        return False
    return True


def already_alerted(data: dict, period_end: datetime) -> bool:
    alerted = data.get("alerted_periods") or {}
    return period_end.date().isoformat() in alerted


def mark_alerted(data: dict, period_end: datetime, stamp: datetime) -> None:
    data.setdefault("alerted_periods", {})[period_end.date().isoformat()] = stamp.isoformat()
    data["last_check_at"] = stamp.isoformat()


def resolve_now(args: argparse.Namespace, tz: ZoneInfo) -> datetime:
    if not args.now:
        return datetime.now(tz)
    parsed = datetime.fromisoformat(args.now)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def main() -> int:
    args = parse_args()
    settings = AlertSettings()
    try:
        config = load_config(args.config)
        setup_logging(config)
        settings = AlertSettings.from_config(config)
        timezone_name = config["schedule"].get("timezone", "America/Regina")
        tz = ZoneInfo(timezone_name)
        now = resolve_now(args, tz)
        schedule_time = str(config["schedule"].get("time", DEFAULT_SCHEDULE_TIME))
        state = load_state(config, ROOT)
    except Exception as exc:
        print(f"WATCHDOG CONFIG ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    if args.grace_hours is not None:
        settings.grace_hours = args.grace_hours

    if args.test_alert:
        report_problem(
            project_root=ROOT,
            title="Weekly Clean Fuels Digest alert test",
            message=(
                "This is a test notification. No digest was sent and no state was "
                "changed. If you can see this, the alert channels work."
            ),
            settings=settings,
            context={"mode": "test"},
            timezone_name=timezone_name,
            write_record=False,
        )
        print("Test notification sent through the enabled channels.")
        return EXIT_OK

    verdict = evaluate(
        state, now=now, schedule_time=schedule_time, grace_hours=settings.grace_hours
    )
    logging.info("Watchdog check: %s - %s", verdict.status, verdict.message)
    print(f"{verdict.status}: {verdict.message}")

    if not verdict.alert_required or verdict.period_end is None:
        return EXIT_OK

    bookkeeping = load_watchdog_state(ROOT)
    if already_alerted(bookkeeping, verdict.period_end) and not args.force_alert:
        print(f"Already reported for {verdict.period_end.date()}; not notifying again.")
        return EXIT_ALERT

    report_problem(
        project_root=ROOT,
        title="Weekly Clean Fuels Digest was not delivered",
        message=(
            f"Expected send time: {verdict.expected_send_at.isoformat()}\n"
            f"Reporting period end: {verdict.period_end.isoformat()}\n"
            f"Grace allowed: {settings.grace_hours} hour(s)\n\n"
            f"{verdict.message}\n\n"
            "Check runtime\\logs\\weekly_digest.log and the Task Scheduler history."
        ),
        settings=settings,
        context={
            "status": verdict.status,
            "period_end": verdict.period_end.isoformat(),
            "expected_send_at": verdict.expected_send_at.isoformat(),
            "grace_hours": settings.grace_hours,
        },
        timezone_name=timezone_name,
    )
    mark_alerted(bookkeeping, verdict.period_end, now)
    save_watchdog_state(ROOT, bookkeeping)
    return EXIT_ALERT


if __name__ == "__main__":
    raise SystemExit(main())
