import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weekly_clean_fuels_digest import watchdog
from weekly_clean_fuels_digest.alerts import AlertOutcome, AlertSettings

TZ = ZoneInfo("America/Regina")
FRIDAY = datetime(2026, 9, 25, tzinfo=TZ)  # the period end the digest would report
FRIDAY_0900 = datetime(2026, 9, 25, 9, 0, tzinfo=TZ)


def test_expected_period_end_is_the_most_recent_friday():
    assert watchdog.expected_period_end(FRIDAY_0900).date().isoformat() == "2026-09-25"
    assert (
        watchdog.expected_period_end(datetime(2026, 9, 26, 9, 0, tzinfo=TZ))
        .date()
        .isoformat()
        == "2026-09-25"
    )
    assert (
        watchdog.expected_period_end(datetime(2026, 9, 28, 9, 0, tzinfo=TZ))
        .date()
        .isoformat()
        == "2026-09-25"
    )


def test_scheduled_send_time_uses_the_configured_clock():
    assert watchdog.scheduled_send_time(FRIDAY, "09:00") == FRIDAY_0900
    assert watchdog.scheduled_send_time(FRIDAY, "06:30") == FRIDAY + timedelta(hours=6, minutes=30)
    # An unreadable value must fall back to 09:00 instead of crashing the check.
    assert watchdog.scheduled_send_time(FRIDAY, "not-a-time") == FRIDAY_0900


def test_sent_period_is_reported_as_ok():
    state = {
        "sent_items": {"key": {"sent_at": "x"}},
        "send_transactions": {
            "wcf-1": {
                "status": "sent",
                "period_start": "2026-09-18T00:00:00-06:00",
                "period_end": FRIDAY.isoformat(),
            }
        },
    }

    verdict = watchdog.evaluate(state, now=datetime(2026, 9, 26, 9, 0, tzinfo=TZ))

    assert verdict.status == watchdog.STATUS_OK
    assert verdict.alert_required is False


def test_missing_period_waits_for_the_grace_window():
    state = {"sent_items": {"key": {}}, "send_transactions": {}}

    inside = watchdog.evaluate(state, now=FRIDAY + timedelta(hours=11), grace_hours=6)
    after = watchdog.evaluate(
        state, now=FRIDAY + timedelta(hours=15, minutes=1), grace_hours=6
    )

    assert inside.status == watchdog.STATUS_OK
    assert "grace window" in inside.message
    assert after.status == watchdog.STATUS_MISSING
    assert after.alert_required is True


def test_grace_hours_comes_from_the_alert_settings():
    settings = AlertSettings.from_config({"alerts": {"grace_hours": 1}})
    state = {"sent_items": {"key": {}}, "send_transactions": {}}
    # 11:00, two hours after the scheduled send time: inside a six-hour grace
    # window, but outside a one-hour one.
    moment = FRIDAY_0900 + timedelta(hours=2)

    short = watchdog.evaluate(state, now=moment, grace_hours=settings.grace_hours)
    default = watchdog.evaluate(state, now=moment, grace_hours=6)

    assert short.alert_required is True
    assert default.alert_required is False


def test_pending_transaction_is_reported_as_its_own_case():
    state = {
        "sent_items": {"key": {}},
        "send_transactions": {
            "wcf-1": {"status": "sending", "period_end": FRIDAY.isoformat()}
        },
    }

    verdict = watchdog.evaluate(state, now=FRIDAY + timedelta(hours=20), grace_hours=6)

    assert verdict.status == watchdog.STATUS_PENDING
    assert "--resolve-pending" in verdict.message
    assert verdict.alert_required is True


def test_legacy_last_run_without_transactions_counts_as_delivered():
    """State written before send transactions existed still proves delivery."""
    state = {
        "sent_items": {"key": {}},
        "last_run": {
            "period_start": (FRIDAY - timedelta(days=7)).isoformat(),
            "period_end": FRIDAY.isoformat(),
        },
    }

    verdict = watchdog.evaluate(state, now=FRIDAY + timedelta(hours=30), grace_hours=6)

    assert verdict.status == watchdog.STATUS_OK


