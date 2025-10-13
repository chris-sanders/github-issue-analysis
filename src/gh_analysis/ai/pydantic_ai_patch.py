"""Patches for PydanticAI compatibility issues.

1. Fix Union instantiation error with OpenAI 1.99.2+
2. Fix OpenAI Responses API tool call ID synchronization
"""

from typing import Any

from openai.types import chat
from pydantic_ai._utils import guard_tool_call_id as _guard_tool_call_id
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models import openai as openai_model
from pydantic_ai.models.openai import OpenAIResponsesModel


def patched_map_tool_call(t: ToolCallPart) -> Any:
    """Patched version of _map_tool_call that works with OpenAI 1.99.2+.

    The issue: In OpenAI 1.99.2+, ChatCompletionMessageToolCallParam is a
    Union type alias: Union[ChatCompletionMessageFunctionToolCallParam,
    ChatCompletionMessageCustomToolCallParam]

    You cannot instantiate a Union directly. Since PydanticAI always uses
    type='function', we should use ChatCompletionMessageFunctionToolCallParam
    directly.
    """
    # Use the specific function variant instead of the Union
    # Access _guard_tool_call_id through the module
    tool_call_id = getattr(
        openai_model, "_guard_tool_call_id", lambda t: t.tool_call_id
    )(t)
    return chat.ChatCompletionMessageFunctionToolCallParam(
        id=tool_call_id,
        type="function",
        function={"name": t.tool_name, "arguments": t.args_as_json_str()},
    )


def apply_pydantic_ai_patch() -> None:
    """Apply patches to fix PydanticAI compatibility issues."""
    # 1. Fix Union instantiation error
    setattr(
        openai_model.OpenAIModel, "_map_tool_call", staticmethod(patched_map_tool_call)
    )

    # 2. Fix OpenAI Responses API tool call ID synchronization
    # Based on context-experiments fix for tool call coordination
    original_process_response = OpenAIResponsesModel._process_response

    def patched_process_response(self: Any, response: Any) -> Any:
        """Patched version that applies guard_tool_call_id like Chat API."""
        result = original_process_response(self, response)

        # Apply guard_tool_call_id to all ToolCallPart items for consistency
        for item in result.parts:
            if isinstance(item, ToolCallPart):
                item.tool_call_id = _guard_tool_call_id(item)

        return result

    OpenAIResponsesModel._process_response = patched_process_response  # type: ignore[method-assign]
