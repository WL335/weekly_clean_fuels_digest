from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from logging.handlers import RotatingFileHandler

import yaml

from .alerts import AlertSettings, clear_failure_record, report_failure
from .digest_renderer import human_period, render_html, render_text
from .gmail_source import (
    build_sender_index,
    canonicalize_url,
    gmail_service,
    list_message_ids,
    parse_message,
    send_digest,
)
from .integrations import local_digest as local_digest_integration
from .openai_analyzer import analyze_email
from .shared_digest_models import (
    DigestItem,
    EmailAnalysis,
    RawEmail,
)
from .state_store import load_state, save_state


ROOT = Path(__file__).resolve().parents[2]
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the weekly clean-fuels regulatory email digest."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "config.yaml",
        help="YAML configuration file.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send the digest and record processed items. Without this flag, only preview it.",
    )
    parser.add_argument(
        "--start", help="Optional inclusive start date, YYYY-MM-DD, in the configured timezone."
    )
    parser.add_argument(
        "--end", help="Optional exclusive end date, YYYY-MM-DD, in the configured timezone."
    )
    parser.add_argument(
        "--include-processed",
        action="store_true",
        help="Include items that were already sent in an earlier digest.",
    )
    parser.add_argument(
        "--resolve-pending",
        metavar="DIGEST_ID",
        help="Resolve an ambiguous pending send transaction without sending mail.",
    )
    parser.add_argument(
        "--resolution",
        choices=("sent", "not-sent"),
        help="Required with --resolve-pending: mark it sent, or confirm it was not sent.",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a YAML object: {path}")
    required = ["mailbox", "schedule", "ai", "programs"]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Missing config sections: {', '.join(missing)}")
    for section in ("mailbox", "schedule", "ai"):
        if not isinstance(config[section], dict):
            raise ValueError(f"Configuration section {section!r} must be an object.")
    for section in ("paths", "integrations"):
        if section in config and not isinstance(config[section], dict):
            raise ValueError(f"Configuration section {section!r} must be an object.")
    mailbox = config["mailbox"]
    for field in ("sender", "recipient"):
        if not isinstance(mailbox.get(field), str) or not mailbox[field].strip():
            raise ValueError(f"Configuration mailbox.{field} must be a non-empty string.")
    timezone_name = config["schedule"].get("timezone", "America/Regina")
    try:
        ZoneInfo(timezone_name)
    except (TypeError, KeyError) as exc:
        raise ValueError(f"Invalid schedule.timezone: {timezone_name!r}") from exc
    if not isinstance(config["ai"].get("model"), str) or not config["ai"]["model"].strip():
        raise ValueError("Configuration ai.model must be a non-empty string.")
    for field, default in (
        ("max_email_characters", 30000),
        ("retry_attempts", 3),
        ("request_timeout_seconds", 90),
        ("run_timeout_seconds", 3300),
    ):
        try:
            if float(config["ai"].get(field, default)) <= 0:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Configuration ai.{field} must be positive.") from exc
    if not isinstance(config["programs"], list) or not config["programs"]:
        raise ValueError("Configuration programs must be a non-empty list.")
    program_ids: set[str] = set()
    for index, program in enumerate(config["programs"]):
        if not isinstance(program, dict):
            raise ValueError(f"Configuration programs[{index}] must be an object.")
        for field in ("id", "name", "country"):
            if not isinstance(program.get(field), str) or not program[field].strip():
                raise ValueError(f"Configuration programs[{index}].{field} is required.")
        if program["id"] in program_ids:
            raise ValueError(f"Duplicate program id: {program['id']}")
        program_ids.add(program["id"])
        if not (program.get("sender") or program.get("senders")):
            raise ValueError(f"Configuration program {program['id']} has no sender.")
        if "senders" in program and (
            not isinstance(program["senders"], list)
            or not all(isinstance(sender, str) and sender.strip() for sender in program["senders"])
        ):
            raise ValueError(f"Configuration program {program['id']} has invalid senders.")
        for order in ("country_order", "program_order"):
            if not isinstance(program.get(order), int):
                raise ValueError(f"Configuration program {program['id']} needs integer {order}.")
    for field, default in (("log_max_bytes", 5_000_000), ("log_backup_count", 5)):
        value = config.get("paths", {}).get(field, default)
        if not isinstance(value, int) or value < 0 or (field == "log_max_bytes" and value == 0):
            raise ValueError(f"Configuration paths.{field} has an invalid value.")
    alerts = config.get("alerts", {})
    if not isinstance(alerts, dict):
        raise ValueError("Configuration section 'alerts' must be an object.")
    for field in ("popup_enabled", "desktop_marker_enabled", "event_log_enabled"):
        if field in alerts and not isinstance(alerts[field], bool):
            raise ValueError(f"Configuration alerts.{field} must be true or false.")
    try:
        if float(alerts.get("grace_hours", 6)) <= 0:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValueError("Configuration alerts.grace_hours must be positive.") from exc
    armed_from = alerts.get("watchdog_armed_from")
    if armed_from not in (None, ""):
        try:
            date.fromisoformat(str(armed_from))
        except ValueError as exc:
            raise ValueError(
                "Configuration alerts.watchdog_armed_from must be a YYYY-MM-DD date "
                "or empty."
            ) from exc
    sources = config.get("local_digest_sources", [])
    if not isinstance(sources, list):
        raise ValueError("Configuration local_digest_sources must be a list.")
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or not source.get("program_id") or not source.get("directory"):
            raise ValueError(f"Configuration local_digest_sources[{index}] needs program_id and directory.")
        if source["program_id"] not in program_ids:
            raise ValueError(
                f"Configuration local_digest_sources[{index}] references unknown program "
                f"{source['program_id']}."
            )
    return config


def setup_logging(config: dict) -> None:
    log_path = ROOT / config.get("paths", {}).get(
        "log_file", "runtime/logs/weekly_digest.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            RotatingFileHandler(
                log_path,
                maxBytes=int(config.get("paths", {}).get("log_max_bytes", 5_000_000)),
                backupCount=int(config.get("paths", {}).get("log_backup_count", 5)),
                encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )


def reporting_window(
    timezone_name: str,
    start_override: str | None,
    end_override: str | None,
    period_days: int = 7,
) -> tuple[datetime, datetime]:
    tz = ZoneInfo(timezone_name)
    if period_days < 1:
        raise ValueError("period_days must be a positive integer.")
    if bool(start_override) != bool(end_override):
        raise ValueError("Use --start and --end together.")
    if start_override and end_override:
        start_day = date.fromisoformat(start_override)
        end_day = date.fromisoformat(end_override)
    else:
        today = datetime.now(tz).date()
        days_since_friday = (today.weekday() - 4) % 7
        end_day = today - timedelta(days=days_since_friday)
        # If run before Friday, use the Friday that began the current partial week,
        # then back up one full week to obtain the last completed Fri-Thu period.
        if end_day == today and today.weekday() == 4:
            pass
        start_day = end_day - timedelta(days=period_days)
    start = datetime.combine(start_day, dt_time.min, tzinfo=tz)
    end = datetime.combine(end_day, dt_time.min, tzinfo=tz)
    if end <= start:
        raise ValueError("The end date must be after the start date.")
    return start, end


def normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t\r\n-–—|")


def item_identity(
    program_id: str,
    title: str,
    source_url: str,
    source_kind: str = "email",
    source_item_id: str | None = None,
) -> str:
    if source_kind == "local_digest":
        local_identity = source_item_id or hashlib.sha256(
            f"{normalize_title(title).casefold()}|{canonicalize_url(source_url)}".encode("utf-8")
        ).hexdigest()
        material = f"{program_id}|local-digest:v2|{local_identity}"
    else:
        # Preserve the original email identity so existing sent_items keys remain valid.
        material = f"{program_id}|{canonicalize_url(source_url)}|{normalize_title(title).lower()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def digest_identity(
    config: dict, start: datetime, end: datetime, include_processed: bool = False
) -> str:
    material = {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "sender": config["mailbox"]["sender"],
        "recipient": config["mailbox"]["recipient"],
        "model": config["ai"]["model"],
        "programs": [row["id"] for row in config["programs"]],
    }
    if include_processed:
        material["include_processed"] = True
    fingerprint = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]
    return f"wcf-{fingerprint}"


