from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..shared_digest_models import RawEmail


@dataclass
class LocalDigestItem:
    title: str
    summary: str
    source_link_id: str | None
    confidence: str
    source_item_id: str
    source_group: str


@dataclass
class LocalDigestAnalysis:
    items: list[LocalDigestItem]


def _normalized_identity_value(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _pathway_identity(pathway: dict, duplicate_row: object = None) -> str:
    """Prefer a source ID; otherwise hash stable pathway fields, never CI or row position.

    Row number is only a last-resort tie-breaker for identical duplicate rows in one
    workbook. That favors a visible duplicate over silently collapsing two records.
    """
    for key in ("pathway_id", "Pathway ID", "Pathway ID (ID)"):
        value = _normalized_identity_value(pathway.get(key))
        if value:
            return f"pathway-id:{value}"

    stable_fields = {
        key: _normalized_identity_value(pathway.get(key))
        for key in ("Company (ID)", "Fuel Category", "Class", "Pathway Description")
    }
    stable_fields = {key: value for key, value in stable_fields.items() if value}
    material = json.dumps(stable_fields, sort_keys=True, separators=(",", ":"))
    identity = "pathway-fields:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    if duplicate_row is not None:
        identity += f":duplicate-row:{_normalized_identity_value(duplicate_row)}"
    return identity


def parse_local_timestamp(value: object, path: Path, timezone_name: str) -> datetime:
    tz = ZoneInfo(timezone_name)
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeError(f"Invalid generated timestamp in {path}: {value}") from exc
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=tz)
        return parsed.astimezone(tz)
    return datetime.fromtimestamp(path.stat().st_mtime, tz=tz)


def load_local_digest_messages(
    config: dict, start: datetime, end: datetime, project_root: Path
) -> list[tuple[RawEmail, dict]]:
    programs = {program["id"]: program for program in config["programs"]}
    timezone_name = config["schedule"].get("timezone", "America/Regina")
    messages: list[tuple[RawEmail, dict]] = []

    for source in config.get("local_digest_sources", []):
        program_id = source["program_id"]
        program = programs.get(program_id)
        if program is None:
            raise RuntimeError(
                f"Local digest source {source.get('id', '<unnamed>')} references "
                f"unknown program {program_id}"
            )

        directory = Path(source["directory"])
        if not directory.is_absolute():
            directory = project_root / directory
        if not directory.exists():
            logging.warning("Local digest directory does not exist: %s", directory)
            continue
        if not directory.is_dir():
            raise RuntimeError(f"Local digest path is not a directory: {directory}")

        pattern = source.get("pattern", "*.json")
        timestamp_field = source.get("timestamp_field", "generated_at")
        for path in sorted(directory.glob(pattern)):
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"Could not read local digest {path}: {exc}") from exc
            if not isinstance(payload, dict):
                raise RuntimeError(f"Local digest must contain a JSON object: {path}")

            generated_at = parse_local_timestamp(
                payload.get(timestamp_field), path, timezone_name
            )
            if not (start <= generated_at < end):
                continue

            configured_program_code = source.get("json_program")
            if configured_program_code and payload.get("program") != configured_program_code:
                logging.warning(
                    "Skipping local digest with unexpected program %r: %s",
                    payload.get("program"),
                    path,
                )
                continue

            document_name = str(payload.get("document_key") or path.stem).replace("_", " ")
            previous_version = payload.get("previous_version")
            current_version = payload.get("current_version")
            version_text = (
                f" ({previous_version} to {current_version})"
                if previous_version and current_version
                else ""
            )
            subject = f"{program['name']} local digest: {document_name}{version_text}"
            payload_source = payload.get("source")
            payload_source_url = (
                payload_source.get("source_page")
                if isinstance(payload_source, dict)
                else None
            )
            public_source_url = source.get("public_source_url") or payload_source_url
            stable_path = str(path.resolve()).lower()
            message_id = "local:" + hashlib.sha256(
                stable_path.encode("utf-8")
            ).hexdigest()[:24]
            messages.append(
                (
                    RawEmail(
                        message_id=message_id,
                        sender="local-digest",
                        subject=subject,
                        received_at=generated_at,
                        body=json.dumps(payload, indent=2, ensure_ascii=False),
                        links={},
                        gmail_url=public_source_url or path.resolve().as_uri(),
                        source_label=source.get(
                            "display_label", f"Local digest: {path.name}"
                        ),
                        source_kind="local_digest",
                    ),
                    program,
                )
            )
    return messages


