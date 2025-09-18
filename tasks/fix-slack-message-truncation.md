# Task: Fix Slack Message Truncation Issue

**Status:** ready

**Description:**
Fix Slack notification truncation where AI analysis results are being cut off before the full content is posted. The issue occurs because individual Slack Block Kit section text fields have a 3,000 character limit, and long analysis fields like `root_cause` and `recommended_solution` can exceed this limit, causing message truncation or posting failures. **The solution must preserve ALL analysis content by intelligently splitting into multiple messages/blocks rather than truncating.**

**Root Cause Analysis:**
- Slack Block Kit section blocks have a hard limit of 3,000 characters per text field
- Current implementation at `/Users/chris/src/github-issue-analysis/gh_analysis/slack/client.py:298-336` directly inserts `root_cause` and `recommended_solution` without length validation
- AI analysis results can generate very long responses that exceed these limits
- The current code fails or truncates, losing valuable analysis content

**Acceptance Criteria:**
- [ ] **Zero content loss**: All analysis content must be posted to Slack, no matter how long
- [ ] Individual section blocks never exceed 3,000 character limit
- [ ] Long sections are split across multiple section blocks within the same message
- [ ] Very long analysis results are split across multiple sequential messages with clear continuation indicators ("1/3", "2/3", "3/3")
- [ ] All continuation messages post to the same thread for organization
- [ ] Solution handles all analysis result fields: `root_cause`, `recommended_solution`, `evidence`, `next_steps`
- [ ] Clear indicators show when content continues ("Root Cause (continued):", etc.)
- [ ] Implementation includes comprehensive testing with real-world long analysis results
- [ ] CLI command continues working without errors for long analysis results
- [ ] Message posting order is reliable and sequential

**Implementation Plan:**

### 1. Create Topic-Based Text Splitting Utilities
**Location**: `gh_analysis/slack/text_utils.py`
- `split_text_at_boundaries(text: str, max_length: int = 2900) -> List[str]`: Split text at sentence/paragraph boundaries, preserving formatting
- `create_continuation_header(title: str, is_continuation: bool) -> str`: Generate "Root Cause" or "Root Cause (continued)" headers
- `estimate_blocks_size(blocks: List[Dict]) -> int`: Calculate total character count for blocks

### 2. Implement Topic-Based Formatting Methods
**Location**: `gh_analysis/slack/client.py`

**Replace `_format_analysis_results` with topic-specific methods:**
- `_format_status_topic(results: Dict, agent_name: str) -> List[Dict]`: Status and agent info (always single block)
- `_format_evidence_topic(results: Dict) -> List[Dict]`: Evidence points (may split if >5 items or very long)
- `_format_root_cause_topic(results: Dict) -> List[Dict]`: Root cause analysis (splits if >2900 chars)
- `_format_solution_topic(results: Dict) -> List[Dict]`: Recommended solution (splits if >2900 chars)
- `_format_next_steps_topic(results: Dict) -> List[Dict]`: Next steps (splits if many steps)
- `_format_footer_topic() -> List[Dict]`: Timestamp footer (always single block)

**Each topic method handles its own splitting:**
```python
def _format_root_cause_topic(self, results: Dict) -> List[Dict[str, Any]]:
    root_cause = results.get("root_cause")
    if not root_cause:
        return []

    if len(root_cause) <= 2900:
        # Single block
        return [self._create_section_block("Root Cause", root_cause)]

    # Split into multiple blocks
    parts = split_text_at_boundaries(root_cause, 2900)
    blocks = []
    for i, part in enumerate(parts):
        title = create_continuation_header("Root Cause", i > 0)
        blocks.append(self._create_section_block(title, part))
    return blocks
```

### 3. Add Simple Topic-Based Message Strategy
**Location**: `gh_analysis/slack/client.py`

**Replace `notify_analysis_complete` logic:**
```python
def notify_analysis_complete(self, issue_url: str, issue_title: str, analysis_results: Dict, agent_name: str) -> bool:
    # Generate all topic blocks
    all_topics = [
        self._format_status_topic(analysis_results, agent_name),
        self._format_evidence_topic(analysis_results),
        self._format_root_cause_topic(analysis_results),
        self._format_solution_topic(analysis_results),
        self._format_next_steps_topic(analysis_results),
        self._format_footer_topic()
    ]

    # Filter out empty topics
    non_empty_topics = [topic for topic in all_topics if topic]
    total_blocks = sum(len(topic) for topic in non_empty_topics)

    if total_blocks <= 45:  # Leave margin for safety
        # Send as single message (current behavior preserved)
        all_blocks = [block for topic in non_empty_topics for block in topic]
        return self._post_single_message(all_blocks, issue_title)
    else:
        # Send each topic as separate message in thread
        return self._post_topic_sequence(non_empty_topics, issue_url, issue_title)
```

