import asyncio
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.assistant.outputs import Citation, GroundedAnswer
from app.auth.dependencies import CurrentUser
from app.chat.orchestrator import run_turn
from app.grounding.validator import ValidationResult
from app.retrieval.types import RetrievedPassage
from app.schemas.chat import TextPart, UIMessage


def _passage() -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=0,
        text="Azure revenue increased 29%.",
        page="5",
        section="MD&A",
        fusion_score=0.7,
        ticker="MSFT",
        company_name="Microsoft Corporation",
        form="10-K",
        filing_date=date(2024, 7, 30),
        fiscal_year=2024,
        accession_number="0000789019-24-000012",
    )


def _retriever(passages: list[RetrievedPassage]) -> MagicMock:
    retriever = MagicMock()
    retriever.search = AsyncMock(return_value=passages)
    return retriever


@pytest.mark.anyio
async def test_run_turn_streams_grounded_answer_and_persists() -> None:
    passage = _passage()
    grounded = GroundedAnswer(
        answer="Azure grew [1].",
        citations=[
            Citation(
                citation_index=1,
                chunk_id=passage.chunk_id,
                excerpt="Azure revenue increased 29%.",
            )
        ],
    )
    user_message = UIMessage(role="user", parts=[TextPart(text="Azure growth?")])
    events: list[str] = []

    async def fake_run(query: str, deps) -> GroundedAnswer:
        deps.emit_status("searching", "Searching SEC filings…")
        await asyncio.sleep(0.05)
        deps.registry.register(passage)
        return grounded

    fake_validator = MagicMock()
    fake_validator.validate = AsyncMock(return_value=ValidationResult(ok=True))

    with (
        patch("app.chat.orchestrator.run_document_agent", fake_run),
        patch("app.chat.orchestrator.GroundingValidator", return_value=fake_validator),
        patch(
            "app.chat.streaming.append_grounded_turn",
            AsyncMock(),
        ) as mock_persist,
    ):
        async for event in run_turn(
            client=MagicMock(),
            thread_id=uuid.uuid4(),
            user=CurrentUser(id=uuid.uuid4(), email="a@example.com"),
            user_message=user_message,
            thread_title="New chat",
            retriever=_retriever([passage]),
        ):
            events.append(event)

    assert events[0].startswith('data: {"type":"data-status"')
    assert any('"stage":"searching"' in event for event in events)
    assert any('"type":"text-delta"' in event for event in events)
    assert any('"type":"data-citation"' in event for event in events)
    assert not any('"type":"error"' in event for event in events)
    mock_persist.assert_awaited_once()
    persisted = mock_persist.await_args.kwargs["assistant_message"]
    part_types = {part.type for part in persisted.parts}
    assert "data-status" not in part_types


@pytest.mark.anyio
async def test_run_turn_abstains_when_no_passages_were_retrieved() -> None:
    grounded = GroundedAnswer(
        answer="Bad answer without markers.",
        citations=[
            Citation(
                citation_index=1,
                chunk_id=uuid.uuid4(),
                excerpt="missing from registry",
            )
        ],
    )
    user_message = UIMessage(role="user", parts=[TextPart(text="Question")])

    with (
        patch(
            "app.chat.orchestrator.run_document_agent",
            AsyncMock(return_value=grounded),
        ),
        patch("app.chat.streaming.append_grounded_turn", AsyncMock()) as mock_persist,
    ):
        events = [
            event
            async for event in run_turn(
                client=MagicMock(),
                thread_id=uuid.uuid4(),
                user=CurrentUser(id=uuid.uuid4(), email="a@example.com"),
                user_message=user_message,
                thread_title="New chat",
                retriever=_retriever([]),
            )
        ]

    assert not any('"type":"error"' in event for event in events)
    mock_persist.assert_awaited_once()
    persisted = mock_persist.await_args.kwargs["assistant_message"]
    assert persisted.parts[0].text.startswith("I couldn't retrieve")
    assert len(persisted.parts) == 1


@pytest.mark.anyio
async def test_run_turn_does_not_retry_when_no_passages_were_retrieved() -> None:
    invalid = GroundedAnswer(
        answer="Bad citation [1].",
        citations=[
            Citation(
                citation_index=1,
                chunk_id=uuid.uuid4(),
                excerpt="not registered",
            )
        ],
    )
    user_message = UIMessage(role="user", parts=[TextPart(text="Azure growth?")])
    attempts = 0

    async def fake_run(query: str, deps) -> GroundedAnswer:
        nonlocal attempts
        attempts += 1
        return invalid

    fake_validator = MagicMock()
    fake_validator.validate = AsyncMock(
        return_value=ValidationResult(
            ok=False,
            error="Citation references a chunk that was not retrieved.",
        )
    )

    with (
        patch("app.chat.orchestrator.run_document_agent", fake_run),
        patch("app.chat.orchestrator.GroundingValidator", return_value=fake_validator),
        patch("app.chat.streaming.append_grounded_turn", AsyncMock()) as mock_persist,
    ):
        events = [
            event
            async for event in run_turn(
                client=MagicMock(),
                thread_id=uuid.uuid4(),
                user=CurrentUser(id=uuid.uuid4(), email="a@example.com"),
                user_message=user_message,
                thread_title="New chat",
                retriever=_retriever([]),
            )
        ]

    assert attempts == 1
    assert fake_validator.validate.await_count == 1
    assert not any('"type":"error"' in event for event in events)
    assert not any('"stage":"retrying"' in event for event in events)
    mock_persist.assert_awaited_once()
    persisted = mock_persist.await_args.kwargs["assistant_message"]
    assert persisted.parts[0].text.startswith("I couldn't retrieve")
