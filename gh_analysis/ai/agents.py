"""PydanticAI agents for GitHub issue analysis."""

from pydantic_ai import Agent

from .models import ProductLabelingResponse
from .prompts import PRODUCT_LABELING_PROMPT

# Product labeling agent - direct definition
product_labeling_agent = Agent(
    output_type=ProductLabelingResponse,
    instructions=PRODUCT_LABELING_PROMPT,
    retries=2,
)

# Future agents can be added here:
# issue_classification_agent = Agent(
#     output_type=IssueClassificationResponse,
#     instructions=ISSUE_CLASSIFICATION_PROMPT,
#     retries=2,
# )
