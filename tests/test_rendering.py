"""Renderer snapshots and link-scope rules.

The snapshot uses a frozen configuration instead of the live ``config.yaml``:
otherwise adding a country to the production inventory would churn the golden
files. Run with ``UPDATE_RENDER_FIXTURES=1`` to regenerate the goldens after a
deliberate, reviewed change to the rendered output.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weekly_clean_fuels_digest import digest_renderer
from weekly_clean_fuels_digest.shared_digest_models import DigestItem

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
TZ = ZoneInfo("America/Regina")
PERIOD_START = datetime(2026, 9, 25, tzinfo=TZ)
PERIOD_END = datetime(2026, 10, 2, tzinfo=TZ)
DIGEST_ID = "wcf-fixture-0001"

WORKBOOK_URL = (
    "https://ww2.arb.ca.gov/sites/default/files/classic/fuels/lcfs/"
    "fuelpathways/current-pathways_all.xlsx"
)
BC_PAGE_URL = (
    "https://www2.gov.bc.ca/gov/content/industry/electricity-alternative-energy/"
    "transportation-energies/renewable-low-carbon-fuels/information-bulletins"
)

FROZEN_CONFIG = {
    "programs": [
        {
            "id": "california_lcfs",
            "country": "United States",
            "country_order": 1,
            "program_order": 1,
            "name": "California Low Carbon Fuel Standard (LCFS)",
        },
        {
            "id": "oregon_cfp",
            "country": "United States",
            "country_order": 1,
            "program_order": 2,
            "name": "Oregon Clean Fuels Program (CFP)",
        },
        {
            "id": "bc_lcfs",
            "country": "Canada",
            "country_order": 2,
            "program_order": 1,
            "name": "BC Low Carbon Fuel Standard (LCFS)",
        },
    ]
}


def make_item(
    program_id: str,
    title: str,
    summary: str,
    source_url: str,
    *,
    source_group: str | None = None,
    source_label: str = "View original source",
    source_kind: str = "email",
    item_key: str,
) -> DigestItem:
    program = next(row for row in FROZEN_CONFIG["programs"] if row["id"] == program_id)
    return DigestItem(
        country=program["country"],
        country_order=program["country_order"],
        program_id=program["id"],
        program_name=program["name"],
        program_order=program["program_order"],
        title=title,
        summary=summary,
        source_url=source_url,
        source_label=source_label,
        source_message_id="fixture-message",
        received_at=PERIOD_START.isoformat(),
        confidence="high",
        item_key=item_key,
        source_kind=source_kind,
        source_item_id=item_key if source_kind == "local_digest" else None,
        source_group=source_group,
    )


def fixture_items() -> list[DigestItem]:
    """One item set that exercises every rendering branch.

    California: two newly certified pathways (multi-line summaries, one shared
    workbook link), one existing-pathway update in the same link cluster, and one
    ordinary email item with its own link. Oregon: no items at all. British
    Columbia: one guidance item, plus one item whose source URL is not public, so
    the label fallback is exercised in both formats.
    """
    return [
        make_item(
            "california_lcfs",
            "Anew RNG, LLC (5877) — Bio-CNG (Tier 1)",
            "Certified CI: -382 gCO2e/MJ\n"
            "Pathway Description: Biogas from swine manure in Laverne, OK",
            WORKBOOK_URL,
            source_group="Newly Certified Pathways",
            source_kind="local_digest",
            item_key="ca-pathway-a",
        ),
        make_item(
            "california_lcfs",
            "Redfield Energy, LLC (4061) — Ethanol (Tier 1)",
            "Certified CI: 69.13 gCO2e/MJ\n"
            "Pathway Description: Midwest Corn, Dry Mill",
            WORKBOOK_URL,
            source_group="Newly Certified Pathways",
            source_kind="local_digest",
            item_key="ca-pathway-b",
        ),
        make_item(
            "california_lcfs",
            "Redfield Energy, LLC (4061) — Ethanol - Cellulosic (Tier 1)",
            "Certified CI updated: 26.97 → 25.10 gCO2e/MJ\n"
            "Pathway Description: Corn Fiber Ethanol via the EDENIQ process",
            WORKBOOK_URL,
            source_group="Existing Pathway Updates",
            source_kind="local_digest",
            item_key="ca-pathway-update",
        ),
        make_item(
            "california_lcfs",
            "LCFS quarterly workshop announced",
            "CARB will hold a public workshop on the quarterly LCFS report.",
            "https://mail.google.com/mail/u/0/#all/fixture-ca",
            item_key="ca-email",
        ),
        make_item(
            "bc_lcfs",
            "RLCF-009 — Reporting Responsibility and Requirements for Type B Fuels",
            "The guidance clarifies responsibility and allocation rules for "
            "non-electric Type B fuels.",
            BC_PAGE_URL,
            source_group="Guidance Updates",
            source_kind="local_digest",
            item_key="bc-guidance",
        ),
        make_item(
            "bc_lcfs",
            "BC LCFS information bulletin archived",
            "An older bulletin was archived with no changes to requirements.",
            "file:///D:/WorkSpace/Code/RegProgram_Automation/program/BC_LCFS/archive.json",
            source_label="Local digest: bc_archive.json",
            source_kind="local_digest",
            item_key="bc-archive",
        ),
    ]


def check_fixture(name: str, rendered: str) -> None:
    path = FIXTURE_DIR / name
    if os.environ.get("UPDATE_RENDER_FIXTURES"):
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        return
    assert path.exists(), (
        f"Missing golden file {path}. Regenerate deliberately with "
        "UPDATE_RENDER_FIXTURES=1 after reviewing the output change."
    )
    assert rendered == path.read_text(encoding="utf-8"), (
        f"Rendered output no longer matches {path.name}. If the change is "
        "intended, regenerate with UPDATE_RENDER_FIXTURES=1 and review the diff."
    )


def test_rendered_html_matches_the_golden_file():
    rendered = digest_renderer.render_html(
        fixture_items(), FROZEN_CONFIG, PERIOD_START, PERIOD_END, DIGEST_ID
    )

    check_fixture("render_html.html", rendered)


def test_rendered_text_matches_the_golden_file():
    rendered = digest_renderer.render_text(
        fixture_items(), FROZEN_CONFIG, PERIOD_START, PERIOD_END, DIGEST_ID
    )

    check_fixture("render_text.txt", rendered)


def test_no_format_ever_renders_a_non_public_url():
    items = fixture_items()

    html_body = digest_renderer.render_html(items, FROZEN_CONFIG, PERIOD_START, PERIOD_END)
    text_body = digest_renderer.render_text(items, FROZEN_CONFIG, PERIOD_START, PERIOD_END)

    assert "file:///" not in html_body
    assert "file:///" not in text_body


def ca_pathway_cluster(text_body: str) -> str:
    """The California pathway cluster only: its two groups and their one link.

    Scoping matters here. A whole-document count of one link would hold only
    because a fixture happened to contain a single program, and it would silently
    break as soon as another section legitimately renders its own link.
    """
    start = text_body.index("Newly Certified Pathway(s)")
    end = text_body.index("LCFS quarterly workshop announced")
    return text_body[start:end]


def test_the_california_cluster_shares_one_link_while_other_sources_keep_theirs():
    items = fixture_items()

    html_body = digest_renderer.render_html(items, FROZEN_CONFIG, PERIOD_START, PERIOD_END)
    text_body = digest_renderer.render_text(items, FROZEN_CONFIG, PERIOD_START, PERIOD_END)

    cluster = ca_pathway_cluster(text_body)
    html_cluster = html_body[
        html_body.index("Newly Certified Pathway(s)") :
        html_body.index("LCFS quarterly workshop announced")
    ]

    # Two pathway groups form one cluster: exactly one link, and it is the shared
    # workbook link rather than a per-item one.
    assert cluster.count("View original source:") == 1
    assert cluster.count(WORKBOOK_URL) == 1
    assert html_cluster.count("View original source →") == 1

    # The document as a whole still carries the email item's link and the BC
    # guidance link, so the cluster rule cannot be satisfied by dropping links.
    assert text_body.count("View original source:") == 3
    assert html_body.count("View original source →") == 3
