import base64
import sys
from datetime import datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weekly_clean_fuels_digest import main as MODULE


def test_reporting_window_override():
    start, end = MODULE.reporting_window("America/Regina", "2026-09-11", "2026-09-18")
    assert start == datetime(2026, 9, 11, 0, 0, tzinfo=ZoneInfo("America/Regina"))
    assert end == datetime(2026, 9, 18, 0, 0, tzinfo=ZoneInfo("America/Regina"))


@pytest.mark.parametrize(
    ("today", "expected_start", "expected_end"),
    [
        (datetime(2026, 9, 25), "2026-09-18", "2026-09-25"),  # Friday
        (datetime(2026, 9, 26), "2026-09-18", "2026-09-25"),  # Saturday
        (datetime(2026, 9, 29), "2026-09-18", "2026-09-25"),  # Tuesday
    ],
)
def test_reporting_window_default_is_last_completed_seven_days(
    monkeypatch, today, expected_start, expected_end
):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(today.year, today.month, today.day, 9, 0, tzinfo=tz)

    monkeypatch.setattr(MODULE, "datetime", FixedDateTime)

    start, end = MODULE.reporting_window("America/Regina", None, None)

    assert start.date().isoformat() == expected_start
    assert end.date().isoformat() == expected_end
    assert (end - start).days == 7


def test_canonicalize_url_removes_tracking():
    result = MODULE.canonicalize_url(
        "HTTPS://Example.COM/update?id=7&utm_source=email&utm_campaign=weekly#section"
    )
    assert result == "https://example.com/update?id=7"


def test_render_contains_country_program_and_empty_message():
    config = MODULE.load_config(ROOT / "config" / "config.yaml")
    start, end = MODULE.reporting_window("America/Regina", "2026-09-11", "2026-09-18")
    output = MODULE.render_html([], config, start, end)
    assert "United States" in output
    assert "Canada Clean Fuel Regulations (CFR)" in output
    assert "UK SAF Mandate" in output
    assert "No relevant updates identified this week." in output


def test_local_digest_integration_is_enabled_by_default():
    config = MODULE.load_config(ROOT / "config" / "config.yaml")
    assert config["integrations"]["local_digest_enabled"] is True


def test_new_mexico_program_accepts_both_configured_senders():
    config = MODULE.load_config(ROOT / "config" / "config.yaml")
    sender_index, senders = MODULE.build_sender_index(config)

    assert "nmed@public.govdelivery.com" in senders
    assert "cleanfuel.standard@env.nm.gov" in senders
    assert sender_index["cleanfuel.standard@env.nm.gov"]["id"] == "new_mexico_ctfp"


def test_standard_email_link_uses_view_original_source_label():
    config = MODULE.load_config(ROOT / "config" / "config.yaml")
    start, end = MODULE.reporting_window("America/Regina", "2026-09-25", "2026-10-02")
    program = config["programs"][0]
    item = MODULE.DigestItem(
        country=program["country"],
        country_order=program["country_order"],
        program_id=program["id"],
        program_name=program["name"],
        program_order=program["program_order"],
        title="Example update",
        summary="Example summary",
        source_url="https://example.com/update",
        source_label="Original email",
        source_message_id="example-message",
        received_at=start.isoformat(),
        confidence="high",
        item_key="example-key",
    )

    output = MODULE.render_html([item], config, start, end)

    assert "View original source →" in output
    assert "Original email →" not in output


def test_email_identity_remains_compatible_while_local_identity_is_source_specific():
    old_email_key = MODULE.item_identity(
        "washington_cfs", "Example update", "https://example.com/update"
    )
    same_email_key = MODULE.item_identity(
        "washington_cfs", "Example update", "https://example.com/update", "email"
    )
    local_key_a = MODULE.item_identity(
        "california_lcfs", "Same displayed title", "https://example.com/file.xlsx",
        "local_digest", "pathway-fields:one",
    )
    local_key_b = MODULE.item_identity(
        "california_lcfs", "Same displayed title", "https://example.com/file.xlsx",
        "local_digest", "pathway-fields:two",
    )

    assert old_email_key == same_email_key
    assert local_key_a != local_key_b


def test_local_identity_metadata_does_not_expand_openai_response_schema():
    schema = MODULE.EmailAnalysis.model_json_schema()
    item_properties = schema["$defs"]["ExtractedItem"]["properties"]

    assert "source_item_id" not in item_properties
    assert "source_group" not in item_properties


def test_digest_id_is_stable_for_same_period_and_configuration():
    config = MODULE.load_config(ROOT / "config" / "config.yaml")
    start, end = MODULE.reporting_window("America/Regina", "2026-09-25", "2026-10-02")

    assert MODULE.digest_identity(config, start, end) == MODULE.digest_identity(config, start, end)
    assert MODULE.digest_identity(config, start, end) != MODULE.digest_identity(
        config, start, end, include_processed=True
    )


def test_digest_id_is_embedded_in_both_preview_formats():
    html_body, text_body = MODULE.add_digest_id_footer(
        "<html><body><td>Please use the original source for verification.</td></tr></body></html>",
        "Digest preview",
        "wcf-test-id",
    )

    assert "Digest ID: wcf-test-id" in html_body
    assert "Digest ID: wcf-test-id" in text_body


def test_send_uses_digest_id_as_message_id_header():
    class FakeMessages:
        raw_message = None

        def send(self, userId, body):
            self.raw_message = body["raw"]
            return self

        def execute(self):
            return {"id": "fake-gmail-id"}

    class FakeUsers:
        def __init__(self):
            self.messages_api = FakeMessages()

        def messages(self):
            return self.messages_api

    class FakeService:
        def __init__(self):
            self.users_api = FakeUsers()

        def users(self):
            return self.users_api

    service = FakeService()
    config = MODULE.load_config(ROOT / "config" / "config.yaml")

    result = MODULE.send_digest(
        service, config, "Test digest", "<p>HTML</p>", "Text", "wcf-test-id"
    )
    encoded = service.users_api.messages_api.raw_message
    parsed = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    )

    assert result == "fake-gmail-id"
    assert parsed["Message-ID"] == "<wcf-test-id@weekly-clean-fuels-digest.local>"


def test_config_rejects_duplicate_program_ids(tmp_path):
    config = MODULE.load_config(ROOT / "config" / "config.yaml")
    config["programs"].append(dict(config["programs"][0]))
    config_path = tmp_path / "invalid.yaml"
    import yaml

    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate program id"):
        MODULE.load_config(config_path)


