"""GitHub issue context formatting utilities."""


def build_github_context(issue) -> str:
    """Build context string from GitHub issue data.

    This is the exact context formatting logic from AgentSpec._build_context
    extracted for reuse across runners.
    
    Args:
        issue: GitHub issue data (either Pydantic model or dict)
    """
    # Handle both Pydantic models and dictionaries
    if hasattr(issue, 'title'):
        # Pydantic model
        title = issue.title
        body = issue.body
        comments = issue.comments if issue.comments else []
    else:
        # Dictionary
        title = issue['title']
        body = issue['body']
        comments = issue.get('comments', [])
    
    context = f"Title: {title}\nBody: {body}\n"
    if comments:
        context += "\nComments:\n"
        for comment in comments:
            if hasattr(comment, 'body'):
                # Pydantic model
                context += f"- {comment.body}\n"
            else:
                # Dictionary
                context += f"- {comment['body']}\n"
    return context
