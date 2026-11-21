"""FastAPI routes for chat threads and stubbed streaming."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from supabase import AsyncClient

from app.auth.dependencies import CurrentUser, get_current_user
from app.chat.messages import extract_last_user_message
from app.chat.orchestrator import run_turn
from app.database.chats import (
    create_thread,
    delete_thread,
    list_threads,
    load_messages,
    require_thread_access,
)
from app.database.documents import get_chunk_context
from app.database.models import DocumentChunk
from app.database.supabase import get_service_role_client, get_user_client
from app.database.users import ensure_user
from app.retrieval.retriever import DocumentRetriever
from app.schemas.chat import (
    CitationContextChunk,
    CitationContextResponse,
    CitationContextTable,
    CreateThreadRequest,
    MessageHistoryResponse,
    StreamRequest,
    ThreadListResponse,
    ThreadResponse,
)

router = APIRouter(prefix="/chat", tags=["chat"])


def _chunk_role(
    chunk: DocumentChunk,
    anchor: DocumentChunk,
) -> Literal["previous", "anchor", "next"]:
    if chunk.id == anchor.id:
        return "anchor"
    if chunk.chunk_index < anchor.chunk_index:
        return "previous"
    return "next"


def citation_context_response(
    chunks: list[DocumentChunk],
    *,
    anchor_chunk_id: uuid.UUID,
) -> CitationContextResponse:
    anchor = next(chunk for chunk in chunks if chunk.id == anchor_chunk_id)
    document = anchor.document
    return CitationContextResponse(
        anchor_chunk_id=anchor.id,
        document_id=anchor.document_id,
        ticker=document.ticker,
        company_name=document.company_name,
        form=document.form,
        filing_date=document.filing_date,
        source_url=document.source_url,
        document_title=document.primary_document,
        fiscal_year=document.fiscal_year,
        table=_table_context_from_chunk(anchor),
        chunks=[
            CitationContextChunk(
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                role=_chunk_role(chunk, anchor),
                text=chunk.text,
                page=chunk.page,
                section=chunk.section,
            )
            for chunk in chunks
        ],
    )


def _table_context_from_chunk(chunk: DocumentChunk) -> CitationContextTable | None:
    metadata = chunk.chunk_metadata or {}
    if metadata.get("chunk_kind") != "table_row":
        return None
    table_data = metadata.get("table")
    if not isinstance(table_data, dict):
        return None
    return CitationContextTable(
        table_index=table_data["table_index"],
        title=table_data.get("title"),
        units=table_data.get("units"),
        markdown=table_data["markdown"],
        table_data=table_data,
    )


async def load_citation_context(
    chunk_id: uuid.UUID,
    radius: int,
    session_factory: async_sessionmaker[AsyncSession],
) -> CitationContextResponse | None:
    async with session_factory() as session:
        async with session.begin():
            chunks = await get_chunk_context(session, chunk_id, radius)
            if chunks is None:
                return None
            return citation_context_response(chunks, anchor_chunk_id=chunk_id)


@router.get("/threads")
async def get_threads(
    user: CurrentUser = Depends(get_current_user),
    client: AsyncClient = Depends(get_user_client),
    service_client: AsyncClient = Depends(get_service_role_client),
) -> ThreadListResponse:
    await ensure_user(service_client, user)
    threads = await list_threads(client, user)
    return ThreadListResponse(threads=threads)


@router.post("/threads")
async def post_thread(
    body: CreateThreadRequest,
    user: CurrentUser = Depends(get_current_user),
    client: AsyncClient = Depends(get_user_client),
    service_client: AsyncClient = Depends(get_service_role_client),
) -> ThreadResponse:
    await ensure_user(service_client, user)
    return await create_thread(client, user, title=body.title)


@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(
    thread_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    client: AsyncClient = Depends(get_user_client),
    service_client: AsyncClient = Depends(get_service_role_client),
) -> MessageHistoryResponse:
    await require_thread_access(service_client, thread_id, user)
    messages = await load_messages(client, thread_id)
    return MessageHistoryResponse(messages=messages)


@router.get("/citations/{chunk_id}/context")
async def get_citation_context(
    request: Request,
    chunk_id: uuid.UUID,
    radius: int = Query(default=1, ge=0, le=3),
    _user: CurrentUser = Depends(get_current_user),
) -> CitationContextResponse:
    context = await load_citation_context(
        chunk_id,
        radius,
        request.app.state.async_session_factory,
    )
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation chunk not found",
        )
    return context


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread_route(
    thread_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    client: AsyncClient = Depends(get_user_client),
    service_client: AsyncClient = Depends(get_service_role_client),
) -> None:
    await require_thread_access(service_client, thread_id, user)
    await delete_thread(client, thread_id)


@router.post("/stream")
async def post_stream(
    body: StreamRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    client: AsyncClient = Depends(get_user_client),
    service_client: AsyncClient = Depends(get_service_role_client),
) -> StreamingResponse:
    await ensure_user(service_client, user)
    thread = await require_thread_access(service_client, body.thread_id, user)
    user_message = extract_last_user_message(body.messages)
    history = await load_messages(client, body.thread_id, limit=4)

    retriever = DocumentRetriever(
        session_factory=request.app.state.async_session_factory,
        google_client=request.app.state.gemini_client,
    )
    return StreamingResponse(
        run_turn(
            client=client,
            thread_id=body.thread_id,
            user=user,
            user_message=user_message,
            thread_title=thread.title,
            retriever=retriever,
            google_client=request.app.state.gemini_client,
            messages=[*history, user_message],
        ),
        media_type="text/event-stream",
    )