### 4. Add Topic Sequence Posting
**Location**: `gh_analysis/slack/client.py`

**Add method**: `_post_topic_sequence(topics: List[List[Dict]], issue_url: str, issue_title: str) -> bool`
- Post first topic as main message (gets thread_ts)
- Post remaining topics as thread replies
- Each message has a clear topic focus
- Handle posting failures gracefully (continue with remaining topics)
- Log which topics posted successfully

**Simple posting without complex sequencing:**
```python
def _post_topic_sequence(self, topics, issue_url, issue_title):
    thread_ts = None
    success_count = 0

    for i, topic_blocks in enumerate(topics):
        if i == 0:
            # First message includes issue info
            blocks = self._add_issue_header(topic_blocks, issue_url, issue_title)
            response = self.bot_client.chat_postMessage(channel=self.config.channel, blocks=blocks)
            thread_ts = response["ts"]
        else:
            # Subsequent messages as thread replies
            response = self.bot_client.chat_postMessage(
                channel=self.config.channel,
                thread_ts=thread_ts,
                blocks=topic_blocks
            )

        if response["ok"]:
            success_count += 1

    return success_count == len(topics)
```

### 5. Complete Implementation Details

**Text Utilities Module** (`gh_analysis/slack/text_utils.py`):
```python
from typing import List

def split_text_at_boundaries(text: str, max_length: int = 2900) -> List[str]:
    """Split text at sentence/paragraph boundaries while preserving formatting."""
    if len(text) <= max_length:
        return [text]

    parts = []
    current_part = ""

    # Split by paragraphs first, then sentences if needed
    paragraphs = text.split('\n\n')

    for paragraph in paragraphs:
        if len(current_part + paragraph) <= max_length:
            current_part += paragraph + '\n\n'
        else:
            if current_part:
                parts.append(current_part.rstrip())
                current_part = ""

            # If paragraph itself is too long, split by sentences
            if len(paragraph) > max_length:
                sentences = paragraph.split('. ')
                for i, sentence in enumerate(sentences):
                    sentence_with_period = sentence + ('. ' if i < len(sentences) - 1 else '')
                    if len(current_part + sentence_with_period) <= max_length:
                        current_part += sentence_with_period
                    else:
                        if current_part:
                            parts.append(current_part.rstrip())
                        current_part = sentence_with_period
            else:
                current_part = paragraph + '\n\n'

    if current_part:
        parts.append(current_part.rstrip())

    return parts

def create_continuation_header(title: str, is_continuation: bool) -> str:
    """Generate header with continuation indicator if needed."""
    return f"{title} (continued)" if is_continuation else title

def estimate_blocks_size(blocks: List[dict]) -> int:
    """Calculate approximate character count for blocks."""
    total = 0
    for block in blocks:
        if block.get('type') == 'section' and 'text' in block:
            total += len(block['text'].get('text', ''))
    return total
```

