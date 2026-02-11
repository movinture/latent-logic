import logging
from typing import Any

import openai

from strands.types.exceptions import ContextWindowOverflowException, ModelThrottledException

logger = logging.getLogger(__name__)

_CONTEXT_OVERFLOW_MESSAGES = [
    "Input is too long for requested model",
    "input length and `max_tokens` exceed context limit",
    "too many total text bytes",
]


def normalize_openai_exception(exc: Exception) -> Exception:
    """Normalize OpenAI-compatible exceptions into Strands exceptions."""
    if isinstance(exc, openai.BadRequestError):
        # Some providers throw a BadRequest for context overflow
        if hasattr(exc, "code") and exc.code == "context_length_exceeded":
            logger.warning("context window overflow detected")
            return ContextWindowOverflowException(str(exc))
        return exc

    if isinstance(exc, openai.RateLimitError):
        logger.warning("rate limit detected")
        return ModelThrottledException(str(exc))

    if isinstance(exc, openai.APIError):
        message = str(exc)
        if any(m in message for m in _CONTEXT_OVERFLOW_MESSAGES):
            logger.warning("context window overflow detected")
            return ContextWindowOverflowException(message)
        return exc

    return exc


def raise_if_normalized(exc: Exception) -> None:
    normalized = normalize_openai_exception(exc)
    if normalized is exc:
        raise exc
    raise normalized
