"""Retry and model fallback for transient Gemini overloads."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

from google.genai import errors
from pydantic_ai.exceptions import ModelHTTPError

logger = logging.getLogger(__name__)

_T = TypeVar("_T")
_RETRY_DELAY_MIN_SECONDS = 0.8
_RETRY_DELAY_MAX_SECONDS = 1.2
_TRANSIENT_STATUS_CODES = {429, 503}


class GeminiFallbackExhausted(RuntimeError):
    def __init__(self, *, status_code: int, models: Sequence[str]) -> None:
        self.status_code = status_code
        self.models = tuple(models)
        super().__init__(
            f"Gemini models exhausted after transient HTTP {status_code} errors"
        )


def _transient_status_code(error: ModelHTTPError | errors.APIError) -> int | None:
    status_code = error.status_code if isinstance(error, ModelHTTPError) else error.code
    return status_code if status_code in _TRANSIENT_STATUS_CODES else None


async def run_with_gemini_fallback(
    primary_model: str,
    fallback_models: Sequence[str],
    request: Callable[[str], Awaitable[_T]],
    *,
    operation: str,
) -> tuple[str, _T]:
    models = list(dict.fromkeys([primary_model, *fallback_models]))
    attempted: list[str] = []
    last_error: ModelHTTPError | errors.APIError | None = None
    last_status_code = 503

    for model_index, model in enumerate(models):
        attempted.append(model)
        for attempt in range(2):
            try:
                result = await request(model)
            except (ModelHTTPError, errors.APIError) as error:
                status_code = _transient_status_code(error)
                if status_code is None:
                    raise
                last_error = error
                last_status_code = status_code
                if attempt == 0:
                    logger.warning(
                        "Gemini %s model=%s returned HTTP %s; retrying once",
                        operation,
                        model,
                        status_code,
                    )
                    await asyncio.sleep(
                        random.uniform(
                            _RETRY_DELAY_MIN_SECONDS,
                            _RETRY_DELAY_MAX_SECONDS,
                        )
                    )
                    continue
                if model_index + 1 < len(models):
                    logger.warning(
                        "Gemini %s fallback model=%s after HTTP %s",
                        operation,
                        models[model_index + 1],
                        status_code,
                    )
                    break
                raise GeminiFallbackExhausted(
                    status_code=status_code,
                    models=attempted,
                ) from error
            else:
                logger.info("Gemini %s served by model=%s", operation, model)
                return model, result

    if last_error is None:
        raise RuntimeError("Gemini fallback chain contains no models")
    raise GeminiFallbackExhausted(
        status_code=last_status_code,
        models=attempted,
    ) from last_error
