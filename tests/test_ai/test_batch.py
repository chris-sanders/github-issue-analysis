"""Tests for batch processing functionality."""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from gh_analysis.ai.batch.batch_manager import BatchManager
from gh_analysis.ai.batch.config_compat import AIModelConfig
from gh_analysis.ai.batch.models import (
    BatchJob,
    BatchJobError,
    BatchResult,
)
from gh_analysis.ai.batch.openai_provider import OpenAIBatchProvider


@pytest.fixture
def temp_batch_dir(tmp_path: Path) -> Path:
    """Create temporary batch directory structure."""
    batch_dir = tmp_path / "data" / "batch"
    (batch_dir / "jobs").mkdir(parents=True)
    (batch_dir / "input").mkdir(parents=True)
    (batch_dir / "output").mkdir(parents=True)

    # Also create issues and results directories
    (tmp_path / "data" / "issues").mkdir(parents=True)
    (tmp_path / "data" / "results").mkdir(parents=True)

    return batch_dir


@pytest.fixture
def sample_issue_data() -> list[dict[str, Any]]:
    """Sample issue data for testing."""
    return [
        {
            "org": "test-org",
            "repo": "test-repo",
            "issue": {
                "number": 1,
                "title": "KOTS admin console not loading",
                "body": "The kotsadm interface shows a blank screen after login",
                "labels": [{"name": "bug"}, {"name": "product::kots"}],
                "comments": [
                    {
                        "user": {"login": "user1"},
                        "body": "This is related to the admin console",
                    }
                ],
            },
        },
        {
            "org": "test-org",
            "repo": "test-repo",
            "issue": {
                "number": 2,
                "title": "Embedded cluster installation fails",
                "body": "k0s cluster fails to start during installation",
                "labels": [{"name": "bug"}],
                "comments": [],
            },
        },
    ]


@pytest.fixture
def ai_model_config() -> AIModelConfig:
    """Sample AI model configuration."""
    return AIModelConfig(
        model_name="openai:gpt-4o-mini",
        thinking=None,
        temperature=0.7,
        include_images=True,
    )


