"""Shared HTML and plain-text rendering for the weekly digest.

Both formats consume one grouping step (``layout_program``) and one section
definition table (``SECTION_SPECS``). Adding a subsection therefore means adding
one entry to that table instead of editing four near-identical render blocks in
two formats, which is how the HTML and text output previously drifted apart.

A section's ``cluster`` decides where its source link goes:

* ``pathways`` — the two California pathway groups share one workbook link, which
  is emitted once after the last group in the cluster;
* ``guidance`` — one link after the BC guidance group;
* no cluster — ordinary items, which carry a link each.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime, timedelta

from .shared_digest_models import DigestItem


SECTION_NEWLY_CERTIFIED = "Newly Certified Pathways"
SECTION_EXISTING_UPDATES = "Existing Pathway Updates"
SECTION_GUIDANCE = "Guidance Updates"


@dataclass(frozen=True)
class SectionSpec:
    group: str
    heading: str
    multiline: bool
    cluster: str | None


SECTION_SPECS = (
    SectionSpec(SECTION_NEWLY_CERTIFIED, "Newly Certified Pathway(s)", True, "pathways"),
    SectionSpec(SECTION_EXISTING_UPDATES, "Existing Pathway Updates", True, "pathways"),
    SectionSpec(SECTION_GUIDANCE, "Guidance Updates", False, "guidance"),
)
SECTION_GROUPS = {spec.group for spec in SECTION_SPECS}

NO_UPDATES_HTML = (
    "<div style='margin:10px 0 18px;padding:14px 16px;background:#f7f9fa;"
    "border-left:3px solid #b8c2cc;color:#52606d;font-size:14px;font-style:italic;'>"
    "No relevant updates identified this week.</div>"
)
NO_UPDATES_TEXT = "No relevant updates identified this week."


@dataclass
class ProgramLayout:
    """One program's items, split into ordered sections, links, and the rest."""

    sections: list[tuple[SectionSpec, list[DigestItem]]]
    clusters: dict[str, DigestItem]
    cluster_last_index: dict[str, int]
    standard: list[DigestItem]


def layout_program(items: list[DigestItem]) -> ProgramLayout:
    """Group one program's items once, for both renderers."""
    sections: list[tuple[SectionSpec, list[DigestItem]]] = []
    clusters: dict[str, DigestItem] = {}
    cluster_last_index: dict[str, int] = {}
    for spec in SECTION_SPECS:
        selected = [
            item
            for item in items
            if (item.source_group or item.source_label) == spec.group
        ]
        if not selected:
            continue
        if spec.cluster:
            clusters.setdefault(spec.cluster, selected[0])
            cluster_last_index[spec.cluster] = len(sections)
        sections.append((spec, selected))
    standard = [
        item
        for item in items
        if (item.source_group or item.source_label) not in SECTION_GROUPS
    ]
    return ProgramLayout(sections, clusters, cluster_last_index, standard)


def group_by_program(
    items: list[DigestItem], program_rows: list[dict]
) -> dict[str, list[DigestItem]]:
    """Bucket items by program, tolerating a program that is not configured."""
    grouped: dict[str, list[DigestItem]] = {row["id"]: [] for row in program_rows}
    for item in items:
        grouped.setdefault(item.program_id, []).append(item)
    return grouped


def human_period(start: datetime, end: datetime) -> str:
    inclusive_end = end.date() - timedelta(days=1)
    if start.year == inclusive_end.year:
        if start.month == inclusive_end.month:
            return f"{start.strftime('%B')} {start.day}–{inclusive_end.day}, {start.year}"
        return f"{start.strftime('%B')} {start.day}–{inclusive_end.strftime('%B')} {inclusive_end.day}, {start.year}"
    return f"{start.strftime('%B')} {start.day}, {start.year}–{inclusive_end.strftime('%B')} {inclusive_end.day}, {inclusive_end.year}"


def is_public_url(url: str) -> bool:
    return url.startswith(("https://", "http://"))


