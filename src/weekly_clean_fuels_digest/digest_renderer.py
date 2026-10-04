from __future__ import annotations

import html
from datetime import datetime, timedelta

from .shared_digest_models import DigestItem


def human_period(start: datetime, end: datetime) -> str:
    inclusive_end = end.date() - timedelta(days=1)
    if start.year == inclusive_end.year:
        if start.month == inclusive_end.month:
            return f"{start.strftime('%B')} {start.day}–{inclusive_end.day}, {start.year}"
        return f"{start.strftime('%B')} {start.day}–{inclusive_end.strftime('%B')} {inclusive_end.day}, {start.year}"
    return f"{start.strftime('%B')} {start.day}, {start.year}–{inclusive_end.strftime('%B')} {inclusive_end.day}, {inclusive_end.year}"


def render_html(items: list[DigestItem], config: dict, start: datetime, end: datetime) -> str:
    period = human_period(start, end)
    program_rows = sorted(
        config["programs"], key=lambda row: (row["country_order"], row["program_order"])
    )
    by_program: dict[str, list[DigestItem]] = {row["id"]: [] for row in program_rows}
    for item in items:
        by_program[item.program_id].append(item)

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
            chunks.append(
                f"<div style='margin-top:22px;padding:9px 12px;background:#123524;color:#ffffff;"
                f"font-size:19px;font-weight:700;'>{html.escape(country)}</div>"
            )
        program_items = by_program[program["id"]]
        count_label = f" · {len(program_items)} update{'s' if len(program_items) != 1 else ''}"
        chunks.append(
            f"<div style='margin-top:22px;font-size:17px;font-weight:700;color:#166534;'>"
            f"{html.escape(program['name'])}<span style='font-weight:400;color:#68737d;'>"
            f"{html.escape(count_label)}</span></div>"
        )
        if not program_items:
            chunks.append(
                "<div style='margin:10px 0 18px;padding:14px 16px;background:#f7f9fa;"
                "border-left:3px solid #b8c2cc;color:#52606d;font-size:14px;font-style:italic;'>"
                "No relevant updates identified this week.</div>"
            )
            continue
        local_pathways = [
            item for item in program_items
            if (item.source_group or item.source_label) == "Newly Certified Pathways"
        ]
        pathway_updates = [
            item for item in program_items
            if (item.source_group or item.source_label) == "Existing Pathway Updates"
        ]
        guidance_updates = [
            item for item in program_items
            if (item.source_group or item.source_label) == "Guidance Updates"
        ]
        standard_items = [
            item
            for item in program_items
            if (item.source_group or item.source_label)
            not in {"Newly Certified Pathways", "Existing Pathway Updates", "Guidance Updates"}
        ]
        if local_pathways:
            chunks.append(
                "<div style='margin-top:16px;padding:10px 12px;background:#eaf4ec;"
                "border-left:4px solid #166534;font-size:15px;font-weight:700;color:#123524;'>"
                "Newly Certified Pathway(s)</div>"
            )
            for index, item in enumerate(local_pathways):
                border = "border-top:1px solid #e5e9ed;" if index else ""
                summary_html = html.escape(item.summary).replace("\n", "<br>")
                chunks.append(
                    f"<div style='padding:15px 0 17px;{border}'>"
                    f"<div style='font-size:15px;font-weight:700;line-height:1.4;color:#1f2933;'>"
                    f"{html.escape(item.title)}</div>"
                    f"<div style='margin-top:7px;font-size:14px;line-height:1.65;color:#364152;'>"
                    f"{summary_html}</div></div>"
                )
        if pathway_updates:
            chunks.append(
                "<div style='margin-top:16px;padding:10px 12px;background:#eaf4ec;"
                "border-left:4px solid #166534;font-size:15px;font-weight:700;color:#123524;'>"
                "Existing Pathway Updates</div>"
            )
            for index, item in enumerate(pathway_updates):
                border = "border-top:1px solid #e5e9ed;" if index else ""
                summary_html = html.escape(item.summary).replace("\n", "<br>")
                chunks.append(
                    f"<div style='padding:15px 0 17px;{border}'>"
                    f"<div style='font-size:15px;font-weight:700;line-height:1.4;color:#1f2933;'>"
                    f"{html.escape(item.title)}</div>"
                    f"<div style='margin-top:7px;font-size:14px;line-height:1.65;color:#364152;'>"
                    f"{summary_html}</div></div>"
                )
        california_local_items = local_pathways + pathway_updates
        if california_local_items:
            public_url = california_local_items[0].source_url
            if public_url.startswith(("https://", "http://")):
                chunks.append(
                    f"<div style='margin:0 0 18px;font-size:13px;'><a href='"
                    f"{html.escape(public_url, quote=True)}' "
                    "style='color:#1261a0;text-decoration:none;font-weight:600;'>"
                    "View original source →</a></div>"
                )

        if guidance_updates:
            chunks.append(
                "<div style='margin-top:16px;padding:10px 12px;background:#eaf4ec;"
                "border-left:4px solid #166534;font-size:15px;font-weight:700;color:#123524;'>"
                "Guidance Updates</div>"
            )
            for index, item in enumerate(guidance_updates):
                border = "border-top:1px solid #e5e9ed;" if index else ""
                chunks.append(
                    f"<div style='padding:15px 0 17px;{border}'>"
                    f"<div style='font-size:15px;font-weight:700;line-height:1.4;color:#1f2933;'>"
                    f"{html.escape(item.title)}</div>"
                    f"<div style='margin-top:7px;font-size:14px;line-height:1.55;color:#364152;'>"
                    f"{html.escape(item.summary)}</div></div>"
                )
            public_url = guidance_updates[0].source_url
            if public_url.startswith(("https://", "http://")):
                chunks.append(
                    f"<div style='margin:0 0 18px;font-size:13px;'><a href='"
                    f"{html.escape(public_url, quote=True)}' "
                    "style='color:#1261a0;text-decoration:none;font-weight:600;'>"
                    "View original source →</a></div>"
                )

        for index, item in enumerate(standard_items):
            border = "border-top:1px solid #e5e9ed;" if index else ""
            if item.source_url.startswith(("https://", "http://")):
                source_html = (
                    f"<a href='{html.escape(item.source_url, quote=True)}' "
                    "style='color:#1261a0;text-decoration:none;font-weight:600;'>"
                    "View original source →</a>"
                )
            else:
                source_html = html.escape(item.source_label)
            chunks.append(
                f"<div style='padding:15px 0 17px;{border}'>"
                f"<div style='font-size:15px;font-weight:700;line-height:1.4;color:#1f2933;'>"
                f"{html.escape(item.title)}</div>"
                f"<div style='margin-top:7px;font-size:14px;line-height:1.55;color:#364152;'>"
                f"{html.escape(item.summary)}</div>"
                f"<div style='margin-top:9px;font-size:13px;color:#52606d;'>{source_html}</div>"
                "</div>"
            )

    chunks.extend(
        [
            "</td></tr>",
            "<tr><td style='padding:14px 32px;background:#f7f9fa;border-top:1px solid #dde3e8;"
            "font-size:11px;color:#7b8794;'>Automatically compiled from configured regulatory email subscriptions. "
            "Please use the original source for verification.</td></tr>",
            "</table></td></tr></table></body></html>",
        ]
    )
    return "".join(chunks)


