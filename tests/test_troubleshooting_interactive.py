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

    @patch("github_issue_analysis.ai.interactive.Prompt.ask")
    def test_single_line_input(self, mock_ask):
        """Test normal single-line input without backslash continuation."""
        mock_ask.return_value = "What is the error?"
        result = get_multiline_input()
        assert result == "What is the error?"
        assert mock_ask.call_count == 1

        # Verify it was called with the correct prompt
        mock_ask.assert_called_with(">>> ", default="")

    @patch("github_issue_analysis.ai.interactive.Prompt.ask")
    def test_multiline_with_backslash(self, mock_ask):
        """Test backslash continuation for multi-line input."""
        mock_ask.side_effect = ["First line\\", "Second line\\", "Third line"]
        result = get_multiline_input()
        assert result == "First line\nSecond line\nThird line"
        assert mock_ask.call_count == 3

        # Verify prompts change for continuation lines
        expected_calls = [
            (">>> ", ""),  # First call args
            ("    ", ""),  # Continuation prompt
            ("    ", ""),  # Continuation prompt
        ]
        actual_calls = [
            (call.args[0], call.kwargs.get("default", ""))
            for call in mock_ask.call_args_list
        ]
        assert actual_calls == expected_calls

    @patch("github_issue_analysis.ai.interactive.Prompt.ask")
    def test_empty_line_handling(self, mock_ask):
        """Test handling of empty lines in multi-line input."""
        mock_ask.side_effect = [
            "First line\\",
            "\\",  # Empty continuation line with backslash to continue
            "Last line",
        ]
        result = get_multiline_input()
        assert result == "First line\n\nLast line"
        assert mock_ask.call_count == 3

    @patch("github_issue_analysis.ai.interactive.Prompt.ask")
    def test_backslash_removal(self, mock_ask):
        """Test that backslashes are properly removed from continuation lines."""
        mock_ask.side_effect = ["Line with backslash\\", "Final line"]
        result = get_multiline_input()
        # Should remove the backslash from the first line
        assert result == "Line with backslash\nFinal line"
        assert "\\" not in result

    @patch("github_issue_analysis.ai.interactive.Prompt.ask")
    def test_empty_line_ends_input(self, mock_ask):
        """Test that empty lines without backslash end the input."""
        mock_ask.side_effect = [
            "First line\\",
            "",  # Empty line without backslash - ends input
        ]
        result = get_multiline_input()
        # Should only capture first line, empty line ends the input
        assert result == "First line\n"
        assert mock_ask.call_count == 2


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
        mock_result_obj.output = "Recovery response"
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
        mock_console.print.assert_any_call("\nRecovery response\n")

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
        first_result.output = "First response"
        first_result.new_messages = lambda: ["msg1", "msg2"]

        second_result = SimpleNamespace()
        second_result.output = "Second response"
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
    """Integration tests with real components where possible."""

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY for real agent testing",
    )
    @patch("github_issue_analysis.ai.interactive.get_multiline_input")
    @patch("github_issue_analysis.ai.interactive.console")
    @pytest.mark.asyncio
    async def test_full_interactive_flow(self, mock_console, mock_input):
        """Test complete flow with real PydanticAI agent (requires API keys).

        This integration test uses a real PydanticAI agent to verify the
        interactive session works with actual agent responses.
        """
        mock_input.side_effect = [
            "What's the root cause of this issue?",
            "Can you provide more details?",
            "exit",
        ]

        try:
            # Use a simple test agent with OpenAI
            agent = Agent(
                "openai:gpt-4o-mini",
                output_type=str,
                system_prompt="You are a helpful technical troubleshooting assistant. "
                "Provide concise, helpful responses about GitHub issues.",
            )

            # Simulate initial analysis
            initial_result = await agent.run(
                "Analyze this test issue: Database connection timeouts in production"
            )

            # Run interactive session
            await run_interactive_session(
                agent,
                initial_result,
                {
                    "issue": {
                        "title": "Database connection timeout",
                        "number": 123,
                        "body": "Production database is timing out",
                    }
                },
                include_images=False,
            )

            # Verify session completed without errors
            # The session should have processed 2 questions before exit
            assert mock_input.call_count == 3  # 2 questions + exit

        except Exception as e:
            # Skip test if API is unavailable or has issues
            pytest.skip(f"API unavailable or failing: {e}")

        # Verify output was displayed (responses from real agent)
        print_calls = [
            call
            for call in mock_console.print.call_args_list
            if call[0] and isinstance(call[0][0], str) and call[0][0].startswith("\n")
        ]
        # Should have at least 2 response prints (one for each question)
        assert len(print_calls) >= 2

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
            "• Use '\\' at line end for multi-line input",
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
        mock_result_obj.output = "This is the agent response"
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

        # Verify response is formatted with surrounding newlines
        mock_console.print.assert_any_call("\nThis is the agent response\n")
