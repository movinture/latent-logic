import json
import logging
import os
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal, TypedDict, TypeVar, cast

import openai
from pydantic import BaseModel

from strands.models.model import Model
from strands.types.content import Messages, SystemContentBlock
from strands.types.exceptions import ContextWindowOverflowException
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolChoice, ToolSpec

from .errors import raise_if_normalized
from .message_format import format_request_messages, format_tools, format_tool_choice

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class FoundryConfig(TypedDict, total=False):
    model_id: str
    endpoint: str
    api_key: str
    params: dict[str, Any] | None
    tool_call_mode: Literal["openai", "deepseek_json", "auto"]


@dataclass
class _ToolCallCandidate:
    name: str
    arguments_json: str


class FoundryCompletionsModel(Model):
    """Custom Strands model provider for Azure Foundry OpenAI-compatible endpoints.

    This provider uses `chat.completions` and streams output into Strands StreamEvent
    chunks. It supports a DeepSeek JSON tool-call workaround by converting a final
    JSON tool request into a Strands toolUse block.
    """

    def __init__(self, **model_config: Any) -> None:
        self.config: FoundryConfig = {}
        self.update_config(**model_config)

        if not self.config.get("endpoint"):
            self.config["endpoint"] = os.getenv("FOUNDRY_ENDPOINT", "")
        if not self.config.get("api_key"):
            self.config["api_key"] = os.getenv("FOUNDRY_API_KEY", "")

        if not self.config.get("tool_call_mode"):
            self.config["tool_call_mode"] = "auto"

    def update_config(self, **model_config: Any) -> None:
        self.config.update(cast(FoundryConfig, model_config))

    def get_config(self) -> FoundryConfig:
        return cast(FoundryConfig, self.config)

    @asynccontextmanager
    async def _get_client(self) -> AsyncIterator[Any]:
        async with openai.AsyncOpenAI(
            api_key=self.config.get("api_key"),
            base_url=self.config.get("endpoint"),
        ) as client:
            yield client

    def _build_request(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None,
        system_prompt: str | None,
        *,
        tool_choice: ToolChoice | None = None,
        system_prompt_content: list[SystemContentBlock] | None = None,
    ) -> dict[str, Any]:
        return {
            "messages": format_request_messages(
                messages,
                system_prompt,
                system_prompt_content=system_prompt_content,
            ),
            "model": self.config["model_id"],
            "stream": True,
            "stream_options": {"include_usage": True},
            "tools": format_tools(tool_specs),
            **format_tool_choice(tool_choice),
            **cast(dict[str, Any], self.config.get("params", {}) or {}),
        }

    def _parse_deepseek_tool_call(self, content: str) -> _ToolCallCandidate | None:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        if "tool_name" in data and "tool_arguments" in data:
            return _ToolCallCandidate(name=data["tool_name"], arguments_json=json.dumps(data["tool_arguments"]))

        return None

    def _should_apply_deepseek_mode(self, finish_reason: str | None, final_text: str) -> bool:
        mode = self.config.get("tool_call_mode", "auto")
        if mode == "deepseek_json":
            return True
        if mode == "openai":
            return False
        # auto: only apply if the final content looks like a JSON tool call
        if finish_reason in ["tool_calls", "stop", "length", None]:
            return self._parse_deepseek_tool_call(final_text) is not None
        return False

    def _format_chunk(self, chunk_type: str, data: Any = None, data_type: str | None = None) -> StreamEvent:
        if chunk_type == "message_start":
            return {"messageStart": {"role": "assistant"}}

        if chunk_type == "content_start":
            if data_type == "tool":
                return {
                    "contentBlockStart": {
                        "start": {"toolUse": {"name": data["name"], "toolUseId": data["toolUseId"]}}
                    }
                }
            return {"contentBlockStart": {"start": {}}}

        if chunk_type == "content_delta":
            if data_type == "tool":
                return {"contentBlockDelta": {"delta": {"toolUse": {"input": data}}}}
            if data_type == "reasoning_content":
                return {"contentBlockDelta": {"delta": {"reasoningContent": {"text": data}}}}
            return {"contentBlockDelta": {"delta": {"text": data}}}

        if chunk_type == "content_stop":
            return {"contentBlockStop": {}}

        if chunk_type == "message_stop":
            return {"messageStop": {"stopReason": data}}

        if chunk_type == "metadata":
            return {
                "metadata": {
                    "usage": {
                        "inputTokens": data.prompt_tokens,
                        "outputTokens": data.completion_tokens,
                        "totalTokens": data.total_tokens,
                    },
                    "metrics": {"latencyMs": 0},
                }
            }

        raise RuntimeError(f"unknown chunk_type: {chunk_type}")

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: ToolChoice | None = None,
        system_prompt_content: list[SystemContentBlock] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamEvent, None]:
        request = self._build_request(
            messages,
            tool_specs,
            system_prompt,
            tool_choice=tool_choice,
            system_prompt_content=system_prompt_content,
        )

        yield self._format_chunk("message_start")

        async with self._get_client() as client:
            try:
                response = await client.chat.completions.create(**request)
            except Exception as e:
                raise_if_normalized(e)

            tool_calls: dict[int, list[Any]] = {}
            data_type: str | None = None
            finish_reason: str | None = None
            final_text = ""
            event = None

            async for event in response:
                if not getattr(event, "choices", None):
                    continue

                choice = event.choices[0]

                if hasattr(choice.delta, "reasoning_content") and choice.delta.reasoning_content:
                    if data_type != "reasoning_content":
                        if data_type is not None:
                            yield self._format_chunk("content_stop", data_type=data_type)
                        yield self._format_chunk("content_start", data_type="reasoning_content")
                    data_type = "reasoning_content"
                    yield self._format_chunk("content_delta", data=choice.delta.reasoning_content, data_type=data_type)

                if choice.delta.content:
                    if data_type != "text":
                        if data_type is not None:
                            yield self._format_chunk("content_stop", data_type=data_type)
                        yield self._format_chunk("content_start", data_type="text")
                    data_type = "text"
                    final_text += choice.delta.content
                    yield self._format_chunk("content_delta", data=choice.delta.content, data_type=data_type)

                for tool_call in choice.delta.tool_calls or []:
                    tool_calls.setdefault(tool_call.index, []).append(tool_call)

                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                    if data_type is not None:
                        yield self._format_chunk("content_stop", data_type=data_type)
                    break

            # Emit tool calls from standard OpenAI-compatible tool_calls
            for tool_deltas in tool_calls.values():
                tool_use_id = tool_deltas[0].id
                tool_name = tool_deltas[0].function.name
                yield self._format_chunk(
                    "content_start",
                    data_type="tool",
                    data={"name": tool_name, "toolUseId": tool_use_id},
                )

                for tool_delta in tool_deltas:
                    yield self._format_chunk(
                        "content_delta",
                        data_type="tool",
                        data=tool_delta.function.arguments or "",
                    )

                yield self._format_chunk("content_stop", data_type="tool")

            # DeepSeek JSON fallback
            if not tool_calls and final_text and self._should_apply_deepseek_mode(finish_reason, final_text):
                candidate = self._parse_deepseek_tool_call(final_text)
                if candidate:
                    tool_use_id = f"deepseek-{uuid.uuid4()}"
                    yield self._format_chunk(
                        "content_start",
                        data_type="tool",
                        data={"name": candidate.name, "toolUseId": tool_use_id},
                    )
                    yield self._format_chunk(
                        "content_delta",
                        data_type="tool",
                        data=candidate.arguments_json,
                    )
                    yield self._format_chunk("content_stop", data_type="tool")
                    yield self._format_chunk("message_stop", data="tool_use")
                else:
                    yield self._format_chunk("message_stop", data=finish_reason or "end_turn")
            else:
                # Map finish reasons to Strands stopReason
                if finish_reason == "tool_calls":
                    stop_reason = "tool_use"
                elif finish_reason == "length":
                    stop_reason = "max_tokens"
                else:
                    stop_reason = "end_turn"

                yield self._format_chunk("message_stop", data=stop_reason)

            # Drain response for usage
            async for event in response:
                _ = event

            if event and hasattr(event, "usage") and event.usage:
                yield self._format_chunk("metadata", data=event.usage)

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        # Minimal structured output implementation: use the OpenAI parse API if available.
        async with self._get_client() as client:
            try:
                response = await client.beta.chat.completions.parse(
                    model=self.config["model_id"],
                    messages=format_request_messages(prompt, system_prompt),
                    response_format=output_model,
                )
            except Exception as e:
                raise_if_normalized(e)

        parsed: T | None = None
        if len(response.choices) != 1:
            raise ValueError("Expected exactly one choice from model")

        for choice in response.choices:
            if isinstance(choice.message.parsed, output_model):
                parsed = choice.message.parsed
                break

        if parsed is None:
            raise ValueError("No valid structured output found in model response")

        yield {"output": parsed}