def resolve_pending_transaction(
    state: dict, digest_id: str, resolution: str, timezone_name: str
) -> None:
    transactions = state.get("send_transactions", {})
    transaction = transactions.get(digest_id)
    if not isinstance(transaction, dict) or transaction.get("status") != "sending":
        raise ValueError(f"No unresolved sending transaction found for {digest_id}.")
    resolved_at = datetime.now(ZoneInfo(timezone_name)).isoformat()
    transaction["resolved_at"] = resolved_at
    transaction["resolution"] = resolution
    if resolution == "sent":
        transaction["status"] = "sent"
        transaction["sent_at"] = resolved_at
        state.setdefault("sent_items", {})
        for item in transaction.get("items", []):
            state["sent_items"][item["item_key"]] = {
                "sent_at": resolved_at,
                "title": item["title"],
                "program_id": item["program_id"],
                "source_url": item["source_url"],
                "source_kind": item.get("source_kind", "email"),
                "source_item_id": item.get("source_item_id"),
            }
    else:
        transaction["status"] = "resolved_not_sent"


def convert_items(
    raw: RawEmail,
    program: dict,
    analysis: EmailAnalysis | local_digest_integration.LocalDigestAnalysis,
) -> list[DigestItem]:
    converted: list[DigestItem] = []
    for result in analysis.items:
        title = normalize_title(result.title)
        if raw.source_kind == "local_digest":
            summary = "\n".join(
                " ".join(line.split()) for line in result.summary.splitlines() if line.strip()
            )
        else:
            summary = " ".join(result.summary.split())
        if not title or not summary:
            continue
        source_url = raw.links.get(result.source_link_id or "", raw.gmail_url)
        source_item_id = getattr(result, "source_item_id", None)
        source_group = getattr(result, "source_group", None)
        key = item_identity(
            program["id"],
            title,
            source_url,
            raw.source_kind,
            source_item_id,
        )
        converted.append(
            DigestItem(
                country=program["country"],
                country_order=int(program["country_order"]),
                program_id=program["id"],
                program_name=program["name"],
                program_order=int(program["program_order"]),
                title=title,
                summary=summary,
                source_url=source_url,
                source_label=raw.source_label,
                source_message_id=raw.message_id,
                received_at=raw.received_at.isoformat(),
                confidence=result.confidence,
                item_key=key,
                source_kind=raw.source_kind,
                source_item_id=source_item_id,
                source_group=(
                    source_group or raw.source_label
                    if raw.source_kind == "local_digest"
                    else None
                ),
            )
        )
    return converted


