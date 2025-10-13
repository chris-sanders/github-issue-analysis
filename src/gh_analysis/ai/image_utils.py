"""Image processing utilities for AI analysis."""

import mimetypes
from pathlib import Path
from typing import Any


def load_downloaded_images(
    issue_data: dict[str, Any], include_images: bool = True
) -> list[dict[str, Any]]:
    """Load pre-downloaded images from data/attachments directory.

    Args:
        issue_data: Issue data dictionary containing attachment information
        include_images: Whether to include images in processing

    Returns:
        List of image content dictionaries formatted for AI models
    """
    if not include_images:
        return []

    image_contents = []
    issue = issue_data["issue"]

    for attachment in issue.get("attachments", []):
        # Only process downloaded image attachments
        if not attachment.get("downloaded") or not attachment.get("local_path"):
            continue

        local_path = Path(attachment["local_path"])
        if not local_path.exists():
            continue

        # Check if it's an image file
        content_type = (
            attachment.get("content_type") or mimetypes.guess_type(str(local_path))[0]
        )
        if not content_type or not content_type.startswith("image/"):
            continue

        try:
            # Read the downloaded image
            img_bytes = local_path.read_bytes()
            img_size_mb = len(img_bytes) / (1024 * 1024)

            # Check if image is too large (most models have 5MB limits)
            if img_size_mb > 5:
                print(
                    f"WARNING: Image {local_path.name} is {img_size_mb:.2f}MB, "
                    "may be too large for some models"
                )

            image_contents.append(
                {
                    "type": "binary_content",
                    "data": img_bytes,
                    "media_type": content_type,
                    "metadata": {
                        "source": attachment[
                            "source"
                        ],  # "issue_body" or "comment_{id}"
                        "filename": attachment["filename"],
                        "original_url": attachment["original_url"],
                    },
                }
            )
        except Exception as e:
            print(f"Failed to load image {local_path}: {e}")
            continue

    return image_contents


def describe_image_context(attachment_source: str, issue_data: dict[str, Any]) -> str:
    """Get contextual description of where an image appears in the issue.

    Args:
        attachment_source: Source identifier like "issue_body" or "comment_0"
        issue_data: Issue data dictionary

    Returns:
        Human-readable description of the image's context
    """
    if attachment_source == "issue_body":
        return "Image from issue description"

    if attachment_source.startswith("comment_"):
        try:
            comment_id = attachment_source.split("_")[1]
            comment_idx = int(comment_id)
            comments = issue_data["issue"].get("comments", [])
            if comment_idx < len(comments):
                comment = comments[comment_idx]
                user = comment["user"]["login"]
                return f"Image from comment by {user}"
        except (ValueError, IndexError, KeyError):
            pass

    return f"Image from {attachment_source}"
