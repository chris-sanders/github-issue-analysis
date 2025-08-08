"""Functional tests for interactive troubleshoot mode.

These tests focus on real behavior with minimal mocking as specified in the task design.
Only mock external services (API calls) where absolutely necessary.
"""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai import Agent

from github_issue_analysis.ai.interactive import (
    get_multiline_input,
    run_interactive_session,
)


class TestMultilineInput:
    """Test multi-line input handling."""

    @patch("builtins.input")
    def test_single_line_input(self, mock_input):
        """Test normal single-line input without backslash continuation."""
        mock_input.return_value = "What is the error?"
        result = get_multiline_input()
        assert result == "What is the error?"
        assert mock_input.call_count == 1

        # Verify it was called with the correct prompt
        mock_input.assert_called_with("Enter your question: ")

    @patch("builtins.input")
    def test_multiline_with_backslash(self, mock_input):
        """Test backslash continuation for multi-line input."""
        mock_input.side_effect = ["First line\\", "Second line\\", "Third line"]
        result = get_multiline_input()
        assert result == "First line\nSecond line\nThird line"
        assert mock_input.call_count == 3

        # Verify prompts change for continuation lines
        expected_calls = [
            "Enter your question: ",  # First call
            "Continue: ",  # Continuation prompt
            "Continue: ",  # Continuation prompt
        ]
        actual_calls = [call.args[0] for call in mock_input.call_args_list]
        assert actual_calls == expected_calls

    @patch("builtins.input")
    def test_empty_line_handling(self, mock_input):
        """Test handling of empty lines in multi-line input."""
        mock_input.side_effect = [
            "First line\\",
            "\\",  # Empty continuation line with backslash to continue
            "Last line",
        ]
        result = get_multiline_input()
        assert result == "First line\n\nLast line"
        assert mock_input.call_count == 3

    @patch("builtins.input")
    def test_backslash_removal(self, mock_input):
        """Test that backslashes are properly removed from continuation lines."""
        mock_input.side_effect = ["Line with backslash\\", "Final line"]
        result = get_multiline_input()
        # Should remove the backslash from the first line
        assert result == "Line with backslash\nFinal line"
        assert "\\" not in result

    @patch("builtins.input")
    def test_empty_line_ends_input(self, mock_input):
        """Test that empty lines without backslash end the input."""
        mock_input.side_effect = [
            "First line\\",
            "",  # Empty line without backslash - ends input
        ]
        result = get_multiline_input()
        # Should only capture first line, empty line ends the input
        assert result == "First line\n"
        assert mock_input.call_count == 2