def public_source_line(item: DigestItem) -> str | None:
    """Text-renderer link line, only for real web URLs.

    The HTML renderer already refuses to link anything that is not http(s). The
    text renderer must behave the same, otherwise a local digest without a public
    source URL leaks a ``file:///`` path into the plain-text email.
    """
    if is_public_url(item.source_url):
        return f"View original source: {item.source_url}"
    return None


def country_heading_html(country: str) -> str:
    return (
        f"<div style='margin-top:22px;padding:9px 12px;background:#123524;color:#ffffff;"
        f"font-size:19px;font-weight:700;'>{html.escape(country)}</div>"
    )


def program_heading_html(name: str, count: int) -> str:
    count_label = f" · {count} update{'s' if count != 1 else ''}"
    return (
        f"<div style='margin-top:22px;font-size:17px;font-weight:700;color:#166534;'>"
        f"{html.escape(name)}<span style='font-weight:400;color:#68737d;'>"
        f"{html.escape(count_label)}</span></div>"
    )


def subsection_heading_html(title: str) -> str:
    return (
        "<div style='margin-top:16px;padding:10px 12px;background:#eaf4ec;"
        "border-left:4px solid #166534;font-size:15px;font-weight:700;color:#123524;'>"
        f"{html.escape(title)}</div>"
    )


def item_block_html(item: DigestItem, *, multiline: bool, first: bool) -> str:
    border = "" if first else "border-top:1px solid #e5e9ed;"
    summary = html.escape(item.summary)
    line_height = "1.65" if multiline else "1.55"
    if multiline:
        summary = summary.replace("\n", "<br>")
    return (
        f"<div style='padding:15px 0 17px;{border}'>"
        f"<div style='font-size:15px;font-weight:700;line-height:1.4;color:#1f2933;'>"
        f"{html.escape(item.title)}</div>"
        f"<div style='margin-top:7px;font-size:14px;line-height:{line_height};color:#364152;'>"
        f"{summary}</div></div>"
    )


def standard_item_html(item: DigestItem, *, first: bool) -> str:
    border = "" if first else "border-top:1px solid #e5e9ed;"
    if is_public_url(item.source_url):
        source_html = (
            f"<a href='{html.escape(item.source_url, quote=True)}' "
            "style='color:#1261a0;text-decoration:none;font-weight:600;'>"
            "View original source →</a>"
        )
    else:
        source_html = html.escape(item.source_label)
    return (
        f"<div style='padding:15px 0 17px;{border}'>"
        f"<div style='font-size:15px;font-weight:700;line-height:1.4;color:#1f2933;'>"
        f"{html.escape(item.title)}</div>"
        f"<div style='margin-top:7px;font-size:14px;line-height:1.55;color:#364152;'>"
        f"{html.escape(item.summary)}</div>"
        f"<div style='margin-top:9px;font-size:13px;color:#52606d;'>{source_html}</div>"
        "</div>"
    )


def cluster_link_html(item: DigestItem) -> str | None:
    if not is_public_url(item.source_url):
        return None
    anchor = (
        f"<a href='{html.escape(item.source_url, quote=True)}' "
        "style='color:#1261a0;text-decoration:none;font-weight:600;'>"
        "View original source →</a>"
    )
    return f"<div style='margin:0 0 18px;font-size:13px;'>{anchor}</div>"


