import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weekly_clean_fuels_digest import watchdog
from weekly_clean_fuels_digest.alerts import AlertSettings

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
    state = {"sent_items": {"key": {}}, "last_run": {"period_end": FRIDAY.isoformat()}}

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