class TestInteractiveSession:
    """Test interactive session flow."""

    @patch("github_issue_analysis.ai.interactive.get_multiline_input")
    @patch("github_issue_analysis.ai.interactive.console")
    @pytest.mark.asyncio
    async def test_exit_command(self, mock_console, mock_input):
        """Test that 'exit' command properly ends the session."""
        mock_input.side_effect = ["What's the root cause?", "exit"]

        # Create minimal mock agent that tracks calls
        mock_agent = AsyncMock()
        mock_result_obj = SimpleNamespace()
        mock_result_obj.output = "Here's the troubleshooting analysis"
        mock_result_obj.new_messages = lambda: ["message1", "message2"]

        mock_agent.run.return_value = mock_result_obj

        # Mock initial result
        mock_initial_result = AsyncMock()
        mock_initial_result.new_messages = lambda: ["initial_message"]

        await run_interactive_session(
            mock_agent,
            mock_initial_result,
            {"issue": {"title": "Test Issue", "number": 123}},
            include_images=False,
        )

        # Verify one question was processed before exit
        assert mock_agent.run.call_count == 1

        # Verify agent was called with the question and message history
        call_args = mock_agent.run.call_args
        assert call_args[0][0] == "What's the root cause?"  # First positional arg
        assert "message_history" in call_args[1]  # Should be in kwargs

        # Verify session end message was printed
        mock_console.print.assert_any_call("Session ended. Thank you!")

    @patch("github_issue_analysis.ai.interactive.get_multiline_input")
    @patch("github_issue_analysis.ai.interactive.console")
    @pytest.mark.asyncio
    async def test_keyboard_interrupt(self, mock_console, mock_input):
        """Test Ctrl+C handling gracefully exits the session."""
        mock_input.side_effect = KeyboardInterrupt()

        mock_agent = AsyncMock()
        mock_initial_result = AsyncMock()
        mock_initial_result.new_messages = lambda: []

        # Should exit gracefully without errors
        await run_interactive_session(
            mock_agent,
            mock_initial_result,
            {"issue": {"title": "Test Issue"}},
            include_images=False,
        )

        # No agent calls should have been made
        assert mock_agent.run.call_count == 0

        # Verify graceful exit message was printed
        mock_console.print.assert_any_call("\nSession ended. Thank you!")

    @patch("github_issue_analysis.ai.interactive.get_multiline_input")
    @patch("github_issue_analysis.ai.interactive.console")
    @pytest.mark.asyncio
    async def test_empty_input_handling(self, mock_console, mock_input):
        """Test that empty inputs are skipped and session continues."""
        mock_input.side_effect = [
            "",  # Empty input - should be skipped
            "   ",  # Whitespace only - should be skipped
            "What's wrong?",  # Valid input
            "exit",
        ]

        mock_agent = AsyncMock()
        mock_result_obj = SimpleNamespace()
        mock_result_obj.output = "Analysis response"
        mock_result_obj.new_messages = lambda: []
        mock_agent.run.return_value = mock_result_obj

        mock_initial_result = AsyncMock()
        mock_initial_result.new_messages = lambda: []

        await run_interactive_session(
            mock_agent,
            mock_initial_result,
            {"issue": {"title": "Test Issue"}},
            include_images=False,
        )

        # Only one valid question should have been processed
        assert mock_agent.run.call_count == 1
        call_args = mock_agent.run.call_args
        assert call_args[0][0] == "What's wrong?"

    @patch("github_issue_analysis.ai.interactive.get_multiline_input")
    @patch("github_issue_analysis.ai.interactive.console")
    @pytest.mark.asyncio
    async def test_error_handling_continues_session(self, mock_console, mock_input):
        """Test that errors during agent calls don't crash the session."""
        mock_input.side_effect = [
            "First question",  # Will cause error
            "Second question",  # Should still work
            "exit",
        ]

        mock_agent = AsyncMock()
        # First call raises exception, second succeeds
        mock_result_obj = SimpleNamespace()
        mock_result_obj.output = SimpleNamespace(
            answer="Recovery response", additional_findings=[], references_used=[]
        )
        mock_result_obj.new_messages = lambda: []

        mock_agent.run.side_effect = [Exception("API timeout"), mock_result_obj]

        mock_initial_result = AsyncMock()
        mock_initial_result.new_messages = lambda: []

        await run_interactive_session(
            mock_agent,
            mock_initial_result,
            {"issue": {"title": "Test Issue"}},
            include_images=False,
        )

        # Both questions should have been attempted
        assert mock_agent.run.call_count == 2

        # Error message should be displayed
        mock_console.print.assert_any_call("[red]Error: API timeout[/red]")
        mock_console.print.assert_any_call(
            "[yellow]You can continue asking questions or type 'exit' to end.[/yellow]"
        )

        # Session should continue and process second question
        # The response is printed as a Markdown object - check for successful response
        calls = mock_console.print.call_args_list
        markdown_calls = [call for call in calls if "Markdown" in str(call)]
        assert len(markdown_calls) > 0, (
            "Expected at least one Markdown object to be printed after recovery"
        )

    @patch("github_issue_analysis.ai.interactive.get_multiline_input")
    @patch("github_issue_analysis.ai.interactive.console")
    @pytest.mark.asyncio
    async def test_message_history_continuity(self, mock_console, mock_input):
        """Test that message history is properly maintained across questions."""
        mock_input.side_effect = ["First question", "Follow-up question", "exit"]

        # Mock agent that returns different message histories
        mock_agent = AsyncMock()

        # Create mock results with evolving message histories
        first_result = SimpleNamespace()
        first_result.output = SimpleNamespace(
            answer="First response", additional_findings=[], references_used=[]
        )
        first_result.new_messages = lambda: ["msg1", "msg2"]

        second_result = SimpleNamespace()
        second_result.output = SimpleNamespace(
            answer="Second response", additional_findings=[], references_used=[]
        )
        second_result.new_messages = lambda: ["msg1", "msg2", "msg3", "msg4"]

        mock_agent.run.side_effect = [first_result, second_result]

        # Mock initial result
        mock_initial_result = SimpleNamespace()
        mock_initial_result.new_messages = lambda: ["initial"]

        await run_interactive_session(
            mock_agent,
            mock_initial_result,
            {"issue": {"title": "Test Issue"}},
            include_images=False,
        )

        # Verify both questions were processed
        assert mock_agent.run.call_count == 2

        # Verify message history continuity
        first_call = mock_agent.run.call_args_list[0]
        second_call = mock_agent.run.call_args_list[1]

        # First call should use initial message history
        assert first_call[1]["message_history"] == ["initial"]

        # Second call should use updated message history from first result
        assert second_call[1]["message_history"] == ["msg1", "msg2"]

    @patch("github_issue_analysis.ai.interactive.get_multiline_input")
    @patch("github_issue_analysis.ai.interactive.console")
    @pytest.mark.asyncio
    async def test_case_insensitive_exit(self, mock_console, mock_input):
        """Test that exit command is case-insensitive."""
        test_cases = ["EXIT", "Exit", "eXiT"]

        for exit_command in test_cases:
            mock_input.side_effect = [exit_command]
            mock_console.reset_mock()

            mock_agent = AsyncMock()
            mock_initial_result = AsyncMock()
            mock_initial_result.new_messages = lambda: []

            await run_interactive_session(
                mock_agent,
                mock_initial_result,
                {"issue": {"title": "Test Issue"}},
                include_images=False,
            )

            # No agent calls should be made
            assert mock_agent.run.call_count == 0
            # Exit message should be displayed
            mock_console.print.assert_any_call("Session ended. Thank you!")