**Updated SlackClient Methods** (`gh_analysis/slack/client.py`):
```python
def _create_section_block(self, title: str, content: str) -> Dict[str, Any]:
    """Helper to create section block with consistent formatting."""
    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*{title}:*\n{content}",
        },
    }

def _format_status_topic(self, results: Dict, agent_name: str) -> List[Dict[str, Any]]:
    """Format status and agent info (always single block)."""
    status = results.get("status", "unknown")
    status_emoji = (
        "✅" if status == "resolved"
        else "📋" if status == "needs_data"
        else "❓"
    )

    return [{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"{status_emoji} *Analysis Complete* - Agent: `{agent_name}`",
        },
    }, {
        "type": "section",
        "fields": [{
            "type": "mrkdwn",
            "text": f"*Status:* {status.replace('_', ' ').title()}",
        }],
    }]

def _format_evidence_topic(self, results: Dict) -> List[Dict[str, Any]]:
    """Format evidence points (may split if very long)."""
    evidence = results.get("evidence", [])
    if not evidence:
        return []

    # Limit to 5 points initially
    limited_evidence = evidence[:5]
    evidence_text = "\n".join([f"• {point}" for point in limited_evidence])

    if len(evidence) > 5:
        evidence_text += f"\n• ... and {len(evidence) - 5} more points"

    # Check if text fits in single block
    if len(evidence_text) <= 2900:
        return [self._create_section_block("Key Evidence", evidence_text)]

    # Split evidence into multiple blocks if too long
    from .text_utils import split_text_at_boundaries, create_continuation_header
    parts = split_text_at_boundaries(evidence_text, 2900)
    blocks = []
    for i, part in enumerate(parts):
        title = create_continuation_header("Key Evidence", i > 0)
        blocks.append(self._create_section_block(title, part))
    return blocks

def _format_root_cause_topic(self, results: Dict) -> List[Dict[str, Any]]:
    """Format root cause analysis (splits if >2900 chars)."""
    root_cause = results.get("root_cause")
    status = results.get("status", "unknown")

    if not root_cause or status != "resolved":
        return []

    if len(root_cause) <= 2900:
        return [self._create_section_block("Root Cause", root_cause)]

    # Split into multiple blocks
    from .text_utils import split_text_at_boundaries, create_continuation_header
    parts = split_text_at_boundaries(root_cause, 2900)
    blocks = []
    for i, part in enumerate(parts):
        title = create_continuation_header("Root Cause", i > 0)
        blocks.append(self._create_section_block(title, part))
    return blocks

def _format_solution_topic(self, results: Dict) -> List[Dict[str, Any]]:
    """Format recommended solution (splits if >2900 chars)."""
    solution = results.get("recommended_solution")
    status = results.get("status", "unknown")

    if not solution or status != "resolved":
        return []

    if len(solution) <= 2900:
        return [self._create_section_block("Recommended Solution", solution)]

    # Split into multiple blocks
    from .text_utils import split_text_at_boundaries, create_continuation_header
    parts = split_text_at_boundaries(solution, 2900)
    blocks = []
    for i, part in enumerate(parts):
        title = create_continuation_header("Recommended Solution", i > 0)
        blocks.append(self._create_section_block(title, part))
    return blocks

def _format_next_steps_topic(self, results: Dict) -> List[Dict[str, Any]]:
    """Format next steps (splits if many steps)."""
    next_steps = results.get("next_steps", [])
    status = results.get("status", "unknown")

    if not next_steps or status != "needs_data":
        return []

    # Limit to 3 steps initially
    limited_steps = next_steps[:3]
    steps_text = "\n".join([f"• {step}" for step in limited_steps])

    if len(next_steps) > 3:
        steps_text += f"\n• ... and {len(next_steps) - 3} more steps"

    if len(steps_text) <= 2900:
        return [self._create_section_block("Next Steps", steps_text)]

    # Split steps if too long
    from .text_utils import split_text_at_boundaries, create_continuation_header
    parts = split_text_at_boundaries(steps_text, 2900)
    blocks = []
    for i, part in enumerate(parts):
        title = create_continuation_header("Next Steps", i > 0)
        blocks.append(self._create_section_block(title, part))
    return blocks

def _format_footer_topic(self) -> List[Dict[str, Any]]:
    """Format footer with timestamp (always single block)."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    return [{
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"Analysis completed at {timestamp}"}
        ],
    }]

def _add_issue_header(self, blocks: List[Dict], issue_url: str, issue_title: str) -> List[Dict]:
    """Add issue header to first message."""
    header_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*GitHub Issue Analysis Complete*\n<{issue_url}|{issue_title}>",
        },
    }
    return [header_block] + blocks

def _post_single_message(self, blocks: List[Dict], issue_title: str) -> bool:
    """Post all content as single message (backward compatibility)."""
    try:
        response = self.bot_client.chat_postMessage(
            channel=self.config.channel,
            blocks=blocks,
            text=f"GitHub Issue Analysis: {issue_title}",
        )
        return bool(response["ok"])
    except Exception as e:
        logger.error(f"Error posting single message: {e}")
        return False

def _post_topic_sequence(self, topics: List[List[Dict]], issue_url: str, issue_title: str) -> bool:
    """Post topics as separate messages in thread."""
    thread_ts = None
    success_count = 0
    total_topics = len(topics)

    logger.info(f"Posting {total_topics} topic messages for analysis")

    for i, topic_blocks in enumerate(topics):
        try:
            if i == 0:
                # First message includes issue header
                blocks_with_header = self._add_issue_header(topic_blocks, issue_url, issue_title)
                response = self.bot_client.chat_postMessage(
                    channel=self.config.channel,
                    blocks=blocks_with_header,
                    text=f"GitHub Issue Analysis: {issue_title}",
                )
                thread_ts = response["ts"]
            else:
                # Subsequent messages as thread replies
                response = self.bot_client.chat_postMessage(
                    channel=self.config.channel,
                    thread_ts=thread_ts,
                    blocks=topic_blocks,
                    text="Analysis continuation",
                )

            if response["ok"]:
                success_count += 1
                logger.info(f"Posted topic {i+1}/{total_topics} successfully")
            else:
                logger.error(f"Failed to post topic {i+1}/{total_topics}: {response}")

        except Exception as e:
            logger.error(f"Error posting topic {i+1}/{total_topics}: {e}")

    success = success_count == total_topics
    if success:
        logger.info(f"All {total_topics} topic messages posted successfully")
    else:
        logger.warning(f"Only {success_count}/{total_topics} topic messages posted successfully")

    return success

# Updated main notification method
def notify_analysis_complete(
    self,
    issue_url: str,
    issue_title: str,
    analysis_results: Dict[str, Any],
    agent_name: str,
) -> bool:
    """Send notification with topic-based splitting to avoid truncation."""
    if not self.config.is_configured():
        logger.warning("Slack is not configured, skipping notification")
        return False

    try:
        # Step 1: Search for existing thread
        thread_ts = self.search_for_issue(issue_url)

        # Step 2: Generate all topic blocks
        from .text_utils import estimate_blocks_size

        all_topics = [
            self._format_status_topic(analysis_results, agent_name),
            self._format_evidence_topic(analysis_results),
            self._format_root_cause_topic(analysis_results),
            self._format_solution_topic(analysis_results),
            self._format_next_steps_topic(analysis_results),
            self._format_footer_topic()
        ]

        # Filter out empty topics
        non_empty_topics = [topic for topic in all_topics if topic]
        total_blocks = sum(len(topic) for topic in non_empty_topics)

        logger.info(f"Generated {len(non_empty_topics)} topics with {total_blocks} total blocks")

        # Step 3: Decide posting strategy
        if total_blocks <= 45:  # Leave margin for Slack's 50 block limit
            # Send as single message (preserves backward compatibility)
            all_blocks = [block for topic in non_empty_topics for block in topic]

            if thread_ts:
                # Reply to existing thread
                return self.post_to_thread(thread_ts, {"blocks": all_blocks}, issue_url, agent_name)
            else:
                # New message
                return self._post_single_message(all_blocks, issue_title)
        else:
            # Send each topic as separate message in thread
            if thread_ts:
                # Post topics as replies to existing thread
                return self._post_topic_replies_to_thread(non_empty_topics, thread_ts)
            else:
                # Post topics as new thread
                return self._post_topic_sequence(non_empty_topics, issue_url, issue_title)

    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False

def _post_topic_replies_to_thread(self, topics: List[List[Dict]], thread_ts: str) -> bool:
    """Post topic messages as replies to existing thread."""
    success_count = 0
    total_topics = len(topics)

    for i, topic_blocks in enumerate(topics):
        try:
            response = self.bot_client.chat_postMessage(
                channel=self.config.channel,
                thread_ts=thread_ts,
                blocks=topic_blocks,
                text="Analysis results",
            )

            if response["ok"]:
                success_count += 1
                logger.info(f"Posted topic reply {i+1}/{total_topics} successfully")
            else:
                logger.error(f"Failed to post topic reply {i+1}/{total_topics}: {response}")

        except Exception as e:
            logger.error(f"Error posting topic reply {i+1}/{total_topics}: {e}")

    return success_count == total_topics
```