def render_text(items: list[DigestItem], config: dict, start: datetime, end: datetime) -> str:
    lines = [
        "WEEKLY CLEAN FUELS REGULATORY UPDATE",
        f"Reporting period: {human_period(start, end)}",
        f"Updates identified: {len(items)}",
        "",
    ]
    program_rows = sorted(
        config["programs"], key=lambda row: (row["country_order"], row["program_order"])
    )
    current_country = None
    for program in program_rows:
        if program["country"] != current_country:
            current_country = program["country"]
            lines.extend([current_country.upper(), "=" * len(current_country), ""])
        selected = [item for item in items if item.program_id == program["id"]]
        lines.append(program["name"])
        if not selected:
            lines.extend(["No relevant updates identified this week.", ""])
        else:
            local_pathways = [
                item for item in selected
                if (item.source_group or item.source_label) == "Newly Certified Pathways"
            ]
            pathway_updates = [
                item for item in selected
                if (item.source_group or item.source_label) == "Existing Pathway Updates"
            ]
            guidance_updates = [
                item for item in selected
                if (item.source_group or item.source_label) == "Guidance Updates"
            ]
            standard_items = [
                item
                for item in selected
                if (item.source_group or item.source_label)
                not in {"Newly Certified Pathways", "Existing Pathway Updates", "Guidance Updates"}
            ]
            if local_pathways:
                lines.extend(["Newly Certified Pathway(s)", "-"])
                for item in local_pathways:
                    lines.extend([item.title, item.summary, ""])
            if pathway_updates:
                lines.extend(["Existing Pathway Updates", "-"])
                for item in pathway_updates:
                    lines.extend([item.title, item.summary, ""])
            california_local_items = local_pathways + pathway_updates
            if california_local_items:
                lines.extend(
                    [f"View original source: {california_local_items[0].source_url}", ""]
                )
            if guidance_updates:
                lines.extend(["Guidance Updates", "-"])
                for item in guidance_updates:
                    lines.extend([item.title, item.summary, ""])
                lines.extend(
                    [f"View original source: {guidance_updates[0].source_url}", ""]
                )
            for item in standard_items:
                source_text = (
                    f"View original source: {item.source_url}"
                    if item.source_url.startswith(("https://", "http://"))
                    else item.source_label
                )
                lines.extend([item.title, item.summary, source_text, ""])
    return "\n".join(lines)