def test_an_earlier_send_does_not_mask_the_current_period():
    state = {
        "sent_items": {"key": {}},
        "send_transactions": {
            "wcf-old": {"status": "sent", "period_end": "2026-09-18T00:00:00-06:00"}
        },
    }

    verdict = watchdog.evaluate(
        state, now=datetime(2026, 9, 26, 9, 0, tzinfo=TZ), grace_hours=6
    )

    assert verdict.status == watchdog.STATUS_MISSING


def test_a_fresh_install_is_not_an_alarm():
    verdict = watchdog.evaluate({}, now=datetime(2026, 10, 3, 9, 0, tzinfo=TZ))

    assert verdict.status == watchdog.STATUS_UNINITIALIZED
    assert verdict.alert_required is False


def test_bookkeeping_reports_each_period_once(tmp_path):
    state = watchdog.load_watchdog_state(tmp_path)
    assert watchdog.already_alerted(state, FRIDAY) is False

    watchdog.mark_alerted(state, FRIDAY, datetime(2026, 9, 26, 9, 0, tzinfo=TZ))
    assert watchdog.already_alerted(state, FRIDAY) is True
    assert watchdog.save_watchdog_state(tmp_path, state) is True

    reloaded = watchdog.load_watchdog_state(tmp_path)
    assert watchdog.already_alerted(reloaded, FRIDAY) is True
    assert watchdog.already_alerted(reloaded, datetime(2026, 10, 2, tzinfo=TZ)) is False


def test_unreadable_bookkeeping_is_ignored(tmp_path):
    path = watchdog.watchdog_state_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")

    assert watchdog.load_watchdog_state(tmp_path) == {"alerted_periods": {}}


def test_malformed_bookkeeping_shape_is_ignored(tmp_path):
    path = watchdog.watchdog_state_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text('{"alerted_periods": []}', encoding="utf-8")

    assert watchdog.load_watchdog_state(tmp_path) == {"alerted_periods": {}}


def test_a_one_day_report_does_not_satisfy_the_weekly_check():
    """A manual report whose end date matches is not the week."""
    state = {
        "sent_items": {"key": {}},
        "send_transactions": {
            "wcf-short": {
                "status": "sent",
                "period_start": "2026-10-01T00:00:00-06:00",
                "period_end": "2026-10-02T00:00:00-06:00",
            }
        },
    }

    verdict = watchdog.evaluate(state, now=datetime(2026, 10, 3, 9, 0, tzinfo=TZ))

    assert verdict.status == watchdog.STATUS_MISSING
    assert verdict.alert_required is True


def test_a_longer_catch_up_report_does_satisfy_the_weekly_check():
    state = {
        "sent_items": {"key": {}},
        "send_transactions": {
            "wcf-catchup": {
                "status": "sent",
                "period_start": "2026-09-18T00:00:00-06:00",
                "period_end": "2026-10-02T00:00:00-06:00",
            }
        },
    }

    verdict = watchdog.evaluate(state, now=datetime(2026, 10, 3, 9, 0, tzinfo=TZ))

    assert verdict.status == watchdog.STATUS_OK


def test_last_run_alone_must_also_cover_the_expected_week():
    state = {
        "sent_items": {"key": {}},
        "last_run": {
            "period_start": "2026-10-01T00:00:00-06:00",
            "period_end": "2026-10-02T00:00:00-06:00",
        },
    }

    verdict = watchdog.evaluate(state, now=datetime(2026, 10, 3, 9, 0, tzinfo=TZ))

    assert verdict.status == watchdog.STATUS_MISSING


def test_an_armed_watchdog_alerts_when_no_history_exists_at_all():
    verdict = watchdog.evaluate(
        {}, now=datetime(2026, 10, 3, 9, 0, tzinfo=TZ), armed_from=date(2026, 10, 2)
    )

    assert verdict.status == watchdog.STATUS_MISSING
    assert verdict.alert_required is True


def test_an_unarmed_watchdog_stays_quiet_when_no_history_exists():
    verdict = watchdog.evaluate({}, now=datetime(2026, 10, 3, 9, 0, tzinfo=TZ))

    assert verdict.status == watchdog.STATUS_UNINITIALIZED
    assert verdict.alert_required is False


