"""Interactive session functionality for troubleshooting analysis."""

from typing import Any

from pydantic_ai import Agent
from rich.console import Console
from rich.prompt import Prompt

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
    console.print("• Use '\\' at line end for multi-line input")
    console.print("[bold blue]" + "─" * 55 + "[/bold blue]\n")

    message_history = initial_result.new_messages()

    while True:
        try:
            # Get user input with multi-line support
            user_input = get_multiline_input()

            if user_input.lower() == "exit":
                console.print("Session ended. Thank you!")
                break

            if not user_input.strip():
                continue

            # Run with context
            result = await agent.run(user_input, message_history=message_history)

            # Display response
            console.print(f"\n{result.output}\n")

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
    """Get input with backslash continuation support.

    Returns:
        The complete multi-line input string
    """
    lines = []
    prompt = ">>> "

    while True:
        line = Prompt.ask(prompt, default="")

        if line.endswith("\\"):
            lines.append(line[:-1])  # Remove backslash
            prompt = "    "  # Indent continuation
        else:
            lines.append(line)
            break

    return "\n".join(lines)