### 6. Comprehensive Testing Strategy

**Unit Tests** (`tests/test_slack_splitting.py`):
```python
import pytest
from unittest.mock import Mock, patch
from gh_analysis.slack.client import SlackClient
from gh_analysis.slack.config import SlackConfig
from gh_analysis.slack.text_utils import split_text_at_boundaries, create_continuation_header

class TestTextSplitting:
    def test_short_text_no_splitting(self):
        text = "Short content"
        result = split_text_at_boundaries(text, 2900)
        assert result == [text]
        assert len(result[0]) <= 2900

    def test_long_text_paragraph_splitting(self):
        # Create text with exactly 3000 chars to trigger splitting
        paragraph1 = "A" * 1400 + "."
        paragraph2 = "B" * 1400 + "."
        text = paragraph1 + "\n\n" + paragraph2

        result = split_text_at_boundaries(text, 2900)
        assert len(result) == 2
        assert len(result[0]) <= 2900
        assert len(result[1]) <= 2900
        assert paragraph1 in result[0]
        assert paragraph2 in result[1]

    def test_very_long_text_sentence_splitting(self):
        # Create very long paragraph that needs sentence splitting
        sentences = [f"This is sentence {i}." for i in range(100)]
        text = " ".join(sentences)

        result = split_text_at_boundaries(text, 2900)
        assert len(result) > 1
        for part in result:
            assert len(part) <= 2900

        # Verify all content preserved
        rejoined = " ".join(result).replace("  ", " ")
        assert rejoined.strip() == text.strip()

    def test_continuation_headers(self):
        assert create_continuation_header("Root Cause", False) == "Root Cause"
        assert create_continuation_header("Root Cause", True) == "Root Cause (continued)"

class TestTopicFormatting:
    def setup_method(self):
        self.client = SlackClient(SlackConfig())

    def test_status_topic_always_fits(self):
        results = {"status": "resolved"}
        blocks = self.client._format_status_topic(results, "test_agent")

        assert len(blocks) == 2  # Status message + status field
        assert "✅" in blocks[0]["text"]["text"]
        assert "test_agent" in blocks[0]["text"]["text"]

    def test_root_cause_topic_short_content(self):
        results = {"root_cause": "Simple root cause", "status": "resolved"}
        blocks = self.client._format_root_cause_topic(results)

        assert len(blocks) == 1
        assert "Simple root cause" in blocks[0]["text"]["text"]
        assert "*Root Cause:*" in blocks[0]["text"]["text"]

    def test_root_cause_topic_long_content_splitting(self):
        # Create root cause longer than 2900 chars
        long_cause = "A" * 3000
        results = {"root_cause": long_cause, "status": "resolved"}
        blocks = self.client._format_root_cause_topic(results)

        assert len(blocks) > 1
        assert "*Root Cause:*" in blocks[0]["text"]["text"]
        assert "*Root Cause (continued):*" in blocks[1]["text"]["text"]

        # Verify all content preserved
        all_text = "".join([block["text"]["text"] for block in blocks])
        assert long_cause in all_text

    def test_evidence_topic_with_many_points(self):
        evidence = [f"Evidence point {i}" for i in range(10)]
        results = {"evidence": evidence}
        blocks = self.client._format_evidence_topic(results)

        assert len(blocks) >= 1
        text_content = blocks[0]["text"]["text"]
        assert "Evidence point 0" in text_content
        assert "Evidence point 4" in text_content  # First 5 items
        assert "and 5 more points" in text_content  # Overflow indicator

    def test_empty_topics_filtered(self):
        results = {"status": "needs_data"}  # No root_cause or solution

        root_cause_blocks = self.client._format_root_cause_topic(results)
        solution_blocks = self.client._format_solution_topic(results)

        assert root_cause_blocks == []
        assert solution_blocks == []

class TestMessageStrategy:
    def setup_method(self):
        self.client = SlackClient(SlackConfig())

    @patch('gh_analysis.slack.client.SlackClient.bot_client')
    def test_single_message_for_small_content(self, mock_bot_client):
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Small analysis results that should fit in single message
        results = {
            "status": "resolved",
            "root_cause": "Simple cause",
            "recommended_solution": "Simple solution"
        }

        success = self.client.notify_analysis_complete(
            "https://github.com/test/test/issues/1",
            "Test Issue",
            results,
            "test_agent"
        )

        assert success
        assert mock_bot_client.chat_postMessage.call_count == 1  # Single message

    @patch('gh_analysis.slack.client.SlackClient.bot_client')
    def test_multi_message_for_large_content(self, mock_bot_client):
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Large analysis results that require splitting
        results = {
            "status": "resolved",
            "root_cause": "A" * 5000,  # Very long content
            "recommended_solution": "B" * 5000,  # Very long content
            "evidence": [f"Evidence {i}" for i in range(20)]  # Many evidence points
        }

        success = self.client.notify_analysis_complete(
            "https://github.com/test/test/issues/1",
            "Test Issue",
            results,
            "test_agent"
        )

        assert success
        assert mock_bot_client.chat_postMessage.call_count > 1  # Multiple messages

        # Verify thread organization
        calls = mock_bot_client.chat_postMessage.call_args_list
        first_call = calls[0][1]  # First message
        assert "thread_ts" not in first_call  # First message creates thread

        for call in calls[1:]:  # Subsequent messages
            assert "thread_ts" in call[1]  # Should be thread replies
            assert call[1]["thread_ts"] == "123"  # Same thread
```

