from __future__ import annotations

import base64
import logging
import re
import time
from datetime import datetime
from email.message import EmailMessage
from email.utils import parseaddr
from functools import partial
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google_auth_httplib2 import AuthorizedHttp
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import httplib2

from .shared_digest_models import RawEmail


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def gmail_service(config: dict):
    request_timeout = float(config.get("ai", {}).get("request_timeout_seconds", 90))
    credentials_path = PROJECT_ROOT / config.get("paths", {}).get(
        "gmail_credentials", "runtime/secrets/credentials.json"
    )
    token_path = PROJECT_ROOT / config.get("paths", {}).get(
        "gmail_token", "runtime/secrets/token.json"
    )
    token_path.parent.mkdir(parents=True, exist_ok=True)

    credentials: Credentials | None = None
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if credentials and credentials.expired and credentials.refresh_token:
        # google-auth's Request takes no constructor arguments; timeout belongs
        # to its callable HTTP request. Bind it here for the token refresh call.
        try:
            credentials.refresh(partial(Request(), timeout=request_timeout))
        except RefreshError as exc:
            if "invalid_grant" not in str(exc):
                raise
            logging.warning(
                "Saved Gmail refresh token is invalid or revoked; starting OAuth login."
            )
            credentials = None
    if not credentials or not credentials.valid:
        if not credentials_path.exists():
            raise FileNotFoundError(
                f"Google OAuth credentials not found: {credentials_path}. See README.md."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
        credentials = flow.run_local_server(port=0)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    authorized_http = AuthorizedHttp(
        credentials, http=httplib2.Http(timeout=request_timeout)
    )
    return build("gmail", "v1", http=authorized_http, cache_discovery=False)


def build_sender_index(config: dict) -> tuple[dict[str, dict], list[str]]:
    sender_index: dict[str, dict] = {}
    senders: list[str] = []
    for program in config["programs"]:
        configured_senders = program.get("senders") or [program["sender"]]
        for sender in configured_senders:
            normalized_sender = sender.strip().lower()
            if normalized_sender in sender_index:
                raise ValueError(
                    f"The same sender is assigned twice: {normalized_sender}"
                )
            sender_index[normalized_sender] = program
            senders.append(normalized_sender)
    return sender_index, senders


def list_message_ids(
    service,
    senders: list[str],
    start: datetime,
    end: datetime,
    deadline: float | None = None,
) -> list[str]:
    sender_query = "{" + " ".join(f"from:{sender}" for sender in senders) + "}"
    query = (
        f"{sender_query} after:{int(start.timestamp())} before:{int(end.timestamp())}"
    )
    logging.info("Gmail query period: %s to %s", start.isoformat(), end.isoformat())
    ids: list[str] = []
    page_token = None
    while True:
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("Overall digest run time budget expired during Gmail search.")
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=500, pageToken=page_token)
            .execute()
        )
        ids.extend(message["id"] for message in response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    logging.info("Found %d candidate messages", len(ids))
    return ids


def decode_body(data: str | None) -> str:
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")


def collect_mime_parts(payload: dict) -> tuple[list[str], list[str]]:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    def walk(part: dict) -> None:
        mime_type = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data")
        if mime_type == "text/plain" and body_data:
            plain_parts.append(decode_body(body_data))
        elif mime_type == "text/html" and body_data:
            html_parts.append(decode_body(body_data))
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    return plain_parts, html_parts


TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
}


def canonicalize_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in TRACKING_QUERY_KEYS
        ]
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), ""))
    except ValueError:
        return url.strip()


def meaningful_links(html_parts: list[str], limit: int = 50) -> dict[str, str]:
    blocked_terms = (
        "unsubscribe",
        "subscription preferences",
        "manage preferences",
        "privacy policy",
        "view in browser",
        "facebook.com",
        "twitter.com",
        "linkedin.com",
        "instagram.com",
    )
    urls: list[str] = []
    seen: set[str] = set()
    for raw_html in html_parts:
        soup = BeautifulSoup(raw_html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = canonicalize_url(anchor["href"])
            label = " ".join(anchor.get_text(" ", strip=True).split())
            combined = f"{label} {href}".lower()
            if not href.startswith(("http://", "https://")):
                continue
            if any(term in combined for term in blocked_terms):
                continue
            if href not in seen:
                seen.add(href)
                urls.append(href)
            if len(urls) >= limit:
                break
        if len(urls) >= limit:
            break
    return {f"L{index}": url for index, url in enumerate(urls, start=1)}


def html_to_text(html_parts: list[str]) -> str:
    chunks: list[str] = []
    for raw_html in html_parts:
        soup = BeautifulSoup(raw_html, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        text = soup.get_text("\n")
        lines = [" ".join(line.split()) for line in text.splitlines()]
        chunks.append("\n".join(line for line in lines if line))
    return "\n".join(chunks)


def parse_message(service, message_id: str, timezone_name: str) -> RawEmail:
    message = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    headers = {
        header["name"].lower(): header["value"]
        for header in message.get("payload", {}).get("headers", [])
    }
    sender = parseaddr(headers.get("from", ""))[1].lower()
    subject = headers.get("subject", "(No subject)")
    received_at = datetime.fromtimestamp(
        int(message["internalDate"]) / 1000, tz=ZoneInfo(timezone_name)
    )
    plain_parts, html_parts = collect_mime_parts(message.get("payload", {}))
    body = "\n".join(part.strip() for part in plain_parts if part.strip())
    if not body:
        body = html_to_text(html_parts)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return RawEmail(
        message_id=message_id,
        sender=sender,
        subject=subject,
        received_at=received_at,
        body=body,
        links=meaningful_links(html_parts),
        gmail_url=f"https://mail.google.com/mail/u/0/#all/{message_id}",
    )


def send_digest(
    service, config: dict, subject: str, html_body: str, text_body: str, digest_id: str
) -> str:
    """Send the multipart digest and return the provider message ID.

    This belongs to the mail adapter, not to the orchestrator: the rebuild
    specification assigns ``send_multipart_email`` to the provider boundary. The
    ``Message-ID`` is derived from the digest ID so a delivered digest stays
    identifiable without relying on the subject line.
    """
    message = EmailMessage()
    message["To"] = config["mailbox"]["recipient"]
    message["From"] = config["mailbox"]["sender"]
    message["Subject"] = subject
    message["Message-ID"] = f"<{digest_id}@weekly-clean-fuels-digest.local>"
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    response = (
        service.users().messages().send(userId="me", body={"raw": encoded}).execute()
    )
    return response["id"]



