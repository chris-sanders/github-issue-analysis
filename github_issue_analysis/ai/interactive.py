"""Interactive session functionality for troubleshooting analysis."""

from typing import Any

from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits
from rich.console import Console
from rich.markdown import Markdown

console = Console()


async def run_interactive_session(
    agent: Agent[None, Any],
    initial_result: Any,
    issue_data: dict[str, Any],
    include_images: bool = True,
) -> None:
    """Run interactive troubleshooting session after initial analysis.

    Args:
        agent: The PydanticAI agent to use for follow-up questions
        initial_result: The result from the initial analysis
        issue_data: The issue data dictionary
        include_images: Whether image analysis is enabled
    """
    # Display interactive mode header
    console.print(
        "\n[bold blue]── Interactive Mode ─────────────────────────[/bold blue]"
    )
    console.print("Ask follow-up questions about this issue.")
    console.print("• Type 'exit' or press Ctrl+C to end")
    console.print("• For multi-line input: End lines with '\\' to continue")
    console.print("[bold blue]" + "─" * 55 + "[/bold blue]\n")

    message_history = initial_result.new_messages()

    while True:
        try:
            # Get user input with multi-line support
            user_input = get_multiline_input()

            if user_input.lower() == "exit":
                console.print("Session ended. Thank you!")
                break

            # Skip empty input and continue asking
            if not user_input.strip():
                console.print(
                    "[dim]Please enter a question or type 'exit' to end.[/dim]"
                )
                continue

            # Show thinking indicator with spinner
            with console.status(
                "[dim]🤔 Analyzing your question...[/dim]", spinner="dots"
            ):
                # Run with context and proper usage limits
                result = await agent.run(
                    user_input,
                    message_history=message_history,
                    usage_limits=UsageLimits(request_limit=150),
                )

            # Display response with better formatting
            console.print("\n[bold green]Response:[/bold green]")

            # Format the response based on its type
            response_output = result.output

            # Check if it's a TroubleshootingResponse object and format it
            if hasattr(response_output, "analysis"):
                # Format the structured troubleshooting response
                analysis = response_output.analysis
                formatted_response = f"""## Root Cause
{analysis.root_cause}

## Key Findings
{chr(10).join(f"• {finding}" for finding in analysis.key_findings)}

## Remediation
{analysis.remediation}

## Technical Explanation
{analysis.explanation}

**Confidence:** {response_output.confidence_score:.2f}
**Processing Time:** {response_output.processing_time_seconds:.1f}s"""

                try:
                    markdown_content = Markdown(formatted_response)
                    console.print(markdown_content)
                except Exception:
                    console.print(formatted_response)
            else:
                # Handle other response types (like simple strings)
                try:
                    markdown_content = Markdown(str(response_output))
                    console.print(markdown_content)
                except Exception:
                    console.print(str(response_output))

            console.print("")  # Add blank line for readability

            # Update message history for next iteration
            message_history = result.new_messages()

        except KeyboardInterrupt:
            console.print("\nSession ended. Thank you!")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print(
                "[yellow]You can continue asking questions or type 'exit' to end."
                "[/yellow]"
            )


def get_multiline_input() -> str:
    r"""Get input with backslash continuation support.

    Usage:
    - For single line: Type and press Enter
    - For multi-line: End lines with \ to continue to next line

    Returns:
        The complete multi-line input string
    """
    lines: list[str] = []
    prompt_text = "Enter your question: "

    while True:
        if lines:  # Continuation line
            try:
                line = input("Continue: ").strip()
            except EOFError:
                break
        else:  # First line
            try:
                line = input(prompt_text).strip()
            except EOFError:
                break

        if line.endswith("\\"):
            lines.append(line[:-1])  # Remove backslash
        else:
            lines.append(line)
            break

    return "\n".join(lines)