**Integration Tests** (`tests/test_slack_integration.py`):
```python
import pytest
from unittest.mock import Mock, patch
from gh_analysis.slack.client import SlackClient
from gh_analysis.slack.config import SlackConfig

class TestSlackIntegration:
    @pytest.fixture
    def real_analysis_results(self):
        # Load real analysis results from fixture file
        return {
            "status": "resolved",
            "root_cause": """The issue is caused by a memory leak in the connection pooling mechanism.
            When connections are not properly closed after timeout, they remain in the pool consuming memory.
            Over time, this leads to memory exhaustion and application crashes. The root cause is in the
            connection cleanup logic in the database adapter where timeout connections are marked as closed
            but not actually removed from the pool. This creates a gradual memory leak that manifests as
            increasing memory usage over several hours of operation. The problem is exacerbated when there
            are many concurrent connections and network instability causes frequent timeouts.""",
            "recommended_solution": """1. Fix the connection pool cleanup by ensuring timed-out connections
            are fully removed from the pool, not just marked as closed.
            2. Implement proper connection lifecycle management with explicit cleanup in finally blocks.
            3. Add connection pool monitoring and alerting to detect memory leaks early.
            4. Set maximum connection pool size limits to prevent runaway memory usage.
            5. Implement connection health checks to proactively remove stale connections.
            6. Add comprehensive logging around connection management for debugging.""",
            "evidence": [
                "Memory usage increases steadily over 4-6 hours",
                "Application crashes with OutOfMemoryError after 8 hours",
                "Connection pool shows increasing number of 'closed' connections",
                "Network timeout errors correlate with memory spikes",
                "Problem only occurs under load with concurrent requests",
                "Restarting application temporarily resolves the issue",
                "Memory dump shows connection objects not being garbage collected"
            ]
        }

    @patch('gh_analysis.slack.client.SlackClient.bot_client')
    @patch('gh_analysis.slack.client.SlackClient.user_client')
    def test_complete_workflow_with_real_data(self, mock_user_client, mock_bot_client, real_analysis_results):
        # Mock Slack API responses
        mock_user_client.search_messages.return_value = {"ok": True, "messages": {"total": 0}}
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123.456"}

        client = SlackClient(SlackConfig())

        success = client.notify_analysis_complete(
            "https://github.com/myorg/myapp/issues/42",
            "Memory leak causing application crashes",
            real_analysis_results,
            "gpt5_mini_medium_mt"
        )

        assert success

        # Verify content preservation
        calls = mock_bot_client.chat_postMessage.call_args_list
        all_posted_text = ""
        for call in calls:
            blocks = call[1]["blocks"]
            for block in blocks:
                if block.get("type") == "section" and "text" in block:
                    all_posted_text += block["text"]["text"]

        # Verify all original content appears in posted messages
        assert real_analysis_results["root_cause"] in all_posted_text
        assert real_analysis_results["recommended_solution"] in all_posted_text
        for evidence in real_analysis_results["evidence"][:5]:  # First 5 evidence points
            assert evidence in all_posted_text

    @patch('gh_analysis.slack.client.SlackClient.bot_client')
    def test_partial_posting_failure_handling(self, mock_bot_client):
        # Simulate partial failure - first message succeeds, second fails
        mock_responses = [
            {"ok": True, "ts": "123.456"},   # First message succeeds
            {"ok": False, "error": "rate_limited"},  # Second message fails
            {"ok": True, "ts": "123.789"},   # Third message succeeds
        ]
        mock_bot_client.chat_postMessage.side_effect = mock_responses

        results = {
            "status": "resolved",
            "root_cause": "A" * 4000,
            "recommended_solution": "B" * 4000
        }

        client = SlackClient(SlackConfig())
        success = client.notify_analysis_complete(
            "https://github.com/test/test/issues/1",
            "Test Issue",
            results,
            "test_agent"
        )

        assert not success  # Should fail due to partial failure
        assert mock_bot_client.chat_postMessage.call_count == 3
```

