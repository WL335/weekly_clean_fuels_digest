from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExtractedItem(BaseModel):
    title: str = Field(
        description="The original item headline, lightly cleaned; do not invent a new headline."
    )
    summary: str = Field(
        description="A factual one- or two-sentence summary grounded only in the source."
    )
    source_link_id: str | None = Field(
        default=None,
        description="An ID such as L3 from the supplied allowed links, or null.",
    )
    confidence: Literal["high", "medium", "low"]


class EmailAnalysis(BaseModel):
    items: list[ExtractedItem] = Field(
        description="Only items directly relevant to the specified regulatory program."
    )


@dataclass
class RawEmail:
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    body: str
    links: dict[str, str]
    gmail_url: str
    source_label: str = "View original source"
    source_kind: Literal["email", "local_digest"] = "email"


@dataclass
class DigestItem:
    country: str
    country_order: int
    program_id: str
    program_name: str
    program_order: int
    title: str
    summary: str
    source_url: str
    source_label: str
    source_message_id: str
    received_at: str
    confidence: str
    item_key: str
    source_kind: Literal["email", "local_digest"] = "email"
    source_item_id: str | None = None
    source_group: str | None = None
