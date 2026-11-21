"""Deterministic citation validation against the turn registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from app.assistant.deps import TurnRegistry
from app.assistant.outputs import Citation, GroundedAnswer

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")
_CITATION_REFERENCE_RE = re.compile(
    r"\[((?:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})|\d+)\]"
)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    error: str | None = None
    partial: bool = False


def _citation_markers(text: str) -> set[int]:
    return {int(match.group(1)) for match in _CITATION_MARKER_RE.finditer(text)}


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def map_uuid_markers_to_citations(
    answer: GroundedAnswer,
    registry: TurnRegistry,
) -> GroundedAnswer:
    citations_by_index: dict[int, Citation] = {}
    citations_by_chunk: dict[UUID, Citation] = {}
    for citation in answer.citations:
        citations_by_index.setdefault(citation.citation_index, citation)
        citations_by_chunk.setdefault(citation.chunk_id, citation)
    retrieved_passages = list(registry.passages_by_chunk_id.values())

    indexes_by_chunk: dict[UUID, int] = {}
    citations: list[Citation] = []

    def replace_reference(match: re.Match[str]) -> str:
        reference = match.group(1)
        if "-" in reference:
            chunk_id = UUID(reference)
            citation = citations_by_chunk.get(chunk_id)
        else:
            reference_index = int(reference)
            citation = citations_by_index.get(reference_index)
            chunk_id = (
                citation.chunk_id
                if citation is not None
                else (
                    retrieved_passages[reference_index - 1].chunk_id
                    if 1 <= reference_index <= len(retrieved_passages)
                    else None
                )
            )

        passage = (
            registry.passages_by_chunk_id.get(chunk_id)
            if chunk_id is not None
            else None
        )
        if passage is None and "-" not in reference:
            reference_index = int(reference)
            if 1 <= reference_index <= len(retrieved_passages):
                chunk_id = retrieved_passages[reference_index - 1].chunk_id
                passage = registry.passages_by_chunk_id[chunk_id]
                citation = None
        if passage is None:
            return ""
        if chunk_id is None:
            return ""

        if chunk_id not in indexes_by_chunk:
            citation_index = len(indexes_by_chunk) + 1
            indexes_by_chunk[chunk_id] = citation_index
            if citation is None:
                citation = Citation(
                    citation_index=citation_index,
                    chunk_id=chunk_id,
                    excerpt=passage.text.strip()[:800],
                )
            else:
                citation = citation.model_copy(
                    update={"citation_index": citation_index}
                )
            citations.append(citation)

        return f"[{indexes_by_chunk[chunk_id]}]"

    answer_text = _CITATION_REFERENCE_RE.sub(replace_reference, answer.answer)
    return answer.model_copy(update={"answer": answer_text, "citations": citations})


def prune_unreferenced_citations(answer: GroundedAnswer) -> GroundedAnswer:
    marker_indices = _citation_markers(answer.answer)
    if not marker_indices:
        return answer

    citations = [
        citation
        for citation in answer.citations
        if citation.citation_index in marker_indices
    ]
    if len(citations) == len(answer.citations):
        return answer

    return answer.model_copy(update={"citations": citations})


def retain_retrieved_citations(
    answer: GroundedAnswer,
    registry: TurnRegistry,
) -> GroundedAnswer:
    citations_by_index: dict[int, Citation] = {}
    for citation in answer.citations:
        passage = registry.passages_by_chunk_id.get(citation.chunk_id)
        if passage is None:
            continue
        excerpt = citation.excerpt
        normalized_excerpt = _normalize_whitespace(excerpt)
        if not normalized_excerpt or normalized_excerpt not in _normalize_whitespace(
            passage.text
        ):
            excerpt = passage.text.strip()[:800]
        citations_by_index.setdefault(
            citation.citation_index,
            citation.model_copy(update={"excerpt": excerpt}),
        )

    indexes: dict[int, int] = {}
    citations: list[Citation] = []

    def replace_marker(match: re.Match[str]) -> str:
        original_index = int(match.group(1))
        citation = citations_by_index.get(original_index)
        if citation is None:
            return ""
        if original_index not in indexes:
            new_index = len(indexes) + 1
            indexes[original_index] = new_index
            citations.append(
                citation.model_copy(update={"citation_index": new_index})
            )
        return f"[{indexes[original_index]}]"

    answer_text = _CITATION_MARKER_RE.sub(replace_marker, answer.answer)
    return answer.model_copy(
        update={
            "answer": answer_text,
            "citations": citations,
            "insufficient_evidence": False,
        }
    )


class GroundingValidator:
    async def validate(
        self,
        answer: GroundedAnswer,
        registry: TurnRegistry,
    ) -> ValidationResult:
        if not answer.answer.strip():
            return ValidationResult(ok=False, error="Answer text is empty.")

        if answer.insufficient_evidence:
            if answer.citations:
                return ValidationResult(
                    ok=False,
                    error="insufficient_evidence answers must not include citations.",
                )
            return ValidationResult(ok=True)

        if not answer.citations:
            return ValidationResult(
                ok=False,
                error="Grounded answers must include at least one citation.",
            )

        if not registry.passages_by_chunk_id:
            return ValidationResult(
                ok=False,
                error="Citations present but no passages were retrieved this turn.",
            )

        indices = [citation.citation_index for citation in answer.citations]
        if len(indices) != len(set(indices)):
            return ValidationResult(ok=False, error="Duplicate citation_index values.")

        if sorted(indices) != list(range(1, len(indices) + 1)):
            return ValidationResult(
                ok=False,
                error="citation_index values must be unique, 1-based, and contiguous.",
            )

        if _citation_markers(answer.answer) != set(indices):
            return ValidationResult(
                ok=False,
                error="Answer [n] markers must match citation_index values exactly.",
            )

        for citation in answer.citations:
            passage = registry.passages_by_chunk_id.get(citation.chunk_id)
            if passage is None:
                return ValidationResult(
                    ok=False,
                    error=f"Citation references chunk {citation.chunk_id} that was not retrieved.",
                )
            excerpt = _normalize_whitespace(citation.excerpt)
            if not excerpt or excerpt not in _normalize_whitespace(passage.text):
                return ValidationResult(
                    ok=False,
                    error=(
                        f"Citation [{citation.citation_index}] excerpt is not a "
                        "verbatim part of its retrieved passage."
                    ),
                )

        return ValidationResult(ok=True)