class TestInteractiveIntegration:
    """Integration tests with mocked components."""

    @patch("github_issue_analysis.ai.interactive.get_multiline_input")
    @patch("github_issue_analysis.ai.interactive.console")
    @pytest.mark.asyncio
    async def test_session_header_display(self, mock_console, mock_input):
        """Test that interactive session displays proper header and instructions."""
        mock_input.side_effect = ["exit"]

        mock_agent = AsyncMock()
        mock_initial_result = AsyncMock()
        mock_initial_result.new_messages = lambda: []

        await run_interactive_session(
            mock_agent,
            mock_initial_result,
            {"issue": {"title": "Test Issue"}},
            include_images=False,
        )

        # Verify header and instructions were displayed
        expected_prints = [
            "\n[bold blue]── Interactive Mode ─────────────────────────[/bold blue]",
            "Ask follow-up questions about this issue.",
            "• Type 'exit' or press Ctrl+C to end",
            "• For multi-line input: End lines with '\\' to continue",
        ]

        for expected_print in expected_prints:
            mock_console.print.assert_any_call(expected_print)

    @patch("github_issue_analysis.ai.interactive.get_multiline_input")
    @patch("github_issue_analysis.ai.interactive.console")
    @pytest.mark.asyncio
    async def test_output_formatting(self, mock_console, mock_input):
        """Test that agent responses are properly formatted with newlines."""
        mock_input.side_effect = ["Test question", "exit"]

        mock_agent = AsyncMock()
        mock_result_obj = SimpleNamespace()
        mock_result_obj.output = SimpleNamespace(
            answer="This is the agent response",
            additional_findings=[],
            references_used=[],
        )
        mock_result_obj.new_messages = lambda: []
        mock_agent.run.return_value = mock_result_obj

        mock_initial_result = AsyncMock()
        mock_initial_result.new_messages = lambda: []

        await run_interactive_session(
            mock_agent,
            mock_initial_result,
            {"issue": {"title": "Test Issue"}},
            include_images=False,
        )

        # Verify response header is displayed and Markdown object was printed
        mock_console.print.assert_any_call("\n[bold green]Response:[/bold green]")

        # Check that a Markdown object was printed (contains the actual response)
        calls = mock_console.print.call_args_list
        markdown_calls = [call for call in calls if "Markdown" in str(call)]
        assert len(markdown_calls) > 0, (
            "Expected a Markdown object to be printed with the response"
        )
