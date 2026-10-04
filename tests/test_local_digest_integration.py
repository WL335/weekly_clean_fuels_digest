import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weekly_clean_fuels_digest import main as MODULE


def test_local_digest_uses_generated_at_and_maps_to_program(tmp_path):
    digest = tmp_path / "ca_digest.json"
    digest.write_text(
        json.dumps(
            {
                "program": "CA_LCFS",
                "generated_at": "2026-09-26T16:15:24",
                "document_key": "current_pathways_all",
                "previous_version": "20260828",
                "current_version": "20260911",
                "added_count": 1,
                "added_pathways": [{"Company (ID)": "Example Producer (1)"}],
            }
        ),
        encoding="utf-8",
    )
    config = MODULE.load_config(ROOT / "config" / "config.yaml")
    config["local_digest_sources"] = [
        {
            "id": "test_ca",
            "program_id": "california_lcfs",
            "directory": str(tmp_path),
            "pattern": "*.json",
            "timestamp_field": "generated_at",
            "json_program": "CA_LCFS",
            "display_label": "Newly Certified Pathways",
            "public_source_url": "https://example.com/current-pathways_all.xlsx",
        }
    ]
    start, end = MODULE.reporting_window(
        "America/Regina", "2026-09-25", "2026-10-02"
    )

    messages = MODULE.local_digest_integration.load_local_digest_messages(
        config, start, end, ROOT
    )

    assert len(messages) == 1
    raw, program = messages[0]
    assert program["id"] == "california_lcfs"
    assert raw.source_kind == "local_digest"
    assert raw.received_at == datetime(
        2026, 9, 26, 16, 15, 24, tzinfo=ZoneInfo("America/Regina")
    )
    assert raw.source_label == "Newly Certified Pathways"
    analysis = MODULE.local_digest_integration.analyze_local_digest(raw)
    assert len(analysis.items) == 1
    assert analysis.items[0].title == "Example Producer (1) — LCFS fuel pathway"
    assert analysis.items[0].summary == (
        "Certified CI: Not stated\nPathway Description: Not stated"
    )
    assert analysis.items[0].confidence == "high"


def test_local_digest_outside_period_is_excluded(tmp_path):
    digest = tmp_path / "old_digest.json"
    digest.write_text(
        json.dumps(
            {
                "program": "CA_LCFS",
                "generated_at": "2026-09-17T23:59:59",
            }
        ),
        encoding="utf-8",
    )
    config = MODULE.load_config(ROOT / "config" / "config.yaml")
    config["local_digest_sources"] = [
        {
            "id": "test_ca",
            "program_id": "california_lcfs",
            "directory": str(tmp_path),
            "json_program": "CA_LCFS",
        }
    ]
    start, end = MODULE.reporting_window(
        "America/Regina", "2026-09-18", "2026-09-25"
    )

    assert (
        MODULE.local_digest_integration.load_local_digest_messages(
            config, start, end, ROOT
        )
        == []
    )


def test_bc_local_digest_renders_as_guidance_updates(tmp_path):
    digest = tmp_path / "bc_digest.json"
    digest.write_text(
        json.dumps(
            {
                "program": "BC_LCFS",
                "generated_at": "2026-09-27T09:03:30",
                "document_key": "RLCF-009",
                "title": "Reporting Responsibility and Requirements for Type B Fuels",
                "digest_summary": "The guidance clarifies responsibility and allocation rules.",
                "source": {
                    "source_page": "https://www2.gov.bc.ca/example/information-bulletins"
                },
            }
        ),
        encoding="utf-8",
    )
    config = MODULE.load_config(ROOT / "config" / "config.yaml")
    config["local_digest_sources"] = [
        {
            "id": "test_bc",
            "program_id": "bc_lcfs",
            "directory": str(tmp_path),
            "pattern": "*.json",
            "timestamp_field": "generated_at",
            "json_program": "BC_LCFS",
            "display_label": "Guidance Updates",
        }
    ]
    start, end = MODULE.reporting_window(
        "America/Regina", "2026-09-25", "2026-10-02"
    )

    messages = MODULE.local_digest_integration.load_local_digest_messages(
        config, start, end, ROOT
    )

    assert len(messages) == 1
    raw, program = messages[0]
    assert program["id"] == "bc_lcfs"
    assert raw.source_label == "Guidance Updates"
    assert raw.gmail_url == "https://www2.gov.bc.ca/example/information-bulletins"
    analysis = MODULE.local_digest_integration.analyze_local_digest(raw)
    assert analysis.items[0].title == (
        "RLCF-009 — Reporting Responsibility and Requirements for Type B Fuels"
    )
    assert analysis.items[0].summary == (
        "The guidance clarifies responsibility and allocation rules."
    )

    items = MODULE.convert_items(raw, program, analysis)
    output = MODULE.render_html(items, config, start, end)
    assert output.count("Guidance Updates") == 1
    assert output.count("View original source →") == 1


