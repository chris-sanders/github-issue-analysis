"""Patch for PydanticAI to fix Union instantiation error with OpenAI 1.99.2+.

This patch fixes the issue where ChatCompletionMessageToolCallParam became a Union
type alias in OpenAI 1.99.2+, which cannot be instantiated directly.
"""

from typing import Any

from openai.types import chat
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models import openai as openai_model


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
    """Apply the patch to fix Union instantiation error."""
    # Replace the problematic method with our patched version
    setattr(
        openai_model.OpenAIModel, "_map_tool_call", staticmethod(patched_map_tool_call)
    )
