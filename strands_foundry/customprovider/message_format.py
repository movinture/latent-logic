import json
import logging
import mimetypes
import base64
from typing import Any

from strands.types.content import ContentBlock, Messages, SystemContentBlock
from strands.types.tools import ToolChoice, ToolResult, ToolSpec, ToolUse

logger = logging.getLogger(__name__)


def _format_message_content(content: ContentBlock) -> dict[str, Any]:
    if "document" in content:
        mime_type = mimetypes.types_map.get(f".{content['document']['format']}", "application/octet-stream")
        file_data = base64.b64encode(content["document"]["source"]["bytes"]).decode("utf-8")
        return {
            "file": {
                "file_data": f"data:{mime_type};base64,{file_data}",
                "filename": content["document"]["name"],
            },
            "type": "file",
        }

    if "image" in content:
        mime_type = mimetypes.types_map.get(f".{content['image']['format']}", "application/octet-stream")
        image_data = base64.b64encode(content["image"]["source"]["bytes"]).decode("utf-8")
        return {
            "image_url": {
                "detail": "auto",
                "format": mime_type,
                "url": f"data:{mime_type};base64,{image_data}",
            },
            "type": "image_url",
        }

    if "text" in content:
        return {"text": content["text"], "type": "text"}

    raise TypeError(f"unsupported content type: {next(iter(content))}")


def _format_tool_call(tool_use: ToolUse) -> dict[str, Any]:
    return {
        "function": {
            "arguments": json.dumps(tool_use["input"]),
            "name": tool_use["name"],
        },
        "id": tool_use["toolUseId"],
        "type": "function",
    }


def _format_tool_message(tool_result: ToolResult) -> dict[str, Any]:
    contents = [
        {"text": json.dumps(content["json"]) } if "json" in content else content
        for content in tool_result["content"]
    ]

    return {
        "role": "tool",
        "tool_call_id": tool_result["toolUseId"],
        "content": [_format_message_content(content) for content in contents],
    }


def _format_system_messages(
    system_prompt: str | None,
    *,
    system_prompt_content: list[SystemContentBlock] | None = None,
) -> list[dict[str, Any]]:
    if system_prompt and system_prompt_content is None:
        system_prompt_content = [{"text": system_prompt}]

    return [
        {"role": "system", "content": content["text"]}
        for content in system_prompt_content or []
        if "text" in content
    ]


def format_request_messages(
    messages: Messages,
    system_prompt: str | None,
    *,
    system_prompt_content: list[SystemContentBlock] | None = None,
) -> list[dict[str, Any]]:
    formatted_messages = _format_system_messages(system_prompt, system_prompt_content=system_prompt_content)

    for message in messages:
        contents = message["content"]
        filtered = [c for c in contents if not any(k in c for k in ["toolResult", "toolUse", "reasoningContent"])]

        formatted_contents = [_format_message_content(c) for c in filtered]
        tool_calls = [_format_tool_call(c["toolUse"]) for c in contents if "toolUse" in c]
        tool_messages = [_format_tool_message(c["toolResult"]) for c in contents if "toolResult" in c]

        formatted_messages.append(
            {
                "role": message["role"],
                "content": formatted_contents,
                **({"tool_calls": tool_calls} if tool_calls else {}),
            }
        )

        formatted_messages.extend(tool_messages)

    return [m for m in formatted_messages if m.get("content") or "tool_calls" in m]


def format_tools(tool_specs: list[ToolSpec] | None) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool_spec["name"],
                "description": tool_spec["description"],
                "parameters": tool_spec["inputSchema"]["json"],
            },
        }
        for tool_spec in tool_specs or []
    ]


def format_tool_choice(tool_choice: ToolChoice | None) -> dict[str, Any]:
    if not tool_choice:
        return {}

    match tool_choice:
        case {"auto": _}:
            return {"tool_choice": "auto"}
        case {"any": _}:
            return {"tool_choice": "required"}
        case {"tool": {"name": tool_name}}:
            return {"tool_choice": {"type": "function", "function": {"name": tool_name}}}
        case _:
            return {"tool_choice": "auto"}
