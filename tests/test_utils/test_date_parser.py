"""Tests for date parsing and validation utilities."""

from datetime import datetime, timedelta

import pytest

from gh_analysis.utils.date_parser import (
    format_datetime_for_github,
    parse_date_input,
    relative_date_to_absolute,
    validate_date_parameters,
    validate_date_range,
)


class TestParseDateInput:
    """Test date input parsing functionality."""

    def test_parse_iso_date(self) -> None:
        """Test parsing of ISO date formats."""
        result = parse_date_input("2024-01-15")
        expected = datetime(2024, 1, 15)
        assert result == expected

    def test_parse_iso_datetime(self) -> None:
        """Test parsing of ISO datetime formats."""
        result = parse_date_input("2024-01-15T10:30:00Z")
        expected = datetime(2024, 1, 15, 10, 30, 0)
        assert result == expected

    def test_parse_iso_datetime_no_z(self) -> None:
        """Test parsing of ISO datetime without Z suffix."""
        result = parse_date_input("2024-01-15T10:30:00")
        expected = datetime(2024, 1, 15, 10, 30, 0)
        assert result == expected

    def test_parse_full_month_name(self) -> None:
        """Test parsing of full month names."""
        result = parse_date_input("January 15, 2024")
        expected = datetime(2024, 1, 15)
        assert result == expected

    def test_parse_abbreviated_month_name(self) -> None:
        """Test parsing of abbreviated month names."""
        result = parse_date_input("Jan 15, 2024")
        expected = datetime(2024, 1, 15)
        assert result == expected

    def test_parse_month_name_no_comma(self) -> None:
        """Test parsing of month names without comma."""
        result = parse_date_input("January 15 2024")
        expected = datetime(2024, 1, 15)
        assert result == expected

    def test_parse_slash_format_year_first(self) -> None:
        """Test parsing of YYYY/MM/DD format."""
        result = parse_date_input("2024/01/15")
        expected = datetime(2024, 1, 15)
        assert result == expected

    def test_parse_slash_format_month_first(self) -> None:
        """Test parsing of MM/DD/YYYY format."""
        result = parse_date_input("01/15/2024")
        expected = datetime(2024, 1, 15)
        assert result == expected

    def test_invalid_date_format(self) -> None:
        """Test that invalid date formats raise ValueError."""
        with pytest.raises(ValueError, match="Unable to parse date"):
            parse_date_input("invalid-date")

    def test_invalid_date_values(self) -> None:
        """Test that invalid date values raise ValueError."""
        with pytest.raises(ValueError, match="Unable to parse date"):
            parse_date_input("2024-13-40")  # Invalid month and day