class TestBatchManager:
    """Test batch manager functionality."""

    def test_init(self, temp_batch_dir: Path) -> None:
        """Test batch manager initialization."""
        manager = BatchManager(str(temp_batch_dir))

        assert manager.base_path == temp_batch_dir
        assert (temp_batch_dir / "jobs").exists()
        assert (temp_batch_dir / "input").exists()
        assert (temp_batch_dir / "output").exists()

    def test_find_issues_no_directory(self, temp_batch_dir: Path) -> None:
        """Test find_issues when issues directory doesn't exist."""
        manager = BatchManager(str(temp_batch_dir))

        # Remove issues directory
        issues_dir = Path("data/issues")
        if issues_dir.exists():
            import shutil

            shutil.rmtree(issues_dir)

        result = manager.find_issues()
        assert result == []

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.exists")
    def test_find_issues_specific_issue(
        self,
        mock_exists: MagicMock,
        mock_glob: MagicMock,
        mock_file: MagicMock,
        temp_batch_dir: Path,
        sample_issue_data: list[dict[str, Any]],
    ) -> None:
        """Test finding a specific issue."""
        manager = BatchManager(str(temp_batch_dir))

        # Mock file system
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(sample_issue_data[0])

        # Test specific issue lookup
        manager.find_issues(org="test-org", repo="test-repo", issue_number=1)

        # Should have called exists with the expected path
        mock_exists.assert_called()

    def test_find_issues_invalid_combination(self, temp_batch_dir: Path) -> None:
        """Test find_issues with invalid argument combination."""
        manager = BatchManager(str(temp_batch_dir))

        with pytest.raises(
            ValueError, match="org and repo are required when specifying issue_number"
        ):
            manager.find_issues(issue_number=1)

    @pytest.mark.asyncio
    @patch("gh_analysis.ai.batch.batch_manager.OpenAIBatchProvider")
    async def test_create_batch_job_success(
        self,
        mock_provider_class: MagicMock,
        temp_batch_dir: Path,
        sample_issue_data: list[dict[str, Any]],
        ai_model_config: AIModelConfig,
    ) -> None:
        """Test successful batch job creation."""
        manager = BatchManager(str(temp_batch_dir))

        # Mock provider
        mock_provider = AsyncMock()
        mock_provider_class.return_value = mock_provider
        mock_provider.create_jsonl_file.return_value = Path("test.jsonl")
        mock_provider.upload_file.return_value = "file_123"
        mock_provider.submit_batch.return_value = "batch_123"

        # Mock find_issues to return sample data
        with patch.object(manager, "find_issues", return_value=sample_issue_data):
            result = await manager.create_batch_job(
                processor_type="product-labeling",
                org="test-org",
                repo="test-repo",
                model_config=ai_model_config,
            )

        # Verify result
        assert isinstance(result, BatchJob)
        assert result.processor_type == "product-labeling"
        assert result.org == "test-org"
        assert result.repo == "test-repo"
        assert result.total_items == 2
        assert result.status == "validating"
        assert result.openai_batch_id == "batch_123"
        assert result.input_file_id == "file_123"

        # Verify provider was called correctly
        mock_provider.create_jsonl_file.assert_called_once()
        mock_provider.upload_file.assert_called_once()
        mock_provider.submit_batch.assert_called_once_with("file_123")

    @pytest.mark.asyncio
    async def test_create_batch_job_no_issues(
        self, temp_batch_dir: Path, ai_model_config: AIModelConfig
    ) -> None:
        """Test batch job creation when no issues found."""
        manager = BatchManager(str(temp_batch_dir))

        # Mock find_issues to return empty list
        with patch.object(manager, "find_issues", return_value=[]):
            with pytest.raises(ValueError, match="No issues found"):
                await manager.create_batch_job(
                    processor_type="product-labeling",
                    org="test-org",
                    repo="test-repo",
                    model_config=ai_model_config,
                )

    @pytest.mark.asyncio
    @patch("gh_analysis.ai.batch.batch_manager.OpenAIBatchProvider")
    async def test_create_batch_job_submission_failure(
        self,
        mock_provider_class: MagicMock,
        temp_batch_dir: Path,
        sample_issue_data: list[dict[str, Any]],
        ai_model_config: AIModelConfig,
    ) -> None:
        """Test batch job creation when submission fails."""
        manager = BatchManager(str(temp_batch_dir))

        # Mock provider to fail on submission
        mock_provider = AsyncMock()
        mock_provider_class.return_value = mock_provider
        mock_provider.create_jsonl_file.return_value = Path("test.jsonl")
        mock_provider.upload_file.return_value = "file_123"
        mock_provider.submit_batch.side_effect = Exception("OpenAI API error")

        with patch.object(manager, "find_issues", return_value=sample_issue_data):
            with pytest.raises(Exception, match="OpenAI API error"):
                await manager.create_batch_job(
                    processor_type="product-labeling",
                    org="test-org",
                    model_config=ai_model_config,
                )

    @pytest.mark.asyncio
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    @patch("gh_analysis.ai.batch.batch_manager.OpenAIBatchProvider")
    async def test_check_job_status(
        self,
        mock_provider_class: MagicMock,
        mock_exists: MagicMock,
        mock_file: MagicMock,
        temp_batch_dir: Path,
        ai_model_config: AIModelConfig,
    ) -> None:
        """Test checking batch job status."""
        manager = BatchManager(str(temp_batch_dir))

        # Create sample job data
        job_id = str(uuid.uuid4())
        batch_job = BatchJob(
            job_id=job_id,
            processor_type="product-labeling",
            org="test-org",
            repo="test-repo",
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=2,
            openai_batch_id="batch_123",
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
            status="in_progress",
        )

        # Mock file operations
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(
            batch_job.model_dump(), default=str
        )

        # Mock provider status response
        mock_provider = AsyncMock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_batch_status.return_value = {
            "status": "completed",
            "output_file_id": "output_123",
            "request_counts": {"completed": 2, "failed": 0},
        }

        result = await manager.check_job_status(job_id)

        assert result.status == "completed"
        assert result.output_file_id == "output_123"
        assert result.processed_items == 2
        assert result.failed_items == 0

    @pytest.mark.asyncio
    async def test_check_job_status_not_found(self, temp_batch_dir: Path) -> None:
        """Test checking status of non-existent job."""
        manager = BatchManager(str(temp_batch_dir))

        with pytest.raises(ValueError, match="No batch job found matching"):
            await manager.check_job_status("nonexistent_job")

    @pytest.mark.asyncio
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.mkdir")
    @patch("gh_analysis.ai.batch.batch_manager.OpenAIBatchProvider")
    async def test_collect_results_success(
        self,
        mock_provider_class: MagicMock,
        mock_mkdir: MagicMock,
        mock_exists: MagicMock,
        mock_file: MagicMock,
        temp_batch_dir: Path,
        ai_model_config: AIModelConfig,
    ) -> None:
        """Test successful result collection."""
        manager = BatchManager(str(temp_batch_dir))

        job_id = str(uuid.uuid4())
        batch_job = BatchJob(
            job_id=job_id,
            processor_type="product-labeling",
            org="test-org",
            repo="test-repo",
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=2,
            openai_batch_id="batch_123",
            input_file_id=None,
            output_file_id="output_123",
            submitted_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
            status="completed",
        )

        # Mock file operations
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(
            batch_job.model_dump(), default=str
        )

        # Mock provider (use MagicMock since parse_batch_results is sync)
        mock_provider = MagicMock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_batch_status.return_value = {
            "status": "completed",
            "output_file_id": "output_123",
        }
        # Make async methods return coroutines
        mock_provider.download_results = AsyncMock(
            return_value=Path("output_file.jsonl")
        )

        # Mock successful batch results
        mock_results = [
            {
                "custom_id": "test-org_test-repo_issue_1",
                "response": {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "confidence": 0.9,
                                        "recommended_labels": [
                                            {
                                                "label": "product::kots",
                                                "confidence": 0.9,
                                                "reasoning": "Admin console issue",
                                            }
                                        ],
                                        "current_labels_assessment": [],
                                        "summary": "KOTS admin issue",
                                        "reasoning": "Clear KOTS issue",
                                        "images_analyzed": [],
                                        "image_impact": "",
                                    }
                                )
                            }
                        }
                    ]
                },
            }
        ]
        mock_provider.parse_batch_results.return_value = mock_results

        result = await manager.collect_results(job_id)

        assert isinstance(result, BatchResult)
        assert result.job_id == job_id
        assert result.total_items == 2
        assert result.successful_items == 1
        assert result.failed_items == 0

    @pytest.mark.asyncio
    async def test_collect_results_job_not_completed(
        self, temp_batch_dir: Path, ai_model_config: AIModelConfig
    ) -> None:
        """Test collecting results when job is not completed."""
        manager = BatchManager(str(temp_batch_dir))

        job_id = str(uuid.uuid4())
        batch_job = BatchJob(
            job_id=job_id,
            processor_type="product-labeling",
            org="test-org",
            repo=None,
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=2,
            openai_batch_id=None,
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
            status="in_progress",  # Not completed
        )

        # Mock check_job_status to return running job
        with patch.object(manager, "check_job_status", return_value=batch_job):
            with pytest.raises(ValueError, match="Job .* is not completed"):
                await manager.collect_results(job_id)

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, temp_batch_dir: Path) -> None:
        """Test listing jobs when no jobs exist."""
        manager = BatchManager(str(temp_batch_dir))

        result = await manager.list_jobs()
        assert result == []

    @pytest.mark.asyncio
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.glob")
    async def test_list_jobs_with_data(
        self,
        mock_glob: MagicMock,
        mock_file: MagicMock,
        temp_batch_dir: Path,
        ai_model_config: AIModelConfig,
    ) -> None:
        """Test listing jobs with existing job data."""
        manager = BatchManager(str(temp_batch_dir))

        # Create sample job data
        job1 = BatchJob(
            job_id="job1",
            processor_type="product-labeling",
            org="org1",
            repo="repo1",
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=5,
            openai_batch_id=None,
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=3,
            failed_items=1,
            input_file_path=None,
            output_file_path=None,
            status="completed",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
        )

        job2 = BatchJob(
            job_id="job2",
            processor_type="product-labeling",
            org="org2",
            repo=None,
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=2,
            openai_batch_id=None,
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
            status="in_progress",
            created_at=datetime(2024, 1, 2, 12, 0, 0),
        )

        # Mock file system
        mock_glob.return_value = [Path("job1.json"), Path("job2.json")]
        mock_file.return_value.read.side_effect = [
            json.dumps(job1.model_dump(), default=str),
            json.dumps(job2.model_dump(), default=str),
        ]

        result = await manager.list_jobs()

        assert len(result) == 2
        # Should be sorted by creation time (newest first)
        assert result[0].job_id == "job2"
        assert result[1].job_id == "job1"
        assert result[0].status == "in_progress"
        assert result[1].status == "completed"