def render_html(
    items: list[DigestItem],
    config: dict,
    start: datetime,
    end: datetime,
    digest_id: str | None = None,
) -> str:
    period = human_period(start, end)
    program_rows = sorted(
        config["programs"], key=lambda row: (row["country_order"], row["program_order"])
    )
    grouped = group_by_program(items, program_rows)

    chunks = [
        "<!doctype html><html><head><meta charset='utf-8'></head>",
        "<body style=\"margin:0;background:#f4f6f8;font-family:Arial,Helvetica,sans-serif;color:#1f2933;\">",
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='background:#f4f6f8;padding:24px 8px;'>",
        "<tr><td align='center'><table role='presentation' width='100%' cellspacing='0' cellpadding='0' "
        "style='max-width:760px;background:#ffffff;border:1px solid #dde3e8;border-radius:8px;'>",
        "<tr><td style='padding:28px 32px 18px;border-bottom:4px solid #166534;'>",
        "<div style='font-size:25px;font-weight:700;color:#123524;'>Weekly Clean Fuels Regulatory Update</div>",
        f"<div style='margin-top:9px;font-size:14px;color:#52606d;'><strong>Reporting period:</strong> {html.escape(period)}"
        f" &nbsp;|&nbsp; <strong>Updates identified:</strong> {len(items)}</div></td></tr>",
        "<tr><td style='padding:12px 32px 30px;'>",
    ]

    current_country = None
    for program in program_rows:
        country = program["country"]
        if country != current_country:
            current_country = country
            chunks.append(country_heading_html(country))

        program_items = grouped[program["id"]]
        chunks.append(program_heading_html(program["name"], len(program_items)))
        if not program_items:
            chunks.append(NO_UPDATES_HTML)
            continue

        layout = layout_program(program_items)
        for index, (spec, section_items) in enumerate(layout.sections):
            chunks.append(subsection_heading_html(spec.heading))
            for position, item in enumerate(section_items):
                chunks.append(
                    item_block_html(item, multiline=spec.multiline, first=position == 0)
                )
            if spec.cluster and layout.cluster_last_index.get(spec.cluster) == index:
                link = cluster_link_html(layout.clusters[spec.cluster])
                if link:
                    chunks.append(link)

        for position, item in enumerate(layout.standard):
            chunks.append(standard_item_html(item, first=position == 0))

    footer = (
        "Automatically compiled from configured regulatory email subscriptions. "
        "Please use the original source for verification."
    )
    if digest_id:
        footer += (
            "<br><span style='font-size:10px;color:#87919a;'>"
            f"Digest ID: {html.escape(digest_id)}</span>"
        )
    chunks.extend(
        [
            "</td></tr>",
            "<tr><td style='padding:14px 32px;background:#f7f9fa;border-top:1px solid #dde3e8;"
            f"font-size:11px;color:#7b8794;'>{footer}</td></tr>",
            "</table></td></tr></table></body></html>",
        ]
    )
    return "".join(chunks)


def section_lines_text(spec: SectionSpec, section_items: list[DigestItem]) -> list[str]:
    lines = [spec.heading, "-"]
    for item in section_items:
        lines.extend([item.title, item.summary, ""])
    return lines


def standard_item_lines_text(item: DigestItem) -> list[str]:
    return [item.title, item.summary, public_source_line(item) or item.source_label, ""]


def render_text(
    items: list[DigestItem],
    config: dict,
    start: datetime,
    end: datetime,
    digest_id: str | None = None,
) -> str:
    lines = [
        "WEEKLY CLEAN FUELS REGULATORY UPDATE",
        f"Reporting period: {human_period(start, end)}",
        f"Updates identified: {len(items)}",
        "",
    ]
    program_rows = sorted(
        config["programs"], key=lambda row: (row["country_order"], row["program_order"])
    )
    grouped = group_by_program(items, program_rows)

    current_country = None
    for program in program_rows:
        if program["country"] != current_country:
            current_country = program["country"]
            lines.extend([current_country.upper(), "=" * len(current_country), ""])

        lines.append(program["name"])
        program_items = grouped[program["id"]]
        if not program_items:
            lines.extend([NO_UPDATES_TEXT, ""])
            continue

        layout = layout_program(program_items)
        for index, (spec, section_items) in enumerate(layout.sections):
            lines.extend(section_lines_text(spec, section_items))
            if spec.cluster and layout.cluster_last_index.get(spec.cluster) == index:
                source_line = public_source_line(layout.clusters[spec.cluster])
                if source_line:
                    lines.extend([source_line, ""])

        for item in layout.standard:
            lines.extend(standard_item_lines_text(item))

    body = "\n".join(lines)
    if digest_id:
        body = f"{body.rstrip()}\n\nDigest ID: {digest_id}\n"
    return body