class TestValidateDateRange:
    """Test date range validation functionality."""

    def test_valid_date_range(self) -> None:
        """Test that valid date ranges pass validation."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        # Should not raise any exception
        validate_date_range(start, end)

    def test_none_dates(self) -> None:
        """Test that None dates are allowed."""
        # Should not raise any exception
        validate_date_range(None, None)
        validate_date_range(datetime(2024, 1, 1), None)
        validate_date_range(None, datetime(2024, 1, 1))

    def test_start_after_end(self) -> None:
        """Test that start date after end date raises ValueError."""
        start = datetime(2024, 12, 31)
        end = datetime(2024, 1, 1)
        with pytest.raises(ValueError, match="Start date.*must be before.*end date"):
            validate_date_range(start, end)

    def test_equal_dates(self) -> None:
        """Test that equal start and end dates raise ValueError."""
        date = datetime(2024, 1, 1)
        with pytest.raises(ValueError, match="Start date.*must be before.*end date"):
            validate_date_range(date, date)


class TestRelativeDateToAbsolute:
    """Test relative date conversion functionality."""

    def test_days_conversion(self) -> None:
        """Test conversion of days to absolute date."""
        result = relative_date_to_absolute(days=30)
        expected = datetime.now() - timedelta(days=30)
        # Allow small time differences due to execution time
        assert abs((result - expected).total_seconds()) < 1

    def test_weeks_conversion(self) -> None:
        """Test conversion of weeks to absolute date."""
        result = relative_date_to_absolute(weeks=4)
        expected = datetime.now() - timedelta(weeks=4)
        # Allow small time differences due to execution time
        assert abs((result - expected).total_seconds()) < 1

    def test_months_conversion(self) -> None:
        """Test conversion of months to absolute date."""
        result = relative_date_to_absolute(months=6)
        expected = datetime.now() - timedelta(days=6 * 30)  # Approximation
        # Allow small time differences due to execution time
        assert abs((result - expected).total_seconds()) < 1

    def test_no_parameters(self) -> None:
        """Test that providing no parameters raises ValueError."""
        with pytest.raises(ValueError, match="Must provide one of"):
            relative_date_to_absolute()

    def test_multiple_parameters(self) -> None:
        """Test that providing multiple parameters raises ValueError."""
        with pytest.raises(ValueError, match="Cannot combine multiple"):
            relative_date_to_absolute(days=30, weeks=4)

    def test_negative_days(self) -> None:
        """Test that negative days raise ValueError."""
        with pytest.raises(ValueError, match="Days must be a positive integer"):
            relative_date_to_absolute(days=-5)

    def test_zero_weeks(self) -> None:
        """Test that zero weeks raise ValueError."""
        with pytest.raises(ValueError, match="Weeks must be a positive integer"):
            relative_date_to_absolute(weeks=0)

    def test_negative_months(self) -> None:
        """Test that negative months raise ValueError."""
        with pytest.raises(ValueError, match="Months must be a positive integer"):
            relative_date_to_absolute(months=-3)


class TestValidateDateParameters:
    """Test comprehensive date parameter validation."""

    def test_valid_absolute_dates(self) -> None:
        """Test validation of valid absolute date parameters."""
        result = validate_date_parameters(
            created_after="2024-01-01",
            created_before="2024-12-31",
            updated_after="2024-06-01",
            updated_before="2024-06-30",
        )

        assert len(result) == 4
        assert result[0] == datetime(2024, 1, 1)  # created_after_dt
        assert result[1] == datetime(2024, 12, 31)  # created_before_dt
        assert result[2] == datetime(2024, 6, 1)  # updated_after_dt
        assert result[3] == datetime(2024, 6, 30)  # updated_before_dt

    def test_valid_relative_dates(self) -> None:
        """Test validation of valid relative date parameters."""
        result = validate_date_parameters(last_months=6)

        assert len(result) == 4
        assert result[0] is not None  # created_after_dt from relative date
        assert result[1] is None  # created_before_dt
        assert result[2] is None  # updated_after_dt
        assert result[3] is None  # updated_before_dt

    def test_conflicting_parameters(self) -> None:
        """Test that conflicting relative and absolute parameters raise ValueError."""
        with pytest.raises(ValueError, match="Cannot combine relative date options"):
            validate_date_parameters(created_after="2024-01-01", last_days=30)

    def test_invalid_created_after(self) -> None:
        """Test that invalid created_after date raises ValueError."""
        with pytest.raises(ValueError, match="Invalid --created-after date"):
            validate_date_parameters(created_after="invalid-date")

    def test_invalid_created_before(self) -> None:
        """Test that invalid created_before date raises ValueError."""
        with pytest.raises(ValueError, match="Invalid --created-before date"):
            validate_date_parameters(created_before="2024-13-40")

    def test_invalid_updated_after(self) -> None:
        """Test that invalid updated_after date raises ValueError."""
        with pytest.raises(ValueError, match="Invalid --updated-after date"):
            validate_date_parameters(updated_after="not-a-date")

    def test_invalid_updated_before(self) -> None:
        """Test that invalid updated_before date raises ValueError."""
        with pytest.raises(ValueError, match="Invalid --updated-before date"):
            validate_date_parameters(updated_before="2024/13/40")

    def test_invalid_date_range(self) -> None:
        """Test that invalid date ranges raise ValueError."""
        with pytest.raises(ValueError, match="Start date.*must be before.*end date"):
            validate_date_parameters(
                created_after="2024-12-31", created_before="2024-01-01"
            )

    def test_invalid_relative_date(self) -> None:
        """Test that invalid relative date parameters raise ValueError."""
        with pytest.raises(ValueError, match="Invalid relative date parameters"):
            validate_date_parameters(last_days=-5)


class TestFormatDatetimeForGithub:
    """Test GitHub date formatting functionality."""

    def test_format_datetime(self) -> None:
        """Test formatting datetime for GitHub API."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = format_datetime_for_github(dt)
        expected = "2024-01-15"
        assert result == expected

    def test_format_date_only(self) -> None:
        """Test formatting date-only datetime for GitHub API."""
        dt = datetime(2024, 12, 31, 0, 0, 0)
        result = format_datetime_for_github(dt)
        expected = "2024-12-31"
        assert result == expected

    def test_format_single_digit_month_day(self) -> None:
        """Test formatting dates with single-digit month and day."""
        dt = datetime(2024, 5, 7)
        result = format_datetime_for_github(dt)
        expected = "2024-05-07"
        assert result == expected
