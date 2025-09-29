"""Base summary runner for case processing."""

import json
from typing import Any, Dict

import openai
from pydantic import BaseModel


class SummaryResult(BaseModel):
    """Structure for case summary."""
    product: list[str]
    symptoms: list[str]
    evidence: list[str]
    cause: str
    fix: list[str]
    confidence: float


class BaseSummaryRunner:
    """Basic summary runner using OpenAI."""

    def __init__(self, model_name: str = "gpt-4-turbo"):
        self.model_name = model_name
        self.client = openai.OpenAI()

    async def analyze(self, issue_data: dict) -> dict:
        """Generate summary for an issue."""

        # Format issue for prompt
        issue_text = self._format_issue(issue_data)

        # Generate summary
        prompt = """Analyze this support case and provide a structured summary with:
        1. Product areas affected (list)
        2. Symptoms reported (list)
        3. Evidence/errors found (list)
        4. Root cause (if identified)
        5. Fix or resolution (list)
        6. Confidence score (0-1)

        Respond in JSON format matching this structure:
        {
            "product": ["area1", "area2"],
            "symptoms": ["symptom1", "symptom2"],
            "evidence": ["error1", "log entry"],
            "cause": "root cause description",
            "fix": ["step1", "step2"],
            "confidence": 0.85
        }"""

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a technical support case analyzer."},
                {"role": "user", "content": f"{prompt}\n\nCase:\n{issue_text}"}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # Validate and return
        validated = SummaryResult(
            product=result.get("product", ["unknown"]),
            symptoms=result.get("symptoms", []),
            evidence=result.get("evidence", []),
            cause=result.get("cause", ""),
            fix=result.get("fix", []),
            confidence=float(result.get("confidence", 0.5))
        )

        return validated.model_dump()

    def _format_issue(self, issue_data: dict) -> str:
        """Format issue data into readable text."""
        lines = [
            f"Issue #{issue_data['number']}: {issue_data['title']}",
            f"State: {issue_data['state']}",
            f"Labels: {', '.join(label['name'] for label in issue_data.get('labels', []))}",
            "",
            "Description:",
            issue_data.get('body', 'No description'),
            "",
            f"Comments ({len(issue_data.get('comments', []))}):"
        ]

        for comment in issue_data.get('comments', [])[:50]:  # Limit to 50 comments
            user = comment.get('user', {}).get('login', 'unknown')
            body = comment.get('body', '')
            lines.append(f"\n@{user}:\n{body}")

        return "\n".join(lines)