**Test Data Creation Commands**:
```bash
# Generate test data with different content lengths for comprehensive testing

# Normal length analysis (should use single message)
uv run gh-analysis process troubleshoot --url [SIMPLE-ISSUE-URL] --agent gpt5_mini_medium_mt --dry-run > tests/fixtures/normal_analysis_results.json

# Long analysis (should trigger topic splitting)
uv run gh-analysis process troubleshoot --url [COMPLEX-ISSUE-URL] --agent gpt5_mini_medium_mt --include-images --dry-run > tests/fixtures/long_analysis_results.json

# Very long analysis (should create multiple topic messages)
uv run gh-analysis process troubleshoot --url [VERY-COMPLEX-ISSUE-URL] --agent gpt5_high_mt --include-images --dry-run > tests/fixtures/very_long_analysis_results.json

# Create synthetic test data for edge cases
python -c "
import json

# Create test case with extremely long root cause (>5000 chars)
test_data = {
    'status': 'resolved',
    'root_cause': 'The fundamental issue stems from ' + 'A' * 5000 + '. This creates problems.',
    'recommended_solution': 'To resolve this issue ' + 'B' * 4000 + '. Follow these steps.',
    'evidence': [f'Evidence point {i}: ' + 'C' * 100 for i in range(15)],
    'next_steps': []
}

with open('tests/fixtures/extreme_length_test.json', 'w') as f:
    json.dump(test_data, f, indent=2)

print('Created extreme length test data')
"
```

### 7. Critical Implementation Notes for Agent

**IMPORTANT**: When implementing this task, pay special attention to:

1. **Import Structure**: The `text_utils.py` module is new and needs to be created from scratch
2. **Method Replacement**: The existing `_format_analysis_results` method should be DEPRECATED, not deleted (keep for reference)
3. **Backward Compatibility**: The `post_to_thread` method signature must remain unchanged
4. **Error Handling**: Each topic formatting method should handle missing/None data gracefully
5. **Logging**: Add comprehensive logging for debugging multi-message flows

**Files to Create**:
- `gh_analysis/slack/text_utils.py` (new file)

**Files to Modify**:
- `gh_analysis/slack/client.py` (major refactoring)