def deduplicate(items: list[DigestItem]) -> list[DigestItem]:
    unique: dict[str, DigestItem] = {}
    for item in items:
        current = unique.get(item.item_key)
        if current is None or len(item.summary) > len(current.summary):
            unique[item.item_key] = item
    return sorted(
        unique.values(),
        key=lambda item: (item.country_order, item.program_order, item.received_at, item.title.lower()),
    )


def preview_paths(config: dict) -> tuple[Path, Path, Path]:
    directory = ROOT / config.get("paths", {}).get(
        "preview_directory", "runtime/output"
    )
    directory.mkdir(parents=True, exist_ok=True)
    return (
        directory / "weekly_digest_preview.html",
        directory / "weekly_digest_preview.txt",
        directory / "weekly_digest_items.json",
    )


def write_preview(html_body: str, text_body: str, items: list[DigestItem], config: dict) -> None:
    html_path, text_path, json_path = preview_paths(config)
    html_path.write_text(html_body, encoding="utf-8")
    text_path.write_text(text_body, encoding="utf-8")
    json_path.write_text(
        json.dumps([asdict(item) for item in items], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logging.info("Preview written to %s", html_path)


EXIT_RUNTIME_FAILURE = 1
EXIT_CONFIG_FAILURE = 2


def main() -> int:
    args = parse_args()
    stage = {"name": "startup"}
    settings = AlertSettings()

    def fail(exc: BaseException, exit_code: int, context: dict | None = None) -> int:
        """Report a failed run through every alert channel, then return the code."""
        return report_failure(
            exc=exc,
            stage=stage["name"],
            settings=settings,
            project_root=ROOT,
            mode="send" if args.send else "preview",
            exit_code=exit_code,
            notify_operator=bool(args.send),
            context=context,
        )

    try:
        config = load_config(args.config)
        setup_logging(config)
        settings = AlertSettings.from_config(config)
        run_timeout = float(config["ai"].get("run_timeout_seconds", 3300))
        if run_timeout <= 0:
            raise ValueError("ai.run_timeout_seconds must be positive.")
        run_deadline = time.monotonic() + run_timeout
        config["_run_deadline_monotonic"] = run_deadline
        timezone_name = config["schedule"].get("timezone", "America/Regina")
        start, end = reporting_window(timezone_name, args.start, args.end)
        sender_index, senders = build_sender_index(config)
        state = load_state(config, ROOT)
        if not args.resolve_pending and not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. See README.md for the Windows setup command."
            )
    except Exception as exc:
        logging.exception("Startup failed")
        return fail(exc, EXIT_CONFIG_FAILURE)

    def ensure_run_budget(stage_name: str) -> None:
        stage["name"] = stage_name
        remaining = run_deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f"Run time budget exhausted before {stage_name}.")

    if args.resolve_pending:
        if not args.resolution:
            return fail(
                ValueError(
                    "Use --resolution sent or --resolution not-sent with --resolve-pending."
                ),
                EXIT_CONFIG_FAILURE,
            )
        try:
            stage["name"] = "resolve pending transaction"
            resolve_pending_transaction(
                state, args.resolve_pending, args.resolution, timezone_name
            )
            save_state(config, state, ROOT)
        except Exception as exc:
            logging.exception("Could not resolve pending transaction")
            return fail(exc, EXIT_CONFIG_FAILURE, {"digest_id": args.resolve_pending})
        print(f"Resolved {args.resolve_pending} as {args.resolution}; no email was sent.")
        return 0
    if args.resolution:
        return fail(
            ValueError("--resolution requires --resolve-pending."), EXIT_CONFIG_FAILURE
        )

    try:
        ensure_run_budget("Gmail connection")
        service = gmail_service(config)
        ensure_run_budget("Gmail message listing")
        message_ids = list_message_ids(service, senders, start, end, deadline=run_deadline)
        collected: list[DigestItem] = []
        for position, message_id in enumerate(message_ids, start=1):
            ensure_run_budget("Gmail message parsing")
            raw = parse_message(service, message_id, timezone_name)
            if not (start <= raw.received_at < end):
                continue
            program = sender_index.get(raw.sender)
            if not program:
                continue
            logging.info(
                "Analyzing %d/%d: %s | %s", position, len(message_ids), program["id"], raw.subject
            )
            try:
                ensure_run_budget("email analysis")
                analysis = analyze_email(raw, program, config)
                collected.extend(convert_items(raw, program, analysis))
            except Exception:
                logging.exception("Could not analyze Gmail message %s", raw.message_id)
                raise

        local_digest_enabled = config.get("integrations", {}).get(
            "local_digest_enabled", True
        )
        if local_digest_enabled:
            stage["name"] = "local digest discovery"
            local_messages = local_digest_integration.load_local_digest_messages(
                config, start, end, ROOT
            )
            logging.info("Found %d matching local digest files", len(local_messages))
            for position, (raw, program) in enumerate(local_messages, start=1):
                ensure_run_budget("local digest analysis")
                logging.info(
                    "Analyzing local digest %d/%d: %s | %s",
                    position,
                    len(local_messages),
                    program["id"],
                    raw.subject,
                )
                try:
                    analysis = local_digest_integration.analyze_local_digest(raw)
                    collected.extend(convert_items(raw, program, analysis))
                except Exception:
                    logging.exception("Could not process local digest %s", raw.source_label)
                    raise
        else:
            logging.info("Local digest integration is disabled by configuration.")

        items = deduplicate(collected)
        if not args.include_processed:
            sent_items = state.get("sent_items", {})
            items = [item for item in items if item.item_key not in sent_items]

        stage["name"] = "rendering"
        digest_id = digest_identity(config, start, end, args.include_processed)
        html_body = render_html(items, config, start, end, digest_id)
        text_body = render_text(items, config, start, end, digest_id)
        stage["name"] = "preview output"
        write_preview(html_body, text_body, items, config)

        if args.send:
            ensure_run_budget("email delivery")
            transactions = state.setdefault("send_transactions", {})
            pending_ids = [
                key for key, value in transactions.items()
                if value.get("status") == "sending"
            ]
            if pending_ids:
                raise RuntimeError(
                    "Unresolved send transaction(s) block automatic sending: "
                    + ", ".join(pending_ids)
                    + ". Resolve with --resolve-pending <DIGEST_ID> --resolution sent|not-sent."
                )
            current_transaction = transactions.get(digest_id)
            if current_transaction and current_transaction.get("status") == "sent":
                raise RuntimeError(
                    f"Digest {digest_id} has already been sent. Use a new reporting period, "
                    "or use --include-processed for one deliberate test resend."
                )
            if not args.include_processed:
                sent_period_ids = [
                    key for key, value in transactions.items()
                    if value.get("status") == "sent"
                    and value.get("period_start") == start.isoformat()
                    and value.get("period_end") == end.isoformat()
                ]
                if sent_period_ids:
                    raise RuntimeError(
                        "A digest for this reporting period was already sent: "
                        + ", ".join(sent_period_ids)
                    )
            subject_template = config["mailbox"].get(
                "subject", "Weekly Clean Fuels Regulatory Update | {period}"
            )
            subject = subject_template.format(period=human_period(start, end))
            transaction = {
                "status": "sending",
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "subject": subject,
                "started_at": datetime.now(ZoneInfo(timezone_name)).isoformat(),
                "items": [
                    {
                        "item_key": item.item_key,
                        "title": item.title,
                        "program_id": item.program_id,
                        "source_url": item.source_url,
                        "source_kind": item.source_kind,
                        "source_item_id": item.source_item_id,
                    }
                    for item in items
                ],
            }
            transactions[digest_id] = transaction
            stage["name"] = "recording send transaction"
            save_state(config, state, ROOT)
            sent_message_id = send_digest(
                service, config, subject, html_body, text_body, digest_id
            )
            sent_at = datetime.now(ZoneInfo(timezone_name)).isoformat()
            stage["name"] = "recording sent items"
            state.setdefault("sent_items", {})
            for item in items:
                state["sent_items"][item.item_key] = {
                    "sent_at": sent_at,
                    "title": item.title,
                    "program_id": item.program_id,
                    "source_url": item.source_url,
                    "source_kind": item.source_kind,
                    "source_item_id": item.source_item_id,
                }
            transaction["status"] = "sent"
            transaction["sent_at"] = sent_at
            transaction["gmail_message_id"] = sent_message_id
            state["last_run"] = {
                "sent_at": sent_at,
                "gmail_message_id": sent_message_id,
                "digest_id": digest_id,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "item_count": len(items),
            }
            save_state(config, state, ROOT)
            logging.info("Digest sent successfully. Gmail message ID: %s", sent_message_id)
        else:
            logging.info("Preview mode complete; no email sent and state was not changed.")
        clear_failure_record(ROOT)
        return 0
    except Exception as exc:
        # Deliberately broad: lazily loaded provider libraries raise their own types
        # (for example google.auth.exceptions.RefreshError, which is none of OSError,
        # ValueError, or RuntimeError), and an unattended weekly job must never fail
        # without notifying the operator.
        logging.exception("Weekly digest failed")
        return fail(exc, EXIT_RUNTIME_FAILURE)


if __name__ == "__main__":
    raise SystemExit(main())