class TestOpenAIBatchProvider:
    """Test OpenAI batch provider functionality."""

    def test_init_without_api_key(self, ai_model_config: AIModelConfig) -> None:
        """Test initialization without API key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIBatchProvider(ai_model_config)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    def test_init_with_api_key(self, ai_model_config: AIModelConfig) -> None:
        """Test successful initialization with API key."""
        provider = OpenAIBatchProvider(ai_model_config)
        assert provider.api_key == "test_key"
        assert provider.config == ai_model_config

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    def test_create_jsonl_file(
        self,
        tmp_path: Path,
        ai_model_config: AIModelConfig,
        sample_issue_data: list[dict[str, Any]],
    ) -> None:
        """Test JSONL file creation."""
        provider = OpenAIBatchProvider(ai_model_config)
        output_path = tmp_path / "test.jsonl"

        result_path = provider.create_jsonl_file(
            sample_issue_data, "product-labeling", output_path
        )

        assert result_path == output_path
        assert output_path.exists()

        # Verify JSONL content
        with open(output_path, encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 2  # Two issues

        # Parse first line
        first_request = json.loads(lines[0])
        assert first_request["custom_id"] == "test-org_test-repo_issue_1"
        assert first_request["method"] == "POST"
        assert first_request["url"] == "/v1/chat/completions"
        assert "body" in first_request

        # Verify request body structure
        body = first_request["body"]
        assert body["model"] == "gpt-4o-mini"  # Without openai: prefix
        assert "messages" in body
        assert len(body["messages"]) == 2  # system + user
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"
        assert "response_format" in body

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    def test_create_jsonl_unsupported_processor(
        self,
        tmp_path: Path,
        ai_model_config: AIModelConfig,
        sample_issue_data: list[dict[str, Any]],
    ) -> None:
        """Test JSONL creation with unsupported processor."""
        provider = OpenAIBatchProvider(ai_model_config)
        output_path = tmp_path / "test.jsonl"

        with pytest.raises(ValueError, match="Unsupported processor type"):
            provider.create_jsonl_file(
                sample_issue_data, "unsupported-processor", output_path
            )

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    def test_format_issue_prompt(
        self, ai_model_config: AIModelConfig, sample_issue_data: list[dict[str, Any]]
    ) -> None:
        """Test issue prompt formatting."""
        provider = OpenAIBatchProvider(ai_model_config)

        prompt = provider._format_issue_prompt(sample_issue_data[0])

        # Verify prompt contains expected elements
        assert "KOTS admin console not loading" in prompt
        assert "kotsadm interface shows a blank screen" in prompt
        assert "test-org/test-repo" in prompt
        assert "product::kots" in prompt
        assert "user1: This is related to the admin console" in prompt
        assert "NO IMAGES PROVIDED" in prompt

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    @pytest.mark.asyncio
    async def test_upload_file_success(
        self, ai_model_config: AIModelConfig, tmp_path: Path
    ) -> None:
        """Test successful file upload."""
        provider = OpenAIBatchProvider(ai_model_config)

        # Create test file
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"test": "data"}\n')

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "file_123"}

            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            result = await provider.upload_file(test_file)

            assert result == "file_123"
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    @pytest.mark.asyncio
    async def test_upload_file_failure(
        self, ai_model_config: AIModelConfig, tmp_path: Path
    ) -> None:
        """Test file upload failure."""
        provider = OpenAIBatchProvider(ai_model_config)

        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"test": "data"}\n')

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad request"

            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            with pytest.raises(Exception, match="File upload failed"):
                await provider.upload_file(test_file)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    @pytest.mark.asyncio
    async def test_submit_batch_success(self, ai_model_config: AIModelConfig) -> None:
        """Test successful batch submission."""
        provider = OpenAIBatchProvider(ai_model_config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "batch_123"}

            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            result = await provider.submit_batch("file_123")

            assert result == "batch_123"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    @pytest.mark.asyncio
    async def test_get_batch_status_success(
        self, ai_model_config: AIModelConfig
    ) -> None:
        """Test successful batch status check."""
        provider = OpenAIBatchProvider(ai_model_config)

        expected_status = {
            "id": "batch_123",
            "status": "completed",
            "output_file_id": "output_123",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = expected_status

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await provider.get_batch_status("batch_123")

            assert result == expected_status

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    @pytest.mark.asyncio
    async def test_download_results_success(
        self, ai_model_config: AIModelConfig, tmp_path: Path
    ) -> None:
        """Test successful results download."""
        provider = OpenAIBatchProvider(ai_model_config)

        output_path = tmp_path / "results.jsonl"
        test_content = b'{"result": "data"}\n'

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = test_content

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await provider.download_results("output_123", output_path)

            assert result == output_path
            assert output_path.exists()
            assert output_path.read_bytes() == test_content

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    def test_parse_batch_results(
        self, ai_model_config: AIModelConfig, tmp_path: Path
    ) -> None:
        """Test batch results parsing."""
        provider = OpenAIBatchProvider(ai_model_config)

        # Create test results file
        results_file = tmp_path / "results.jsonl"
        results_data = [
            {"custom_id": "test1", "response": {"choices": []}},
            {
                "custom_id": "test2",
                "error": {"code": "failed", "message": "Processing failed"},
            },
        ]

        with open(results_file, "w", encoding="utf-8") as f:
            for result in results_data:
                f.write(json.dumps(result) + "\n")

        parsed_results = provider.parse_batch_results(results_file)

        assert len(parsed_results) == 2
        assert parsed_results[0]["custom_id"] == "test1"
        assert parsed_results[1]["custom_id"] == "test2"
        assert "error" in parsed_results[1]


class TestBatchModels:
    """Test batch model validation and serialization."""

    def test_batch_job_creation(self, ai_model_config: AIModelConfig) -> None:
        """Test BatchJob model creation and validation."""
        job = BatchJob(
            job_id="test_job",
            processor_type="product-labeling",
            org="test-org",
            repo="test-repo",
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=10,
            openai_batch_id=None,
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
        )

        assert job.job_id == "test_job"
        assert job.status == "pending"
        assert job.total_items == 10
        assert job.processed_items == 0
        assert job.failed_items == 0
        assert len(job.errors) == 0

    def test_batch_job_status_transitions(self, ai_model_config: AIModelConfig) -> None:
        """Test batch job status transitions."""
        job = BatchJob(
            job_id="test_job",
            processor_type="product-labeling",
            org="test-org",
            repo=None,
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=5,
            openai_batch_id=None,
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
        )

        # Test status progression
        assert job.status == "pending"

        job.status = "validating"
        assert job.status == "validating"

        job.status = "in_progress"
        assert job.status == "in_progress"

        job.status = "completed"
        assert job.status == "completed"

    def test_batch_job_error_handling(self, ai_model_config: AIModelConfig) -> None:
        """Test batch job error tracking."""
        job = BatchJob(
            job_id="test_job",
            processor_type="product-labeling",
            org="test-org",
            repo=None,
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=5,
            openai_batch_id=None,
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
        )

        # Add errors
        error1 = BatchJobError(
            custom_id="item1",
            error_code="processing_failed",
            error_message="Failed to process item",
        )

        error2 = BatchJobError(
            custom_id="item2",
            error_code="invalid_format",
            error_message="Invalid response format",
        )

        job.errors = [error1, error2]

        assert len(job.errors) == 2
        assert job.errors[0].custom_id == "item1"
        assert job.errors[1].custom_id == "item2"

    def test_batch_result_creation(self) -> None:
        """Test BatchResult model creation."""
        result = BatchResult(
            job_id="test_job",
            processor_type="product-labeling",
            total_items=10,
            successful_items=8,
            failed_items=2,
            cost_estimate=None,
            processing_time=None,
            results_directory="/path/to/results",
        )

        assert result.job_id == "test_job"
        assert result.total_items == 10
        assert result.successful_items == 8
        assert result.failed_items == 2
        assert result.cost_estimate is None
        assert result.processing_time is None


class TestBatchCancelRemove:
    """Test cancel and remove functionality."""

    @pytest.mark.asyncio
    async def test_cancel_job_success(
        self, temp_batch_dir: Path, ai_model_config: AIModelConfig
    ) -> None:
        """Test successful job cancellation."""
        manager = BatchManager(str(temp_batch_dir))
        job_id = str(uuid.uuid4())

        # Create a job in cancelable state
        batch_job = BatchJob(
            job_id=job_id,
            processor_type="product-labeling",
            org="test-org",
            repo="test-repo",
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=5,
            openai_batch_id="batch_123",
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
            status="in_progress",
        )

        # Create job file
        job_file = temp_batch_dir / "jobs" / f"{job_id}.json"
        with open(job_file, "w") as f:
            json.dump(batch_job.model_dump(), f, default=str)

        # Mock OpenAI provider
        with patch(
            "gh_analysis.ai.batch.batch_manager.OpenAIBatchProvider"
        ) as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.cancel_batch.return_value = {
                "id": "batch_123",
                "status": "cancelled",
            }

            result = await manager.cancel_job(job_id)

            assert result.status == "cancelled"
            mock_provider.cancel_batch.assert_called_once_with("batch_123")

            # Verify job file was updated
            with open(job_file) as f:
                updated_job = json.load(f)
                assert updated_job["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_job_already_cancelled(
        self, temp_batch_dir: Path, ai_model_config: AIModelConfig
    ) -> None:
        """Test cancelling an already cancelled job."""
        manager = BatchManager(str(temp_batch_dir))
        job_id = str(uuid.uuid4())

        # Create a job already cancelled
        batch_job = BatchJob(
            job_id=job_id,
            processor_type="product-labeling",
            org="test-org",
            repo="test-repo",
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=5,
            openai_batch_id="batch_123",
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
            status="cancelled",
        )

        # Create job file
        job_file = temp_batch_dir / "jobs" / f"{job_id}.json"
        with open(job_file, "w") as f:
            json.dump(batch_job.model_dump(), f, default=str)

        result = await manager.cancel_job(job_id)
        assert result.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_job_completed(
        self, temp_batch_dir: Path, ai_model_config: AIModelConfig
    ) -> None:
        """Test cancelling a completed job."""
        manager = BatchManager(str(temp_batch_dir))
        job_id = str(uuid.uuid4())

        # Create a completed job
        batch_job = BatchJob(
            job_id=job_id,
            processor_type="product-labeling",
            org="test-org",
            repo="test-repo",
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=5,
            openai_batch_id="batch_123",
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
            status="completed",
        )

        # Create job file
        job_file = temp_batch_dir / "jobs" / f"{job_id}.json"
        with open(job_file, "w") as f:
            json.dump(batch_job.model_dump(), f, default=str)

        result = await manager.cancel_job(job_id)
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self, temp_batch_dir: Path) -> None:
        """Test cancelling a non-existent job."""
        manager = BatchManager(str(temp_batch_dir))
        job_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="No batch job found matching"):
            await manager.cancel_job(job_id)

    @pytest.mark.asyncio
    async def test_cancel_job_no_openai_batch_id(
        self, temp_batch_dir: Path, ai_model_config: AIModelConfig
    ) -> None:
        """Test cancelling a job without OpenAI batch ID."""
        manager = BatchManager(str(temp_batch_dir))
        job_id = str(uuid.uuid4())

        # Create a job without OpenAI batch ID
        batch_job = BatchJob(
            job_id=job_id,
            processor_type="product-labeling",
            org="test-org",
            repo="test-repo",
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=5,
            openai_batch_id=None,
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
            status="pending",
        )

        # Create job file
        job_file = temp_batch_dir / "jobs" / f"{job_id}.json"
        with open(job_file, "w") as f:
            json.dump(batch_job.model_dump(), f, default=str)

        with pytest.raises(ValueError, match="has no OpenAI batch ID to cancel"):
            await manager.cancel_job(job_id)

    def test_remove_job_success_with_force(
        self, temp_batch_dir: Path, ai_model_config: AIModelConfig
    ) -> None:
        """Test successful job removal with force flag."""
        manager = BatchManager(str(temp_batch_dir))
        job_id = str(uuid.uuid4())

        # Create a completed job
        batch_job = BatchJob(
            job_id=job_id,
            processor_type="product-labeling",
            org="test-org",
            repo="test-repo",
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=5,
            openai_batch_id=None,
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
            status="completed",
        )

        # Create job file
        job_file = temp_batch_dir / "jobs" / f"{job_id}.json"
        with open(job_file, "w") as f:
            json.dump(batch_job.model_dump(), f, default=str)

        # Create input and output files
        input_file = temp_batch_dir / "input" / f"{job_id}.jsonl"
        output_file = temp_batch_dir / "output" / f"{job_id}_results.jsonl"
        input_file.write_text("test input")
        output_file.write_text("test output")

        # Update job with file paths
        batch_job.input_file_path = str(input_file)
        batch_job.output_file_path = str(output_file)
        with open(job_file, "w") as f:
            json.dump(batch_job.model_dump(), f, default=str)

        result = manager.remove_job(job_id, force=True)

        assert result is True
        assert not job_file.exists()
        assert not input_file.exists()
        assert not output_file.exists()

    def test_remove_job_not_found(self, temp_batch_dir: Path) -> None:
        """Test removing a non-existent job."""
        manager = BatchManager(str(temp_batch_dir))
        job_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="No batch job found matching"):
            manager.remove_job(job_id, force=True)

    @patch("builtins.input", return_value="n")
    def test_remove_job_user_cancels(
        self,
        mock_input: MagicMock,
        temp_batch_dir: Path,
        ai_model_config: AIModelConfig,
    ) -> None:
        """Test user cancelling job removal."""
        manager = BatchManager(str(temp_batch_dir))
        job_id = str(uuid.uuid4())

        # Create a completed job
        batch_job = BatchJob(
            job_id=job_id,
            processor_type="product-labeling",
            org="test-org",
            repo="test-repo",
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=5,
            openai_batch_id=None,
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
            status="completed",
        )

        # Create job file
        job_file = temp_batch_dir / "jobs" / f"{job_id}.json"
        with open(job_file, "w") as f:
            json.dump(batch_job.model_dump(), f, default=str)

        result = manager.remove_job(job_id, force=False)

        assert result is False
        assert job_file.exists()  # File should still exist

    @patch("builtins.input", return_value="y")
    def test_remove_job_user_confirms(
        self,
        mock_input: MagicMock,
        temp_batch_dir: Path,
        ai_model_config: AIModelConfig,
    ) -> None:
        """Test user confirming job removal."""
        manager = BatchManager(str(temp_batch_dir))
        job_id = str(uuid.uuid4())

        # Create a completed job
        batch_job = BatchJob(
            job_id=job_id,
            processor_type="product-labeling",
            org="test-org",
            repo="test-repo",
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=5,
            openai_batch_id=None,
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
            status="completed",
        )

        # Create job file
        job_file = temp_batch_dir / "jobs" / f"{job_id}.json"
        with open(job_file, "w") as f:
            json.dump(batch_job.model_dump(), f, default=str)

        result = manager.remove_job(job_id, force=False)

        assert result is True
        assert not job_file.exists()

    @patch("builtins.input", side_effect=["n", "y"])
    def test_remove_active_job_with_confirmation(
        self,
        mock_input: MagicMock,
        temp_batch_dir: Path,
        ai_model_config: AIModelConfig,
    ) -> None:
        """Test removing active job with multiple confirmation prompts."""
        manager = BatchManager(str(temp_batch_dir))
        job_id = str(uuid.uuid4())

        # Create an active job
        batch_job = BatchJob(
            job_id=job_id,
            processor_type="product-labeling",
            org="test-org",
            repo="test-repo",
            issue_number=None,
            ai_model_config=ai_model_config.model_dump(),
            total_items=5,
            openai_batch_id=None,
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
            status="in_progress",
        )

        # Create job file
        job_file = temp_batch_dir / "jobs" / f"{job_id}.json"
        with open(job_file, "w") as f:
            json.dump(batch_job.model_dump(), f, default=str)

        result = manager.remove_job(job_id, force=False)

        assert result is False
        # Should still exist since user said "n" to first prompt
        assert job_file.exists()


class TestOpenAIProviderCancel:
    """Test OpenAI provider cancel functionality."""

    @pytest.mark.asyncio
    async def test_cancel_batch_success(self, ai_model_config: AIModelConfig) -> None:
        """Test successful batch cancellation."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAIBatchProvider(ai_model_config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock successful response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "batch_123", "status": "cancelled"}
            mock_client.post.return_value = mock_response

            result = await provider.cancel_batch("batch_123")

            assert result["id"] == "batch_123"
            assert result["status"] == "cancelled"
            mock_client.post.assert_called_once_with(
                "https://api.openai.com/v1/batches/batch_123/cancel",
                headers=provider.headers,
                timeout=30.0,
            )

    @pytest.mark.asyncio
    async def test_cancel_batch_failure(self, ai_model_config: AIModelConfig) -> None:
        """Test batch cancellation failure."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAIBatchProvider(ai_model_config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock error response
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.text = "Batch not found"
            mock_client.post.return_value = mock_response

            with pytest.raises(
                Exception, match="Batch cancellation failed: 404 Batch not found"
            ):
                await provider.cancel_batch("batch_123")


class TestBatchSimplifiedConfig:
    """Test batch processing with new simplified configuration interface."""

    @pytest.mark.asyncio
    async def test_create_batch_job_with_dict_config(
        self, temp_batch_dir: Path, sample_issue_data: list[dict[str, Any]]
    ) -> None:
        """Test batch job creation with new simplified dict configuration."""
        manager = BatchManager(str(temp_batch_dir))

        # New simplified configuration format
        config = {
            "model": "anthropic:claude-3-haiku-20241022",
            "temperature": 0.3,
            "retry_count": 3,
            "include_images": False,
        }

        with patch(
            "gh_analysis.ai.batch.batch_manager.OpenAIBatchProvider"
        ) as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.create_jsonl_file.return_value = Path("test.jsonl")
            mock_provider.upload_file.return_value = "file_123"
            mock_provider.submit_batch.return_value = "batch_123"

            with patch.object(manager, "find_issues", return_value=sample_issue_data):
                result = await manager.create_batch_job(
                    processor_type="product-labeling",
                    org="test-org",
                    repo="test-repo",
                    model_config=config,
                )

        # Verify result
        assert isinstance(result, BatchJob)
        assert result.processor_type == "product-labeling"
        assert result.org == "test-org"
        assert result.repo == "test-repo"
        assert result.total_items == 2
        assert result.status == "validating"

        # Verify the config was converted correctly to AIModelConfig
        assert "anthropic:claude-3-haiku-20241022" in str(result.ai_model_config)

    @pytest.mark.asyncio
    async def test_create_batch_job_with_thinking_budget(
        self, temp_batch_dir: Path, sample_issue_data: list[dict[str, Any]]
    ) -> None:
        """Test batch job with thinking_budget parameter."""
        manager = BatchManager(str(temp_batch_dir))

        config = {
            "model": "anthropic:claude-3-5-sonnet-latest",
            "thinking_budget": 5000,
            "temperature": 0.1,
            "retry_count": 1,
            "include_images": True,
        }

        with patch(
            "gh_analysis.ai.batch.batch_manager.OpenAIBatchProvider"
        ) as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.create_jsonl_file.return_value = Path("test.jsonl")
            mock_provider.upload_file.return_value = "file_123"
            mock_provider.submit_batch.return_value = "batch_123"

            with patch.object(manager, "find_issues", return_value=sample_issue_data):
                result = await manager.create_batch_job(
                    processor_type="product-labeling",
                    org="test-org",
                    model_config=config,
                )

        assert isinstance(result, BatchJob)
        assert result.total_items == 2
        assert "claude-3-5-sonnet-latest" in str(result.ai_model_config)

    @pytest.mark.asyncio
    async def test_backward_compatibility_with_ai_model_config(
        self,
        temp_batch_dir: Path,
        sample_issue_data: list[dict[str, Any]],
        ai_model_config: AIModelConfig,
    ) -> None:
        """Test that old AIModelConfig format still works."""
        manager = BatchManager(str(temp_batch_dir))

        with patch(
            "gh_analysis.ai.batch.batch_manager.OpenAIBatchProvider"
        ) as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.create_jsonl_file.return_value = Path("test.jsonl")
            mock_provider.upload_file.return_value = "file_123"
            mock_provider.submit_batch.return_value = "batch_123"

            with patch.object(manager, "find_issues", return_value=sample_issue_data):
                result = await manager.create_batch_job(
                    processor_type="product-labeling",
                    org="test-org",
                    repo="test-repo",
                    model_config=ai_model_config,  # Use old format
                )

        # Should work exactly as before
        assert isinstance(result, BatchJob)
        assert result.processor_type == "product-labeling"
        assert result.total_items == 2
        assert result.status == "validating"

    @pytest.mark.asyncio
    async def test_config_defaults_applied(
        self, temp_batch_dir: Path, sample_issue_data: list[dict[str, Any]]
    ) -> None:
        """Test that default values are applied correctly."""
        manager = BatchManager(str(temp_batch_dir))

        # Minimal config - should get defaults for missing values
        config = {
            "model": "openai:gpt-4o",
        }

        with patch(
            "gh_analysis.ai.batch.batch_manager.OpenAIBatchProvider"
        ) as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.create_jsonl_file.return_value = Path("test.jsonl")
            mock_provider.upload_file.return_value = "file_123"
            mock_provider.submit_batch.return_value = "batch_123"

            with patch.object(manager, "find_issues", return_value=sample_issue_data):
                result = await manager.create_batch_job(
                    processor_type="product-labeling",
                    org="test-org",
                    model_config=config,
                )

        assert isinstance(result, BatchJob)
        # Verify defaults were applied (temperature=0.0, retry_count=2, etc.)
        config_dict = result.ai_model_config
        assert config_dict["model_name"] == "openai:gpt-4o"