**Files to Test**:
- Create `tests/test_slack_splitting.py` (new test file)
- Update existing tests in `tests/test_troubleshooting_functional.py` if they mock Slack

### 8. Validation Commands

**Development Validation**:
```bash
# Run quality checks after implementation
uv run ruff format . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest

# Test new text utilities in isolation
python -c "
from gh_analysis.slack.text_utils import split_text_at_boundaries, create_continuation_header

# Test basic splitting
long_text = 'A' * 3000
parts = split_text_at_boundaries(long_text, 2900)
print(f'Split {len(long_text)} chars into {len(parts)} parts')
for i, part in enumerate(parts):
    print(f'  Part {i+1}: {len(part)} chars')

# Test continuation headers
print(f\"Normal header: '{create_continuation_header('Root Cause', False)}'")
print(f\"Continued header: '{create_continuation_header('Root Cause', True)}'")
print('✅ Text utilities working correctly')
"

# Test topic-based formatting with mock data
python -c "
from gh_analysis.slack.client import SlackClient
from gh_analysis.slack.config import SlackConfig

client = SlackClient(SlackConfig())

# Test different content scenarios
test_cases = [
    {'name': 'Short content', 'root_cause': 'Simple cause', 'status': 'resolved'},
    {'name': 'Long content', 'root_cause': 'A' * 3500, 'status': 'resolved'},
    {'name': 'Very long content', 'root_cause': 'B' * 10000, 'status': 'resolved'},
]

for test in test_cases:
    blocks = client._format_root_cause_topic(test)
    print(f\"{test['name']}: {len(blocks)} blocks generated\")
    for block in blocks:
        if 'text' in block and 'text' in block['text']:
            text_len = len(block['text']['text'])
            assert text_len <= 3000, f'Block exceeds limit: {text_len} chars'

print('✅ All topic formatting respects character limits')
"

# Test complete notification flow with different content sizes
python -c "
from gh_analysis.slack.client import SlackClient
from gh_analysis.slack.config import SlackConfig
import json

# Test different content lengths
test_files = [
    'tests/fixtures/normal_analysis_results.json',
    'tests/fixtures/long_analysis_results.json',
    'tests/fixtures/very_long_analysis_results.json'
]

client = SlackClient(SlackConfig())

for test_file in test_files:
    with open(test_file) as f:
        results = json.load(f)

    # Test new splitting method
    message_parts = client._split_analysis_into_messages(
        results, 'https://github.com/test/test/issues/1', 'test_agent'
    )

    total_chars = 0
    for i, message_blocks in enumerate(message_parts):
        message_char_count = sum(
            len(block.get('text', {}).get('text', ''))
            for block in message_blocks
            if block.get('type') == 'section' and 'text' in block
        )
        total_chars += message_char_count
        print(f'Message {i+1}/{len(message_parts)}: {len(message_blocks)} blocks, {message_char_count} chars')

        # Validate each block is under limit
        for j, block in enumerate(message_blocks):
            if block.get('type') == 'section' and 'text' in block:
                text_len = len(block['text']['text'])
                assert text_len <= 3000, f'Block {j} in message {i+1} exceeds limit: {text_len} chars'

    print(f'Total content preserved: {total_chars} characters in {len(message_parts)} messages')
    print('✅ All blocks within limits, zero content loss\n')
"

# Test with mock Slack posting (validate sequencing)
export SLACK_BOT_TOKEN="test-token" SLACK_USER_TOKEN="test-token"
uv run gh-analysis process troubleshoot --url [USER-PROVIDED-LONG-ISSUE-URL] --agent gpt5_mini_medium_mt --include-images --slack-notifications --dry-run
```

**Production Validation**:
```bash
# Test with real Slack integration (requires user setup)
uv run gh-analysis process troubleshoot --url [USER-LONG-ISSUE-URL] --agent gpt5_mini_medium_mt --include-images --slack-notifications

# Verify in Slack:
# 1. All analysis content appears (no truncation)
# 2. Messages are properly sequenced (1/3, 2/3, 3/3)
# 3. All messages appear in same thread
# 4. Content flows logically across message boundaries
# 5. Formatting is preserved (markdown, code blocks, lists)
```

### 8. Error Handling & Logging

**Add comprehensive logging in `SlackClient`**:
- Log when content requires multi-message splitting with message count
- Log successful sequential message posting with thread organization
- Log partial posting failures (which messages succeeded/failed)
- Log content preservation metrics (total chars preserved)
- Maintain existing error handling for Slack API failures

**Error Recovery**:
- If individual message posting fails, continue posting remaining messages
- Track which parts of analysis were successfully posted
- Provide detailed user feedback about partial success/failure
- Never fail the entire analysis due to Slack formatting issues
- Retry failed message parts once before giving up