def analyze_local_digest(raw: RawEmail) -> LocalDigestAnalysis:
    try:
        payload = json.loads(raw.body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid local digest JSON in {raw.source_label}") from exc

    if payload.get("program") == "BC_LCFS":
        document_key = " ".join(str(payload.get("document_key") or "").split())
        document_title = " ".join(
            str(payload.get("title") or "BC LCFS guidance update").split()
        )
        title = (
            f"{document_key} — {document_title}"
            if document_key and not document_title.lower().startswith(document_key.lower())
            else document_title
        )
        summary = " ".join(
            str(payload.get("digest_summary") or payload.get("summary") or "").split()
        )
        version = _normalized_identity_value(payload.get("current_version"))
        stable_id = f"bc-guidance:{document_key.casefold()}"
        if version:
            stable_id += f":version:{version}"
        else:
            stable_id += ":content:" + hashlib.sha256(
                f"{title}|{summary}".encode("utf-8")
            ).hexdigest()[:24]
        return LocalDigestAnalysis(
            items=[
                LocalDigestItem(
                    title=title,
                    summary=summary or "No summary provided.",
                    source_link_id=None,
                    confidence="high",
                    source_item_id=stable_id,
                    source_group="Guidance Updates",
                )
            ]
        )

    extracted: list[LocalDigestItem] = []
    added_pathways = payload.get("added_pathways", [])
    updated_pathways = payload.get("updated_pathways", [])
    for field_name, pathways in (
        ("added_pathways", added_pathways),
        ("updated_pathways", updated_pathways),
    ):
        if not isinstance(pathways, list):
            raise RuntimeError(f"{field_name} must be a list in {raw.source_label}")

        base_ids = [
            _pathway_identity(pathway)
            for pathway in pathways
            if isinstance(pathway, dict)
        ]
        duplicate_counts = Counter(base_ids)
        seen_ids: set[str] = set()
        for pathway in pathways:
            if not isinstance(pathway, dict):
                raise RuntimeError(f"Each pathway must be an object in {raw.source_label}")
            base_identity = _pathway_identity(pathway)
            identity = base_identity
            if duplicate_counts.get(base_identity, 0) > 1:
                # source_row distinguishes otherwise identical records in this source file.
                identity = _pathway_identity(pathway, pathway.get("source_row"))
                if identity == base_identity or identity in seen_ids:
                    identity += f":occurrence:{len(seen_ids) + 1}"
            seen_ids.add(identity)

            company = str(pathway.get("Company (ID)") or "Unknown company").strip()
            fuel = str(pathway.get("Fuel Category") or "LCFS fuel pathway").strip()
            pathway_class = str(pathway.get("Class") or "").strip()
            description = " ".join(str(pathway.get("Pathway Description") or "").split())
            class_suffix = f" ({pathway_class})" if pathway_class else ""
            title = f"{company} — {fuel}{class_suffix}"

            if field_name == "updated_pathways":
                old_ci = str(
                    pathway.get("Previous Certified CI")
                    or pathway.get("Previous CI")
                    or "Not stated"
                ).strip()
                new_ci = str(
                    pathway.get("Current Certified CI")
                    or pathway.get("Current CI")
                    or "Not stated"
                ).strip()
                summary_lines = [f"Certified CI updated: {old_ci} → {new_ci}"]
                source_group = "Existing Pathway Updates"
                version = _normalized_identity_value(payload.get("current_version"))
                identity += f":update:{version or raw.received_at.date().isoformat()}:{old_ci}->{new_ci}"
            else:
                ci = str(pathway.get("Current Certified CI") or "").strip()
                summary_lines = [f"Certified CI: {ci or 'Not stated'}"]
                source_group = "Newly Certified Pathways"
            summary_lines.append(f"Pathway Description: {description or 'Not stated'}")
            extracted.append(
                LocalDigestItem(
                    title=title,
                    summary="\n".join(summary_lines),
                    source_link_id=None,
                    confidence="high",
                    source_item_id=identity,
                    source_group=source_group,
                )
            )

    return LocalDigestAnalysis(items=extracted)
