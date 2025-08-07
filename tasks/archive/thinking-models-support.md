# Task: AI Thinking Models Support with Smart CLI Validation

**Status:** planning

**Description:**
Implement comprehensive support for AI thinking models (OpenAI o1, Anthropic Claude with thinking, Google Gemini thinking) with intelligent CLI validation that provides helpful error messages and guidance when users specify incompatible model/option combinations.

**Acceptance Criteria:**
- [ ] CLI supports `--thinking-effort {low,medium,high}` for OpenAI o1 models
- [ ] CLI supports `--thinking-budget <tokens>` for Anthropic/Google thinking models  
- [ ] Smart validation with helpful error messages for invalid model/option combinations
- [ ] Environment variable support (`AI_THINKING_EFFORT`, `AI_THINKING_BUDGET`)
- [ ] Enhanced AI configuration system supporting thinking parameters
- [ ] Processor automatically maps generic thinking config to provider-specific settings
- [ ] Backward compatibility - existing configurations work unchanged
- [ ] Model capability mapping system for validation
- [ ] Tests for all thinking model configurations
- [ ] Tests for validation error scenarios
- [ ] Code quality checks pass

**Technical Implementation:**

**1. CLI Enhancement (`cli/process.py`):**
```python
@click.option('--thinking-effort', 
              type=click.Choice(['low', 'medium', 'high']),
              help='Reasoning effort level for OpenAI o1 models')
@click.option('--thinking-budget', 
              type=int,
              help='Thinking token budget for Anthropic/Google models')
def process_cmd(thinking_effort, thinking_budget, model, ...):
    # Validate thinking options against model capabilities
    validate_thinking_configuration(model, thinking_effort, thinking_budget)
```

**2. Model Capability System (`ai/capabilities.py`):**
```python
THINKING_CAPABILITIES = {
    'openai:o1-mini': ['thinking_effort', 'thinking_summary'],
    'openai:o1-preview': ['thinking_effort', 'thinking_summary'],
    'openai:gpt-4o-mini': ['thinking_effort'],  # Limited thinking support
    'anthropic:claude-3-5-sonnet-latest': ['thinking_budget'],
    'anthropic:claude-3-7-sonnet-latest': ['thinking_budget'],
    'google:gemini-2.0-flash': ['thinking_budget'],
    'groq:qwen-qwq-32b': ['thinking_format'],
}

def validate_thinking_configuration(model: str, effort: str, budget: int) -> None:
    """Smart validation with helpful error messages."""
```

**3. Enhanced Configuration (`ai/config.py`):**
```python
class ThinkingConfig(BaseModel):
    effort: Optional[Literal['low', 'medium', 'high']] = None
    budget_tokens: Optional[int] = None
    summary: Optional[Literal['brief', 'detailed']] = None

class AIModelConfig(BaseModel):
    model_name: str
    thinking: Optional[ThinkingConfig] = None
    temperature: Optional[float] = None
```

**4. Smart Error Messages:**
```
❌ Error: Model 'openai:gpt-4o' does not support --thinking-effort

💡 For thinking support, try these models:
   OpenAI o1 models: o1-mini, o1-preview
   Available options: --thinking-effort {low,medium,high}

   Anthropic models: claude-3-5-sonnet-latest  
   Available options: --thinking-budget <tokens>

   Google models: gemini-2.0-flash
   Available options: --thinking-budget <tokens>
```

**5. Processor Updates (`ai/processors.py`):**
```python
def _build_model_settings(self) -> Any:
    """Map generic thinking config to provider-specific settings."""
    if not self.config.thinking:
        return None
        
    if 'openai' in self.model_name:
        return OpenAIResponsesModelSettings(
            openai_reasoning_effort=self.config.thinking.effort,
            openai_reasoning_summary=self.config.thinking.summary or 'brief'
        )
    elif 'anthropic' in self.model_name:
        return AnthropicModelSettings(
            anthropic_thinking={
                'type': 'enabled',
                'budget_tokens': self.config.thinking.budget_tokens
            }
        )
    elif 'google' in self.model_name:
        return GoogleModelSettings(
            google_thinking_config={
                'thinking_budget': self.config.thinking.budget_tokens
            }
        )
```

**Environment Variables:**
```bash
AI_THINKING_EFFORT=high
AI_THINKING_BUDGET=2048  
AI_THINKING_SUMMARY=detailed
```

**Agent Notes:**
- PydanticAI has excellent built-in thinking support across all major providers
- Current codebase only uses basic string model configuration - needs enhancement
- Key design principle: thinking options presence implicitly enables thinking mode
- Smart validation should guide users toward correct model/option combinations
- Must maintain backward compatibility with existing AI_MODEL environment variable

**Validation:**
```bash
# Test thinking model configurations
uv run gh-analysis process product-labeling \
  --model openai:o1-mini --thinking-effort high \
  --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number USER_PROVIDED_ISSUE_NUMBER

uv run gh-analysis process product-labeling \
  --model anthropic:claude-3-5-sonnet-latest --thinking-budget 2048 \
  --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number USER_PROVIDED_ISSUE_NUMBER

# Test validation errors
uv run gh-analysis process product-labeling \
  --model openai:gpt-4o --thinking-effort high
# Should show helpful error with model suggestions

# Test environment variables
export AI_THINKING_EFFORT=medium
uv run gh-analysis process product-labeling \
  --model openai:o1-mini \
  --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number USER_PROVIDED_ISSUE_NUMBER

# Test backward compatibility
uv run gh-analysis process product-labeling \
  --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number USER_PROVIDED_ISSUE_NUMBER
# Should work exactly as before

# Run all tests
uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest
```

**Files to Create/Modify:**
- `github_issue_analysis/ai/capabilities.py` (new)
- `github_issue_analysis/ai/config.py` (new) 
- `github_issue_analysis/ai/processors.py` (modify)
- `github_issue_analysis/cli/process.py` (modify)
- `tests/test_ai/test_thinking_models.py` (new)
- `tests/test_cli/test_thinking_validation.py` (new)