def test_california_pathway_identity_ignores_ci_and_row_position():
    def analyze(ci, source_row):
        raw = MODULE.RawEmail(
            message_id="local:ca-workbook",
            sender="local-digest",
            subject="California pathway digest",
            received_at=datetime(2026, 9, 26, tzinfo=ZoneInfo("America/Regina")),
            body=json.dumps(
                {
                    "program": "CA_LCFS",
                    "current_version": "20260925",
                    "added_pathways": [
                        {
                            "Company (ID)": "Example Biofuels (1234)",
                            "Fuel Category": "Bio-CNG",
                            "Class": "Tier 1",
                            "Current Certified CI": ci,
                            "Pathway Description": "Manure biogas upgraded to pipeline quality",
                            "source_row": source_row,
                        }
                    ],
                }
            ),
            links={},
            gmail_url="https://example.com/pathways.xlsx",
            source_label="Newly Certified Pathways",
            source_kind="local_digest",
        )
        return MODULE.local_digest_integration.analyze_local_digest(raw).items[0]

    first = analyze("-382", 17)
    moved_and_recertified = analyze("-375", 41)

    assert first.source_item_id == moved_and_recertified.source_item_id
    assert first.source_group == "Newly Certified Pathways"


def test_identical_pathway_rows_use_source_row_only_as_collision_tiebreaker():
    raw = MODULE.RawEmail(
        message_id="local:ca-workbook",
        sender="local-digest",
        subject="California pathway digest",
        received_at=datetime(2026, 9, 26, tzinfo=ZoneInfo("America/Regina")),
        body=json.dumps(
            {
                "program": "CA_LCFS",
                "added_pathways": [
                    {
                        "Company (ID)": "Example Biofuels (1234)",
                        "Fuel Category": "Bio-CNG",
                        "Class": "Tier 1",
                        "Pathway Description": "Same route",
                        "source_row": 17,
                    },
                    {
                        "Company (ID)": "Example Biofuels (1234)",
                        "Fuel Category": "Bio-CNG",
                        "Class": "Tier 1",
                        "Pathway Description": "Same route",
                        "source_row": 18,
                    },
                ],
            }
        ),
        links={},
        gmail_url="https://example.com/pathways.xlsx",
        source_label="Newly Certified Pathways",
        source_kind="local_digest",
    )

    items = MODULE.local_digest_integration.analyze_local_digest(raw).items

    assert len(items) == 2
    assert items[0].source_item_id != items[1].source_item_id


def test_bc_second_document_version_has_a_new_local_identity():
    def analyze(version, summary):
        raw = MODULE.RawEmail(
            message_id="local:bc-bulletin",
            sender="local-digest",
            subject="BC guidance digest",
            received_at=datetime(2026, 9, 26, tzinfo=ZoneInfo("America/Regina")),
            body=json.dumps(
                {
                    "program": "BC_LCFS",
                    "document_key": "RLCF-009",
                    "current_version": version,
                    "title": "Reporting Responsibility and Requirements for Type B Fuels",
                    "digest_summary": summary,
                }
            ),
            links={},
            gmail_url="https://example.com/bc",
            source_label="Guidance Updates",
            source_kind="local_digest",
        )
        return MODULE.local_digest_integration.analyze_local_digest(raw).items[0]

    first = analyze("2026-09-01", "Original guidance.")
    revised = analyze("2026-09-25", "Revised guidance.")

    assert first.source_item_id != revised.source_item_id
    assert MODULE.item_identity("bc_lcfs", first.title, "https://example.com/bc", "local_digest", first.source_item_id) != MODULE.item_identity(
        "bc_lcfs", revised.title, "https://example.com/bc", "local_digest", revised.source_item_id
    )


def test_existing_pathway_updates_render_in_separate_subsection():
    digest = {
        "program": "CA_LCFS",
        "current_version": "20260925",
        "added_pathways": [
            {
                "Company (ID)": "New Producer (5678)",
                "Fuel Category": "Renewable Diesel",
                "Class": "Tier 1",
                "Current Certified CI": "-90",
                "Pathway Description": "Newly certified route",
                "source_row": 20,
            }
        ],
        "updated_pathways": [
            {
                "Company (ID)": "Example Biofuels (1234)",
                "Fuel Category": "Bio-CNG",
                "Class": "Tier 1",
                "Previous Certified CI": "-382",
                "Current Certified CI": "-375",
                "Pathway Description": "Manure biogas upgraded to pipeline quality",
                "source_row": 17,
            }
        ],
    }
    raw = MODULE.RawEmail(
        message_id="local:ca-workbook",
        sender="local-digest",
        subject="California pathway digest",
        received_at=datetime(2026, 9, 26, tzinfo=ZoneInfo("America/Regina")),
        body=json.dumps(digest),
        links={},
        gmail_url="https://example.com/pathways.xlsx",
        source_label="Newly Certified Pathways",
        source_kind="local_digest",
    )
    config = MODULE.load_config(ROOT / "config" / "config.yaml")
    start, end = MODULE.reporting_window("America/Regina", "2026-09-25", "2026-10-02")
    analysis = MODULE.local_digest_integration.analyze_local_digest(raw)
    items = MODULE.convert_items(raw, config["programs"][0], analysis)

    output = MODULE.render_html(items, config, start, end)

    assert "Existing Pathway Updates" in output
    assert "Newly Certified Pathway(s)" in output
    assert "Certified CI updated: -382 → -375" in output
    assert output.count("View original source →") == 1


