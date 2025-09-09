"""
Gemini model patches for pydantic_ai compatibility.

Import this module to apply necessary patches for Gemini model issues:
- Fixes _auth initialization bug
- Handles MALFORMED_FUNCTION_CALL finish reason with proper retries

Usage:
    from .gemini_patches import apply_gemini_patches
    apply_gemini_patches()
"""


def apply_gemini_patches():
    """Apply all necessary Gemini model patches for pydantic_ai compatibility."""

    # Import everything here to avoid affecting module load order
    from typing import Annotated, Literal, NotRequired

    import pydantic
    import pydantic_ai.models.gemini as gemini_module
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    from pydantic_ai.models.gemini import GeminiModel, _GeminiCandidates

    # Patch 1: Fix _auth initialization bug
    original_init = GeminiModel.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._auth = None

    GeminiModel.__init__ = patched_init

    # Patch 2: Handle MALFORMED_FUNCTION_CALL finish reason
    # Create patched version with MALFORMED_FUNCTION_CALL added to finish_reason
    class _PatchedGeminiCandidates(_GeminiCandidates):
        finish_reason: NotRequired[
            Annotated[
                Literal["STOP", "MAX_TOKENS", "SAFETY", "MALFORMED_FUNCTION_CALL"],
                pydantic.Field(alias="finishReason"),
            ]
        ]

    # Replace the original with our patched version in the gemini module
    gemini_module._GeminiCandidates = _PatchedGeminiCandidates

    # Patch the _process_response method to handle MALFORMED_FUNCTION_CALL finish reason
    original_gemini_process_response = GeminiModel._process_response

    def patched_gemini_process_response(self, response):
        """Handle MALFORMED_FUNCTION_CALL finish reason by raising appropriate exception."""
        if len(response["candidates"]) >= 1:
            finish_reason = response["candidates"][0].get("finish_reason")
            if finish_reason == "MALFORMED_FUNCTION_CALL":
                # Raise a specific exception that can be caught and retried
                raise UnexpectedModelBehavior(
                    "Gemini returned MALFORMED_FUNCTION_CALL - tool call parameters may be invalid",
                    str(response),
                )

        # Continue with normal Gemini processing
        return original_gemini_process_response(self, response)

    GeminiModel._process_response = patched_gemini_process_response

    print("✅ Gemini model patches applied successfully")
