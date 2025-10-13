"""Date parsing and validation utilities for GitHub issue collection."""

from datetime import datetime, timedelta

import typer


def parse_date_input(date_str: str) -> datetime:
    """Parse various date formats into datetime objects.

    Supports:
    - ISO dates: 2024-01-01, 2024-01-01T10:00:00Z
    - Common formats: January 1, 2024, Jan 1 2024

    Args:
        date_str: Date string to parse

    Returns:
        Parsed datetime object

    Raises:
        ValueError: If date format is not recognized
    """
    # Common date formats to try
    formats = [
        "%Y-%m-%d",  # 2024-01-01
        "%Y-%m-%dT%H:%M:%SZ",  # 2024-01-01T10:00:00Z
        "%Y-%m-%dT%H:%M:%S",  # 2024-01-01T10:00:00
        "%B %d, %Y",  # January 1, 2024
        "%b %d, %Y",  # Jan 1, 2024
        "%B %d %Y",  # January 1 2024
        "%b %d %Y",  # Jan 1 2024
        "%Y/%m/%d",  # 2024/01/01
        "%m/%d/%Y",  # 01/01/2024
        "%d/%m/%Y",  # 01/01/2024 (day first)
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # If none of the formats worked, raise a helpful error
    raise ValueError(
        f"Unable to parse date '{date_str}'. "
        f"Supported formats include: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SSZ, "
        f"'January 1, 2024', 'Jan 1 2024', MM/DD/YYYY"
    )


def validate_date_range(start: datetime | None, end: datetime | None) -> None:
    """Validate date range logic.

    Args:
        start: Start date (optional)
        end: End date (optional)

    Raises:
        ValueError: If date range is invalid
    """
    if start is None and end is None:
        return

    # Check if start is after end
    if start is not None and end is not None and start >= end:
        raise ValueError(
            f"Start date ({start.strftime('%Y-%m-%d')}) must be before "
            f"end date ({end.strftime('%Y-%m-%d')})"
        )

    # Check for future dates (optional warning)
    now = datetime.now()
    if start is not None and start > now:
        # Allow future dates but warn user
        typer.echo(
            f"Warning: Start date {start.strftime('%Y-%m-%d')} is in the future",
            err=True,
        )

    if end is not None and end > now:
        typer.echo(
            f"Warning: End date {end.strftime('%Y-%m-%d')} is in the future", err=True
        )


def relative_date_to_absolute(
    days: int | None = None, weeks: int | None = None, months: int | None = None
) -> datetime:
    """Convert relative dates to absolute dates.

    Args:
        days: Number of days ago (optional)
        weeks: Number of weeks ago (optional)
        months: Number of months ago (optional)

    Returns:
        Datetime object representing the calculated past date

    Raises:
        ValueError: If multiple relative date options provided or values are invalid
    """
    # Ensure only one relative date option is provided
    provided_options = sum(1 for x in [days, weeks, months] if x is not None)
    if provided_options == 0:
        raise ValueError("Must provide one of: days, weeks, or months")
    if provided_options > 1:
        raise ValueError("Cannot combine multiple relative date options")

    now = datetime.now()

    if days is not None:
        if days <= 0:
            raise ValueError("Days must be a positive integer")
        return now - timedelta(days=days)

    if weeks is not None:
        if weeks <= 0:
            raise ValueError("Weeks must be a positive integer")
        return now - timedelta(weeks=weeks)

    if months is not None:
        if months <= 0:
            raise ValueError("Months must be a positive integer")
        # Approximate months as 30 days each
        # This is imprecise but sufficient for GitHub API date filtering
        return now - timedelta(days=months * 30)

    # Should never reach here due to validation above
    raise ValueError("Invalid relative date parameters")


def validate_date_parameters(
    created_after: str | None = None,
    created_before: str | None = None,
    updated_after: str | None = None,
    updated_before: str | None = None,
    last_days: int | None = None,
    last_weeks: int | None = None,
    last_months: int | None = None,
) -> tuple[
    datetime | None,  # created_after_dt
    datetime | None,  # created_before_dt
    datetime | None,  # updated_after_dt
    datetime | None,  # updated_before_dt
]:
    """Validate and parse all date parameters.

    Args:
        created_after: Created after date string
        created_before: Created before date string
        updated_after: Updated after date string
        updated_before: Updated before date string
        last_days: Last N days (convenience option)
        last_weeks: Last N weeks (convenience option)
        last_months: Last N months (convenience option)

    Returns:
        Tuple of parsed datetime objects (created_after, created_before,
        updated_after, updated_before)

    Raises:
        ValueError: If parameters are invalid or conflicting
    """
    # Check for conflicting relative vs absolute date options
    relative_options = [last_days, last_weeks, last_months]
    absolute_options = [created_after, created_before, updated_after, updated_before]

    has_relative = any(x is not None for x in relative_options)
    has_absolute = any(x is not None for x in absolute_options)

    if has_relative and has_absolute:
        raise ValueError(
            "Cannot combine relative date options (--last-days/weeks/months) "
            "with absolute date options (--created-after/before, "
            "--updated-after/before)"
        )

    # Handle relative date options
    if has_relative:
        try:
            relative_start = relative_date_to_absolute(
                days=last_days, weeks=last_weeks, months=last_months
            )
            # For relative dates, set as created_after filter
            return relative_start, None, None, None
        except ValueError as e:
            raise ValueError(f"Invalid relative date parameters: {e}")

    # Handle absolute date options
    created_after_dt = None
    created_before_dt = None
    updated_after_dt = None
    updated_before_dt = None

    if created_after:
        try:
            created_after_dt = parse_date_input(created_after)
        except ValueError as e:
            raise ValueError(f"Invalid --created-after date: {e}")

    if created_before:
        try:
            created_before_dt = parse_date_input(created_before)
        except ValueError as e:
            raise ValueError(f"Invalid --created-before date: {e}")

    if updated_after:
        try:
            updated_after_dt = parse_date_input(updated_after)
        except ValueError as e:
            raise ValueError(f"Invalid --updated-after date: {e}")

    if updated_before:
        try:
            updated_before_dt = parse_date_input(updated_before)
        except ValueError as e:
            raise ValueError(f"Invalid --updated-before date: {e}")

    # Validate date ranges
    validate_date_range(created_after_dt, created_before_dt)
    validate_date_range(updated_after_dt, updated_before_dt)

    return created_after_dt, created_before_dt, updated_after_dt, updated_before_dt


def format_datetime_for_github(dt: datetime) -> str:
    """Format datetime for GitHub API search queries.

    Args:
        dt: Datetime to format

    Returns:
        ISO formatted date string for GitHub API
    """
    return dt.strftime("%Y-%m-%d")
