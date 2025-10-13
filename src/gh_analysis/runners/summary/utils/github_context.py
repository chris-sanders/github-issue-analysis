"""GitHub issue context formatting utilities."""


def build_github_context(issue) -> str:
    """Build context string from GitHub issue data.

    This is the exact context formatting logic from AgentSpec._build_context
    extracted for reuse across runners.
    """
    context = f"Title: {issue['title']}\nBody: {issue['body']}\n"
    if issue.get("comments"):
        context += "\nComments:\n"
        for comment in issue["comments"]:
            context += f"- {comment['body']}\n"
    return context
