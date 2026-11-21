"""PydanticAI document agent definition."""

from __future__ import annotations

import time
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.usage import UsageLimits
from google import genai

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer
from app.assistant.status import emit_agent_done, emit_agent_start
from app.config import settings
from app.core.companies import COMPANY_REGISTRY
from app.llm import run_with_gemini_fallback
from app.retrieval.types import RetrievedPassage

_INSTRUCTIONS_PATH = Path(__file__).with_name("instructions.md")
INSTRUCTIONS = _INSTRUCTIONS_PATH.read_text(encoding="utf-8")


def get_document_agent(
    client: genai.Client | None = None,
    *,
    model_name: str | None = None,
) -> Agent[DocumentAgentDeps, GroundedAnswer]:
    provider = (
        GoogleProvider(client=client)
        if client is not None
        else GoogleProvider(api_key=settings.google_api_key)
    )
    model = GoogleModel(model_name or settings.gemini_model, provider=provider)
    return Agent(
        model,
        deps_type=DocumentAgentDeps,
        output_type=GroundedAnswer,
        instructions=INSTRUCTIONS,
    )


def format_passages_for_synthesis(passages: list[RetrievedPassage]) -> str:
    if not passages:
        return "No relevant filing passages were retrieved."

    formatted: list[str] = []
    for index, passage in enumerate(passages, start=1):
        fiscal_period = (
            f"FY{passage.fiscal_year}"
            if passage.fiscal_year is not None
            else f"report date {passage.filing_date.isoformat()}"
        )
        metadata = [
            f"company={passage.company_name or COMPANY_REGISTRY.get(passage.ticker).display_name}",
            f"document={passage.document_title or passage.form}",
            f"filing={passage.form}",
            f"period={fiscal_period}",
            f"page={passage.page or 'not available'}",
            f"section={passage.section or 'not available'}",
            f"chunk_id={passage.chunk_id}",
        ]
        excerpt = passage.text.strip()
        formatted.append(f"[{index}] {' | '.join(metadata)}\n{excerpt}")
    return "\n\n".join(formatted)


async def run_document_agent(
    query: str,
    deps: DocumentAgentDeps,
) -> GroundedAnswer:
    passages = deps.retrieved_passages
    if passages is None:
        started = time.perf_counter()
        passages = await deps.retriever.search(
            query,
            top_k=settings.retrieval_top_k,
            include_neighbors=False,
        )
        deps.retrieval_ms += (time.perf_counter() - started) * 1000
        deps.registry.register_many(passages)

    user_prompt = f"Research question:\n{query}\n\n"
    if deps.conversation_context:
        user_prompt += (
            f"Recent conversation for follow-up continuity:\n"
            f"{deps.conversation_context}\n\n"
        )
    user_prompt += (
        f"Retrieved filing passages:\n{format_passages_for_synthesis(passages)}"
    )
    emit_agent_start(
        deps,
        model=settings.gemini_model,
        request_limit=8,
    )

    async def run_with_model(model_name: str):
        return await get_document_agent(
            deps.google_client,
            model_name=model_name,
        ).run(
            user_prompt,
            deps=deps,
            usage_limits=UsageLimits(request_limit=8),
        )

    _, result = await run_with_gemini_fallback(
        settings.gemini_model,
        settings.gemini_fallback_models,
        run_with_model,
        operation="generation",
    )
    usage = result.usage
    emit_agent_done(
        deps,
        requests=usage.requests or 0,
        tool_calls=usage.tool_calls or 0,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )
    return result.output