### 9. Documentation Updates

**Update**: `gh_analysis/slack/client.py` docstrings
- Document multi-message posting strategy and content splitting
- Explain sequential message posting with thread organization
- Note Slack API constraints and how they're handled
- Document zero content loss guarantee

**Update**: `tasks/add-slack-notifications.md`
- Document the multi-posting solution for long content
- Add troubleshooting section for message sequencing issues
- Update usage examples showing multi-message thread organization
- Explain how very long analysis results are handled

### 10. Backward Compatibility Requirements

**CRITICAL**: This implementation MUST maintain backward compatibility:

1. **Existing Method Signatures**: Do NOT change the signature of:
   - `notify_analysis_complete(issue_url, issue_title, analysis_results, agent_name)`
   - `post_to_thread(thread_ts, analysis_results, issue_url, agent_name)`
   - `search_for_issue(issue_url)`

2. **Normal Content Behavior**: Content that fits in a single message (most common case) should:
   - Still post as a single message (no change in behavior)
   - Use the same formatting as before
   - Not trigger any new multi-message logic

3. **Existing Tests**: All existing tests should continue to pass without modification

4. **API Response Handling**: The return value (boolean success indicator) must remain the same

5. **Configuration**: No new environment variables or configuration required - existing config should work

### 11. Implementation Notes

**Content Preservation Strategy:**
- **Zero content loss**: Every character from analysis results must reach Slack
- Use 2,900 char limit (not 3,000) to account for JSON overhead and formatting
- Split at logical boundaries (sentence/paragraph breaks) when possible
- Preserve all markdown formatting across message boundaries

**Message Organization Strategy:**
1. **Single message preferred**: Use when all content fits comfortably
2. **Multi-message when needed**: Clear sequence indicators (1/3, 2/3, 3/3)
3. **Thread organization**: All parts posted to same thread for readability
4. **Logical flow**: Related content stays together (don't split root cause from evidence)

**Content Priority (for message boundaries):**
1. Header with status and agent info (Message 1)
2. Evidence points (complete in single message when possible)
3. Root cause analysis (can span messages if very long)
4. Solution/next steps (can span messages if very long)
5. Footer timestamp (final message)

**Backward Compatibility:**
- All existing functionality preserved
- No changes to CLI interface or configuration
- Normal-length content behavior unchanged (single message)
- Graceful enhancement for long content (multi-message)

**Performance Considerations:**
- Analyze content length once, then split efficiently
- Minimize Slack API calls while ensuring delivery
- Post messages sequentially to maintain order
- Use proper delays between messages if needed for rate limiting

This solution eliminates content truncation entirely while providing an elegant multi-message experience for long AI analysis results.

## Agent Notes

This task requires careful attention to:
1. **Zero content loss commitment**: Every character of analysis results must reach Slack - no truncation allowed
2. **Real-world testing**: Use actual long analysis results from troubleshooting commands (>10,000 chars) to validate splitting behavior
3. **Slack API compliance**: Ensure solution respects all limits (3,000 chars per section, 50 blocks per message) through intelligent splitting
4. **Thread organization**: Multi-message sequences must be well-organized with clear continuation indicators and proper threading
5. **Content flow**: Split at logical boundaries to maintain readability across message parts
6. **Error handling**: Partial posting failures should not prevent remaining content from being delivered
7. **Backward compatibility**: Normal-length content should behave exactly as before (single message)
8. **Performance**: Content analysis and splitting should be efficient without significant overhead

## Implementation Checklist

**Before Starting:**
- [ ] Read and understand the existing `gh_analysis/slack/client.py` implementation
- [ ] Review how `_format_analysis_results` currently works (will be replaced)
- [ ] Understand the Slack Block Kit structure and limits

**Implementation Steps:**
- [ ] Create `gh_analysis/slack/text_utils.py` with splitting utilities
- [ ] Add topic-based formatting methods to SlackClient
- [ ] Update `notify_analysis_complete` to use topic-based approach
- [ ] Add `_post_topic_sequence` for multi-message posting
- [ ] Add `_post_topic_replies_to_thread` for existing thread replies
- [ ] Deprecate (but keep) `_format_analysis_results` method
- [ ] Create comprehensive unit tests in `tests/test_slack_splitting.py`
- [ ] Test with real long analysis results
- [ ] Verify backward compatibility with normal-length content
- [ ] Update documentation

**Success Criteria:**
- [ ] No content is ever truncated or lost
- [ ] Long analysis results post successfully to Slack
- [ ] Messages organize logically in threads
- [ ] Normal content still posts as single message
- [ ] All tests pass including new and existing ones
- [ ] Quality checks pass (ruff, mypy, pytest)

The implementation should prioritize content preservation and user experience, ensuring complete AI analysis delivery through an elegant topic-based splitting approach.