def write_watchdog_config(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "mailbox": {"sender": "a@example.com", "recipient": "a@example.com"},
                "schedule": {"timezone": "America/Regina", "time": "09:00"},
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
    return path


def watchdog_args(config_path: Path, *, now: str | None = None, test_alert: bool = False):
    return argparse.Namespace(
        config=config_path,
        now=now,
        grace_hours=None,
        force_alert=False,
        test_alert=test_alert,
    )


def state_with_only_older_history() -> dict:
    """History exists, but nothing covers the expected period."""
    return {
        "sent_items": {"key": {"sent_at": "x"}},
        "send_transactions": {
            "wcf-old": {
                "status": "sent",
                "period_start": "2026-09-18T00:00:00-06:00",
                "period_end": "2026-09-25T00:00:00-06:00",
            }
        },
    }


def test_watchdog_alerts_when_it_cannot_read_its_own_state(tmp_path, monkeypatch):
    config_path = write_watchdog_config(tmp_path)
    monkeypatch.setattr(watchdog, "ROOT", tmp_path)
    monkeypatch.setattr(watchdog, "parse_args", lambda: watchdog_args(config_path))
    calls = []

    def unreadable(config, root):
        raise RuntimeError("state file is corrupt")

    monkeypatch.setattr(watchdog, "load_state", unreadable)
    monkeypatch.setattr(
        watchdog, "report_problem", lambda **kwargs: calls.append(kwargs) or []
    )

    code = watchdog.main()

    assert code == watchdog.EXIT_CONFIG_ERROR
    assert calls, "a watchdog that cannot run must still report"
    assert "watchdog could not run" in calls[0]["title"]


def test_an_undelivered_alert_is_not_recorded_as_handled(tmp_path, monkeypatch):
    config_path = write_watchdog_config(tmp_path)
    monkeypatch.setattr(watchdog, "ROOT", tmp_path)
    monkeypatch.setattr(
        watchdog,
        "parse_args",
        lambda: watchdog_args(config_path, now="2026-10-03T09:00:00"),
    )
    monkeypatch.setattr(watchdog, "load_state", lambda config, root: state_with_only_older_history())
    monkeypatch.setattr(
        watchdog,
        "report_problem",
        lambda **kwargs: [AlertOutcome("popup", False, "no session")],
    )

    code = watchdog.main()

    assert code == watchdog.EXIT_ALERT_UNDELIVERED
    assert not watchdog.watchdog_state_path(tmp_path).exists()


def test_a_delivered_alert_marks_the_period(tmp_path, monkeypatch):
    config_path = write_watchdog_config(tmp_path)
    monkeypatch.setattr(watchdog, "ROOT", tmp_path)
    monkeypatch.setattr(
        watchdog,
        "parse_args",
        lambda: watchdog_args(config_path, now="2026-10-03T09:00:00"),
    )
    monkeypatch.setattr(watchdog, "load_state", lambda config, root: state_with_only_older_history())
    monkeypatch.setattr(
        watchdog,
        "report_problem",
        lambda **kwargs: [AlertOutcome("desktop_marker", True, "path")],
    )

    code = watchdog.main()

    assert code == watchdog.EXIT_ALERT
    bookkeeping = watchdog.load_watchdog_state(tmp_path)
    assert watchdog.already_alerted(bookkeeping, datetime(2026, 10, 2, tzinfo=TZ))


def test_test_alert_reports_when_nothing_was_delivered(tmp_path, monkeypatch):
    config_path = write_watchdog_config(tmp_path)
    monkeypatch.setattr(watchdog, "ROOT", tmp_path)
    monkeypatch.setattr(
        watchdog, "parse_args", lambda: watchdog_args(config_path, test_alert=True)
    )
    monkeypatch.setattr(watchdog, "load_state", lambda config, root: {})
    monkeypatch.setattr(
        watchdog,
        "report_problem",
        lambda **kwargs: [AlertOutcome("popup", False, "no session")],
    )

    assert watchdog.main() == watchdog.EXIT_ALERT_UNDELIVERED
