"""Pydantic models for chat API request and response bodies."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str = Field(max_length=12_000)


class CitationPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    citation_index: int = Field(alias="citationIndex")
    chunk_id: uuid.UUID = Field(alias="chunkId")
    excerpt: str
    ticker: str
    company_name: str | None = Field(default=None, alias="companyName")
    form: str
    filing_date: date = Field(alias="filingDate")
    page: str | None = None
    section: str | None = None
    document_title: str | None = Field(default=None, alias="documentTitle")
    fiscal_year: int | None = Field(default=None, alias="fiscalYear")


class CitationPart(BaseModel):
    type: Literal["data-citation"] = "data-citation"
    id: str | None = None
    data: CitationPayload


class CitationContextChunk(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    chunk_id: uuid.UUID = Field(alias="chunkId")
    chunk_index: int = Field(alias="chunkIndex")
    role: Literal["previous", "anchor", "next"]
    text: str
    page: str | None = None
    section: str | None = None


class CitationContextTable(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    table_index: int = Field(alias="tableIndex")
    title: str | None = None
    units: str | None = None
    markdown: str
    table_data: dict[str, Any] = Field(alias="tableData")


class CitationContextResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    anchor_chunk_id: uuid.UUID = Field(alias="anchorChunkId")
    document_id: uuid.UUID = Field(alias="documentId")
    ticker: str
    company_name: str | None = Field(default=None, alias="companyName")
    form: str
    filing_date: date = Field(alias="filingDate")
    source_url: str = Field(alias="sourceUrl")
    document_title: str | None = Field(default=None, alias="documentTitle")
    fiscal_year: int | None = Field(default=None, alias="fiscalYear")
    chunks: list[CitationContextChunk]
    table: CitationContextTable | None = None


class StatusPayload(BaseModel):
    stage: str
    message: str


class StatusPart(BaseModel):
    type: Literal["data-status"] = "data-status"
    data: StatusPayload


MessagePart = Annotated[
    TextPart | CitationPart | StatusPart,
    Field(discriminator="type"),
]


class UIMessage(BaseModel):
    id: str | None = None
    role: Literal["user", "assistant", "system"]
    parts: list[MessagePart] = Field(default_factory=list, max_length=64)


class CreateThreadRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ThreadResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: uuid.UUID
    title: str = Field(max_length=255)
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class ThreadListResponse(BaseModel):
    threads: list[ThreadResponse]


class MessageHistoryResponse(BaseModel):
    messages: list[UIMessage]


class StreamRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    thread_id: uuid.UUID = Field(validation_alias="threadId")
    messages: list[UIMessage] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def latest_user_message_has_text(self) -> Self:
        latest_user_message = next(
            (message for message in reversed(self.messages) if message.role == "user"),
            None,
        )
        if latest_user_message is None or not any(
            isinstance(part, TextPart) and part.text.strip()
            for part in latest_user_message.parts
        ):
            raise ValueError("The latest user message must contain non-empty text.")
        return self


def thread_row_to_response(row: dict[str, Any]) -> ThreadResponse:
    return ThreadResponse(
        id=uuid.UUID(str(row["id"])),
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
