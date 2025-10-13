"""OpenAI Batch API provider for cost-effective AI processing."""

import base64
import json
import os
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console

from ..prompts import PRODUCT_LABELING_PROMPT
from .config_compat import AIModelConfig, build_provider_specific_settings

console = Console()


class OpenAIBatchProvider:
    """OpenAI Batch API implementation for cost-effective processing."""

    def __init__(self, config: AIModelConfig):
        """Initialize OpenAI batch provider.

        Args:
            config: AI model configuration
        """
        self.config = config
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        # Validate model supports batch processing
        model_name = config.model_name.split(":", 1)[-1].lower()
        unsupported_models = ["o1-mini", "o1-preview", "o3-mini"]
        if any(unsupported in model_name for unsupported in unsupported_models):
            raise ValueError(
                f"Model '{config.model_name}' does not support OpenAI Batch API. "
                f"Use gpt-4o, gpt-4o-mini, gpt-3.5-turbo, or o4-mini for batch "
                f"processing."
            )

        self.base_url = "https://api.openai.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def create_jsonl_file(
        self, issues: list[dict[str, Any]], processor_type: str, output_path: Path
    ) -> Path:
        """Convert issues to OpenAI JSONL format with custom_id for tracking.

        Args:
            issues: List of issue data dictionaries
            processor_type: Type of processor (e.g., 'product-labeling')
            output_path: Path where to save the JSONL file

        Returns:
            Path to the created JSONL file
        """
        if processor_type != "product-labeling":
            raise ValueError(f"Unsupported processor type: {processor_type}")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build system prompt
        system_prompt = PRODUCT_LABELING_PROMPT

        # Get model settings for OpenAI
        model_settings = build_provider_specific_settings(self.config)

        # Extract just the model name without provider prefix
        model_name = self.config.model_name.split(":", 1)[-1]

        with open(output_path, "w", encoding="utf-8") as f:
            for issue_data in issues:
                issue = issue_data["issue"]

                # Create custom_id for tracking
                custom_id = (
                    f"{issue_data['org']}_{issue_data['repo']}_issue_{issue['number']}"
                )

                # Format the issue prompt using the same logic as the regular processor
                user_prompt = self._format_issue_prompt(issue_data)

                # Build messages with image support
                messages = [{"role": "system", "content": system_prompt}]

                # Handle images if enabled and present
                if self.config.include_images and issue.get("attachments"):
                    user_message: dict[str, Any] = {
                        "role": "user",
                        "content": [{"type": "text", "text": user_prompt}],
                    }

                    # Add images to the message
                    for attachment in issue["attachments"]:
                        # Skip attachments that failed to download
                        if not attachment.get("local_path"):
                            continue

                        # Load image file and convert to base64
                        image_path = Path(attachment["local_path"])
                        if image_path.exists():
                            with open(image_path, "rb") as img_file:
                                img_data = base64.b64encode(img_file.read()).decode(
                                    "utf-8"
                                )
                                content_type = attachment["content_type"]
                                data_url = f"data:{content_type};base64,{img_data}"
                                user_message["content"].append(
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": data_url},
                                    }
                                )
                    messages.append(user_message)
                else:
                    # Text-only message
                    messages.append({"role": "user", "content": user_prompt})

                # Build the request body
                request_body = {
                    "model": model_name,
                    "messages": messages,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "product_labeling_response",
                            "strict": True,
                            "schema": self._get_response_schema(),
                        },
                    },
                }

                # Add model-specific settings (temperature, reasoning, etc.)
                request_body.update(model_settings)

                # Create JSONL entry
                jsonl_entry = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": request_body,
                }

                f.write(json.dumps(jsonl_entry, separators=(",", ":")) + "\n")

        console.print(f"Created JSONL file with {len(issues)} requests: {output_path}")
        return output_path

    def _format_issue_prompt(self, issue_data: dict[str, Any]) -> str:
        """Format issue data for analysis prompt.

        Same logic as ProductLabelingProcessor.
        """
        issue = issue_data["issue"]

        # Include all comments with full content
        comment_text = ""
        if issue.get("comments"):
            all_comments = issue["comments"]
            comment_entries = []
            for comment in all_comments:
                user = comment["user"]["login"]
                body = comment["body"].replace("\n", " ").strip()
                comment_entries.append(f"{user}: {body}")
            comment_text = " | ".join(comment_entries)

        # Handle image processing based on configuration
        image_instruction = ""
        if self.config.include_images:
            # Check if issue has attachments/images
            attachments = issue.get("attachments", [])
            if attachments:
                image_instruction = f"""

**IMAGES PROVIDED:** This issue contains {len(attachments)} image(s) to analyze.
Analyze any relevant images and include your findings in the image_impact field.
"""
            else:
                image_instruction = """

**NO IMAGES PROVIDED:** This issue contains no images to analyze.
IMPORTANT: Leave images_analyzed as an empty array and image_impact as an empty
string since no images were provided.
"""
        else:
            image_instruction = """

**NO IMAGES PROVIDED:** Image analysis is disabled for this batch.
IMPORTANT: Leave images_analyzed as an empty array and image_impact as an empty
string since image processing is disabled.
"""

        return f"""
Analyze this GitHub issue for product labeling:

**Title:** {issue["title"]}

**Body:** {issue["body"]}

**Current Labels:** {
            json.dumps(
                [
                    label["name"]
                    for label in issue["labels"]
                    if label["name"].startswith("product::")
                ],
                separators=(",", ":"),
            )
        }

**Repository:** {issue_data["org"]}/{issue_data["repo"]}

**Comments:** {comment_text or "No comments"}
{image_instruction}

Recommend the most appropriate product label(s) based on the issue content.
"""

    def _get_response_schema(self) -> dict[str, Any]:
        """Get JSON schema for ProductLabelingResponse."""
        return {
            "type": "object",
            "properties": {
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Overall confidence in analysis",
                },
                "recommended_labels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {
                                "type": "string",
                                "enum": [
                                    "product::kots",
                                    "product::troubleshoot",
                                    "product::kurl",
                                    "product::embedded-cluster",
                                    "product::sdk",
                                    "product::docs",
                                    "product::vendor",
                                    "product::downloadportal",
                                    "product::compatibility-matrix",
                                ],
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                                "description": "Confidence score 0-1",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Explanation for this recommendation",
                            },
                        },
                        "required": ["label", "confidence", "reasoning"],
                        "additionalProperties": False,
                    },
                    "description": "Suggested product labels",
                },
                "current_labels_assessment": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "correct": {
                                "type": "boolean",
                                "description": (
                                    "Whether this label is correctly applied"
                                ),
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Explanation of the assessment",
                            },
                        },
                        "required": ["label", "correct", "reasoning"],
                        "additionalProperties": False,
                    },
                    "description": "Assessment of existing labels",
                },
                "summary": {
                    "type": "string",
                    "description": (
                        "Brief summary of the issue's product classification"
                    ),
                },
                "reasoning": {
                    "type": "string",
                    "description": "Detailed reasoning for label recommendations",
                },
                "images_analyzed": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string"},
                            "source": {"type": "string"},
                            "description": {"type": "string"},
                            "relevance_score": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                            },
                        },
                        "required": [
                            "filename",
                            "source",
                            "description",
                            "relevance_score",
                        ],
                        "additionalProperties": False,
                    },
                    "description": (
                        "Analysis of images found in issue. "
                        "MUST be empty if no images were provided."
                    ),
                },
                "image_impact": {
                    "type": "string",
                    "description": (
                        "How images influenced the classification decision. "
                        "MUST be empty if no images were provided."
                    ),
                },
            },
            "required": [
                "confidence",
                "recommended_labels",
                "current_labels_assessment",
                "summary",
                "reasoning",
                "images_analyzed",
                "image_impact",
            ],
            "additionalProperties": False,
        }

    async def upload_file(self, file_path: Path) -> str:
        """Upload JSONL file to OpenAI for batch processing.

        Args:
            file_path: Path to the JSONL file

        Returns:
            OpenAI file ID
        """
        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/jsonl")}
                data = {"purpose": "batch"}

                response = await client.post(
                    f"{self.base_url}/files",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files=files,
                    data=data,
                    timeout=60.0,
                )

                if response.status_code != 200:
                    raise Exception(
                        f"File upload failed: {response.status_code} {response.text}"
                    )

                result = response.json()
                console.print(f"Uploaded file: {result['id']}")
                return str(result["id"])

    async def submit_batch(self, input_file_id: str) -> str:
        """Submit batch job to OpenAI.

        Args:
            input_file_id: OpenAI file ID for the input JSONL

        Returns:
            OpenAI batch ID
        """
        async with httpx.AsyncClient() as client:
            data = {
                "input_file_id": input_file_id,
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
            }

            response = await client.post(
                f"{self.base_url}/batches",
                headers=self.headers,
                json=data,
                timeout=30.0,
            )

            if response.status_code != 200:
                raise Exception(
                    f"Batch submission failed: {response.status_code} {response.text}"
                )

            result = response.json()
            console.print(f"Submitted batch: {result['id']}")
            return str(result["id"])

    async def get_batch_status(self, batch_id: str) -> dict[str, Any]:
        """Get batch job status from OpenAI.

        Args:
            batch_id: OpenAI batch ID

        Returns:
            Batch status information
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/batches/{batch_id}",
                headers=self.headers,
                timeout=30.0,
            )

            if response.status_code != 200:
                raise Exception(
                    f"Status check failed: {response.status_code} {response.text}"
                )

            return dict(response.json())

    async def download_results(self, output_file_id: str, output_path: Path) -> Path:
        """Download completed batch results.

        Args:
            output_file_id: OpenAI output file ID
            output_path: Local path to save the results

        Returns:
            Path to the downloaded results file
        """
        async with httpx.AsyncClient() as client:
            # First get the file content URL
            response = await client.get(
                f"{self.base_url}/files/{output_file_id}/content",
                headers=self.headers,
                timeout=60.0,
            )

            if response.status_code != 200:
                raise Exception(
                    f"Results download failed: {response.status_code} {response.text}"
                )

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save the results
            with open(output_path, "wb") as f:
                f.write(response.content)

            console.print(f"Downloaded results: {output_path}")
            return output_path

    async def cancel_batch(self, batch_id: str) -> dict[str, Any]:
        """Cancel a batch job via OpenAI API.

        Args:
            batch_id: OpenAI batch ID to cancel

        Returns:
            Updated batch status information

        Raises:
            Exception: If cancellation fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/batches/{batch_id}/cancel",
                headers=self.headers,
                timeout=30.0,
            )

            if response.status_code != 200:
                raise Exception(
                    f"Batch cancellation failed: {response.status_code} {response.text}"
                )

            result = response.json()
            console.print(f"Cancelled batch: {result['id']}")
            return dict(result)

    def parse_batch_results(self, results_file: Path) -> list[dict[str, Any]]:
        """Parse batch results JSONL file.

        Args:
            results_file: Path to the results JSONL file

        Returns:
            List of parsed results
        """
        results = []

        with open(results_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        result = json.loads(line)
                        results.append(result)
                    except json.JSONDecodeError as e:
                        console.print(
                            f"[yellow]Warning: Failed to parse line: {e}[/yellow]"
                        )
                        continue

        return results
