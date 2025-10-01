"""
Reusable PydanticAI tools for technical support analysis.

This module contains tool functions that can be used across different agents
and experiments to enhance their analytical capabilities.
"""

import os
import re
import subprocess
import tempfile
import tarfile
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from .summary_retrieval import SummaryRetrievalClient


def search_evidence(query: str, limit: int = 2, threshold: float = 0.6) -> str:
    """Search for similar technical evidence in past support cases.

    Use this tool when you encounter specific technical evidence (error messages,
    log entries, diagnostic output) and want to find similar patterns from resolved
    cases. This helps identify precedent solutions and common root causes.

    Best results come from detailed technical descriptions. Include context like
    the failure mode, specific error messages, and what component is affected.

    Args:
        query: Technical evidence to search for - use detailed descriptions with context
        limit: Maximum number of similar cases to return (default: 2, max: 5)
        threshold: Minimum similarity score (default: 0.6, range: 0.0-1.0)

    Returns:
        Formatted string containing similar cases with their evidence, root causes, and fixes.
        Returns "No similar evidence found." if no matches above threshold.

    Examples of effective queries:
        "Pod stuck in ContainerCreating state FailedMount unable to mount volumes"
        "ImagePullBackOff ErrImagePull failed to pull and extract image dial tcp timeout"
        "DNS resolution failed timeout resolving external domain names"
        "PersistentVolumeClaim is pending no persistent volumes available to satisfy"
    """
    try:
        # Validate and constrain parameters
        limit = max(1, min(limit, 5))  # Constrain to 1-5 results
        threshold = max(0.0, min(threshold, 1.0))  # Constrain to 0.0-1.0

        if not query.strip():
            return "Error: Query is empty. Please provide technical evidence to search for."

        # Initialize client and search
        client = SummaryRetrievalClient()
        results = client.search_by_evidence(query, limit=limit, threshold=threshold)

        if not results:
            return "No similar evidence found. Try lowering the threshold or using different technical terms."

        # Format results for agent consumption
        return _format_evidence_search_results(results, query, threshold)

    except Exception as e:
        return f"Error searching evidence: {str(e)}"


def _format_evidence_search_results(
    results: List[Dict[str, Any]], query: str, threshold: float
) -> str:
    """Format evidence search results for agent consumption using XML format.

    Args:
        results: List of matching case dictionaries from database
        query: Original search query
        threshold: Similarity threshold used

    Returns:
        XML formatted string with case details for agent analysis
    """
    if not results:
        return "No similar evidence found."

    def parse_array_field(field_value):
        """Parse array field that might be returned as string from Snowflake."""
        if isinstance(field_value, str):
            # Try to parse as JSON array if it looks like one
            if field_value.strip().startswith("[") and field_value.strip().endswith(
                "]"
            ):
                import json

                try:
                    return json.loads(field_value)
                except json.JSONDecodeError:
                    return [field_value]  # Return as single item if can't parse
            else:
                return [field_value]  # Single string item
        elif isinstance(field_value, list):
            return field_value
        else:
            return []

    context_lines = [
        f'<similar_evidence_cases query="{query}" threshold="{threshold:.2f}" count="{len(results)}">'
    ]

    for i, case in enumerate(results, 1):
        # Basic case info
        issue_key = f"{case.get('ORG_NAME', 'unknown')}/{case.get('REPO_NAME', 'unknown')}#{case.get('ISSUE_NUMBER', 'unknown')}"
        similarity = case.get("evidence_similarity", case.get("EVIDENCE_SIMILARITY", 0))

        context_lines.append(
            f'<case id="{i}" issue="{issue_key}" similarity="{similarity:.3f}">'
        )

        # Evidence items (limit to top 3 for readability)
        evidence_items = parse_array_field(case.get("EVIDENCE", []))
        if evidence_items and any(e for e in evidence_items):
            context_lines.append("<evidence>")
            for evidence in evidence_items[:3]:  # Limit to top 3
                if evidence and str(evidence).strip():
                    context_lines.append(f"<item>{evidence}</item>")
            context_lines.append("</evidence>")

        # Root cause if available
        cause = case.get("CAUSE", "")
        if cause and str(cause).strip():
            context_lines.append(f"<root_cause>{cause}</root_cause>")

        # Fix actions if available
        fix_items = parse_array_field(case.get("FIX", []))
        if fix_items and any(f for f in fix_items):
            context_lines.append("<fix_applied>")
            for fix in fix_items[:2]:  # Limit to top 2 fix items
                if fix and str(fix).strip():
                    context_lines.append(f"<action>{fix}</action>")
            context_lines.append("</fix_applied>")

        context_lines.append("</case>")

    context_lines.append("</similar_evidence_cases>")

    return "\n".join(context_lines)


# Helm Debugging Tools


def list_tar_contents(tar_path: str) -> str:
    """List the contents of a tar archive without extracting it.

    Use this tool to explore the structure of KOTS releases or Helm chart archives
    before extracting specific files. This helps you understand what's available
    and plan your investigation strategy.

    Args:
        tar_path: Path to the tar/tar.gz archive to inspect

    Returns:
        Formatted list of files and directories in the archive.
        Returns error message if archive cannot be read.

    Examples of when to use:
        - Initial exploration of a KOTS release structure
        - Finding specific Helm charts (.tgz files) within a release
        - Locating HelmChart YAML manifests
        - Understanding the overall organization of files
    """
    try:
        tar_path = Path(tar_path)
        if not tar_path.exists():
            return f"Error: Archive not found at {tar_path}"

        if not tar_path.is_file():
            return f"Error: {tar_path} is not a file"

        # Open and list contents
        with tarfile.open(tar_path, "r:*") as tar:
            members = tar.getmembers()

            if not members:
                return "Archive is empty"

            # Format output for easy reading
            lines = [f"Archive contents ({len(members)} items):"]

            # Separate directories and files for better organization
            dirs = []
            files = []

            for member in members:
                if member.isdir():
                    dirs.append(f"📁 {member.name}/")
                elif member.isfile():
                    size_kb = member.size / 1024 if member.size > 1024 else member.size
                    size_unit = "KB" if member.size > 1024 else "B"
                    files.append(f"📄 {member.name} ({size_kb:.1f} {size_unit})")

            # Add directories first, then files
            if dirs:
                lines.append("\nDirectories:")
                lines.extend(sorted(dirs))

            if files:
                lines.append("\nFiles:")
                lines.extend(sorted(files))

            return "\n".join(lines)

    except tarfile.TarError as e:
        return f"Error reading tar archive: {str(e)}"
    except Exception as e:
        return f"Error listing archive contents: {str(e)}"


def extract_file(tar_path: str, file_path: str, dest_dir: Optional[str] = None) -> str:
    """Extract a specific file from a tar archive to a temporary location.

    Use this tool when you need to examine the contents of specific files within
    archives, such as Chart.yaml files from Helm charts or HelmChart manifests
    from KOTS releases.

    Args:
        tar_path: Path to the tar/tar.gz archive
        file_path: Path of the file within the archive to extract
        dest_dir: Optional destination directory (uses temp dir if not specified)

    Returns:
        Path to the extracted file, or error message if extraction fails.

    Examples of when to use:
        - Extract Chart.yaml from a Helm chart .tgz file
        - Extract specific HelmChart YAML manifests from KOTS releases
        - Get values.yaml files for analysis
        - Extract template files to understand rendering issues
    """
    try:
        tar_path = Path(tar_path)
        if not tar_path.exists():
            return f"Error: Archive not found at {tar_path}"

        # Use provided dest_dir or create temp directory
        if dest_dir:
            dest_path = Path(dest_dir)
            dest_path.mkdir(parents=True, exist_ok=True)
        else:
            dest_path = Path(tempfile.mkdtemp())

        # Extract the specific file
        with tarfile.open(tar_path, "r:*") as tar:
            try:
                # Find the member
                member = tar.getmember(file_path)

                # Extract to destination
                tar.extract(member, dest_path)

                # Return the full path to extracted file
                extracted_path = dest_path / file_path
                return str(extracted_path)

            except KeyError:
                return f"Error: File '{file_path}' not found in archive. Use list_tar_contents to see available files."

    except tarfile.TarError as e:
        return f"Error reading tar archive: {str(e)}"
    except Exception as e:
        return f"Error extracting file: {str(e)}"


def extract_all_files(tar_path: str, dest_dir: Optional[str] = None) -> str:
    """Extract all files from a tar archive to a directory for comprehensive analysis.

    Use this tool when you need to perform comprehensive analysis of a KOTS release
    containing multiple Helm charts. This extracts the entire archive structure,
    enabling systematic examination of all charts, manifests, and configuration files.

    Args:
        tar_path: Path to the tar/tar.gz archive
        dest_dir: Optional destination directory (uses temp dir if not specified)

    Returns:
        Path to the extraction directory containing all files, or error message if extraction fails.

    Examples of when to use:
        - Extract complete KOTS release for comprehensive Helm chart analysis
        - Get all Chart.yaml, values.yaml, and template files at once
        - Enable systematic analysis of multiple charts in a single operation
        - Support comprehensive investigation workflows requiring all files
    """
    try:
        tar_path = Path(tar_path)
        if not tar_path.exists():
            return f"Error: Archive not found at {tar_path}"

        # Use provided dest_dir or create temp directory
        if dest_dir:
            dest_path = Path(dest_dir)
            dest_path.mkdir(parents=True, exist_ok=True)
        else:
            dest_path = Path(tempfile.mkdtemp())

        # Extract all files
        with tarfile.open(tar_path, "r:*") as tar:
            # Get total file count for progress context
            members = tar.getmembers()
            file_count = len([m for m in members if m.isfile()])

            # Extract all files
            tar.extractall(dest_path)

            return f"Successfully extracted {file_count} files to: {dest_path}\nUse list_directory tool to explore the extracted structure."

    except tarfile.TarError as e:
        return f"Error reading tar archive: {str(e)}"
    except Exception as e:
        return f"Error extracting all files: {str(e)}"


def read_yaml_file(file_path: str) -> str:
    """Read and parse a YAML file, returning its structured content.

    Use this tool to examine YAML configuration files such as Chart.yaml metadata,
    HelmChart KOTS manifests, values.yaml files, and Kubernetes resource definitions.

    Args:
        file_path: Path to the YAML file to read

    Returns:
        Formatted YAML content with structure and key information highlighted.
        Returns error message if file cannot be read or parsed.

    Examples of when to use:
        - Analyze Chart.yaml to understand chart metadata and version
        - Examine HelmChart KOTS manifests for configuration issues
        - Review values.yaml files for templating problems
        - Inspect Kubernetes resource definitions
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            return f"Error: File not found at {file_path}"

        if not file_path.is_file():
            return f"Error: {file_path} is not a file"

        # Read and parse YAML
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Try to parse as YAML for validation
        try:
            parsed_data = yaml.safe_load(content)

            # Format output with helpful analysis
            lines = [f"YAML file: {file_path.name}"]
            lines.append("=" * 50)

            # Add some helpful metadata if it's a known type
            if isinstance(parsed_data, dict):
                # Detect file type and highlight key information
                if "apiVersion" in parsed_data and "kind" in parsed_data:
                    lines.append(
                        f"📋 Kubernetes Resource: {parsed_data.get('kind', 'Unknown')}"
                    )
                    lines.append(
                        f"🔖 API Version: {parsed_data.get('apiVersion', 'Unknown')}"
                    )

                elif "name" in parsed_data and "version" in parsed_data:
                    lines.append(f"📦 Chart: {parsed_data.get('name', 'Unknown')}")
                    lines.append(f"🏷️  Version: {parsed_data.get('version', 'Unknown')}")

                if "metadata" in parsed_data:
                    metadata = parsed_data["metadata"]
                    if isinstance(metadata, dict) and "name" in metadata:
                        lines.append(f"📛 Name: {metadata['name']}")

            lines.append("\n📄 Content:")
            lines.append(content)

            return "\n".join(lines)

        except yaml.YAMLError as e:
            return f"YAML parsing error in {file_path.name}: {str(e)}\n\nRaw content:\n{content}"

    except Exception as e:
        return f"Error reading file: {str(e)}"


def run_helm_command(command: str, chart_path: str = "") -> str:
    """Execute a helm CLI command safely with proper error handling.

    Use this tool to run helm commands for chart analysis, template rendering,
    and metadata extraction. Only safe, read-only commands are allowed.

    Args:
        command: Helm command to run ('show chart', 'show values', 'template', 'lint')
        chart_path: Path to chart/archive to operate on (required for most commands)

    Returns:
        Command output or error message with explanation.

    Allowed commands:
        - 'show chart': Get Chart.yaml metadata from a chart archive
        - 'show values': Get default values.yaml from a chart archive
        - 'template': Render templates (use carefully - may require values)
        - 'lint': Validate chart for issues
        - 'version': Get helm version information

    Examples of when to use:
        - Get Chart.yaml content: run_helm_command('show chart', '/path/to/chart.tgz')
        - Get default values: run_helm_command('show values', '/path/to/chart.tgz')
        - Validate chart: run_helm_command('lint', '/path/to/chart.tgz')
    """
    try:
        # Whitelist of allowed commands for security
        allowed_commands = ["show", "template", "lint", "version"]

        command_parts = command.strip().split()
        if not command_parts or command_parts[0] not in allowed_commands:
            return f"Error: Command '{command}' not allowed. Allowed: {', '.join(allowed_commands)}"

        # Build full command
        cmd_args = ["helm"] + command_parts

        # Add chart path if provided and needed
        if chart_path and command_parts[0] != "version":
            chart_path = Path(chart_path)
            if not chart_path.exists():
                return f"Error: Chart path not found: {chart_path}"
            cmd_args.append(str(chart_path))

        # Execute command with timeout
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout
            cwd=os.getcwd(),
        )

        # Format output
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                return f"✅ Command: helm {command}\n\n{output}"
            else:
                return "✅ Command completed successfully but produced no output"
        else:
            error_output = result.stderr.strip() or "Unknown error"
            return f"❌ Command failed: helm {command}\nError: {error_output}"

    except subprocess.TimeoutExpired:
        return f"❌ Command timed out: helm {command}"
    except FileNotFoundError:
        return "❌ helm command not found. Ensure helm is installed and in PATH."
    except Exception as e:
        return f"Error executing helm command: {str(e)}"


def read_file(file_path: str, max_lines: int = 100) -> str:
    """Read any text file and return its contents with helpful metadata.

    Use this tool to read any text-based file such as logs, configuration files,
    template files, scripts, or documentation. Handles various file types and
    provides intelligent formatting based on file extension.

    Args:
        file_path: Path to the file to read
        max_lines: Maximum number of lines to read (default: 100, max: 500)

    Returns:
        Formatted file content with metadata and type-specific highlighting.
        Returns error message if file cannot be read.

    Examples of when to use:
        - Read Helm template files (.yaml, .tpl, .txt)
        - Examine configuration files (.conf, .ini, .properties)
        - Check log files for error messages
        - Read documentation or README files
        - Examine shell scripts or other text files
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            return f"Error: File not found at {file_path}"

        if not file_path.is_file():
            return f"Error: {file_path} is not a file"

        # Constrain max_lines for safety
        max_lines = max(10, min(max_lines, 500))

        # Get file info
        file_size = file_path.stat().st_size
        file_ext = file_path.suffix.lower()

        # Try to read as text
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip())

            content = "\n".join(lines)
            total_lines = i + 1

            # Format output with file metadata
            output_lines = [f"📄 File: {file_path.name}"]
            output_lines.append("=" * 50)

            # Add file type and size info
            if file_ext:
                file_type = _get_file_type_description(file_ext)
                output_lines.append(f"📝 Type: {file_type}")

            size_str = (
                f"{file_size} bytes"
                if file_size < 1024
                else f"{file_size / 1024:.1f} KB"
            )
            output_lines.append(f"📏 Size: {size_str}")

            if total_lines > max_lines:
                output_lines.append(f"📊 Showing: {max_lines} of {total_lines}+ lines")
            else:
                output_lines.append(f"📊 Lines: {total_lines}")

            output_lines.append("\n📄 Content:")
            output_lines.append(content)

            # Add truncation notice if file was truncated
            if total_lines >= max_lines:
                output_lines.append(
                    f"\n⚠️  File truncated at {max_lines} lines. Use larger max_lines to see more."
                )

            return "\n".join(output_lines)

        except UnicodeDecodeError:
            # Try with different encodings
            for encoding in ["latin-1", "cp1252", "ascii"]:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read()[:10000]  # Limit to 10KB for binary-ish files
                    return f"📄 File: {file_path.name} (encoding: {encoding})\n{'=' * 50}\n{content}"
                except UnicodeDecodeError:
                    continue

            # If all encodings fail, it's likely a binary file
            return f"❌ Cannot read {file_path.name}: appears to be a binary file"

    except PermissionError:
        return f"❌ Permission denied reading file: {file_path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


def _get_file_type_description(file_ext: str) -> str:
    """Get a human-readable description of file type based on extension."""
    type_map = {
        ".yaml": "YAML configuration",
        ".yml": "YAML configuration",
        ".json": "JSON data",
        ".tpl": "Helm template",
        ".txt": "Text file",
        ".md": "Markdown documentation",
        ".sh": "Shell script",
        ".py": "Python script",
        ".js": "JavaScript",
        ".conf": "Configuration file",
        ".ini": "INI configuration",
        ".properties": "Properties file",
        ".log": "Log file",
        ".toml": "TOML configuration",
        ".xml": "XML document",
        ".html": "HTML document",
        ".css": "CSS stylesheet",
        ".sql": "SQL script",
        ".go": "Go source code",
        ".java": "Java source code",
        ".dockerfile": "Docker configuration",
    }
    return type_map.get(
        file_ext, f"{file_ext[1:].upper()} file" if file_ext else "Text file"
    )


def grep_file(
    file_path: str,
    pattern: str,
    context_lines: int = 2,
    max_matches: int = 20,
    use_regex: bool = False,
) -> str:
    """Search for a pattern within a text file and return matching lines with context.

    Use this tool to search for specific strings, error messages, configuration values,
    or patterns within files. Particularly useful after running helm template to find
    specific rendered values or when examining large configuration files.

    Args:
        file_path: Path to the file to search
        pattern: String or regex pattern to search for (case-insensitive)
        context_lines: Number of lines before/after each match to show (default: 2, max: 5)
        max_matches: Maximum number of matches to return (default: 20, max: 50)
        use_regex: Whether to use regex matching instead of substring search (default: False)

    Returns:
        Formatted search results showing matches with line numbers and context.
        Returns message if no matches found or if file cannot be read.

    Examples of when to use:
        - Search for error messages in helm template output
        - Find specific configuration values in rendered YAML
        - Look for environment variables or secrets in templates
        - Search for service names or ports in complex configurations
        - Find duplicate keys or conflicting values
        - Use regex to search for multiple terms: pattern="error|warning|fail" with use_regex=True
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            return f"Error: File not found at {file_path}"

        if not file_path.is_file():
            return f"Error: {file_path} is not a file"

        # Constrain parameters for safety
        context_lines = max(0, min(context_lines, 5))
        max_matches = max(1, min(max_matches, 50))

        # Read file and search for pattern
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            # Try alternative encodings
            for encoding in ["latin-1", "cp1252"]:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        lines = f.readlines()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                return f"❌ Cannot read {file_path.name}: encoding not supported"

        # Find matching lines
        matches = []

        # Compile regex pattern if needed
        if use_regex:
            try:
                regex_pattern = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                return f"❌ Invalid regex pattern '{pattern}': {str(e)}"
        else:
            pattern_lower = pattern.lower()

        for line_num, line in enumerate(lines, 1):
            # Check if line matches
            if use_regex:
                if regex_pattern.search(line):
                    matches.append(
                        {
                            "line_num": line_num,
                            "line": line.rstrip(),
                            "context_start": max(1, line_num - context_lines),
                            "context_end": min(len(lines), line_num + context_lines),
                        }
                    )
            else:
                if pattern_lower in line.lower():
                    matches.append(
                        {
                            "line_num": line_num,
                            "line": line.rstrip(),
                            "context_start": max(1, line_num - context_lines),
                            "context_end": min(len(lines), line_num + context_lines),
                        }
                    )

            # Stop if we hit max matches
            if len(matches) >= max_matches:
                break

        if not matches:
            return f"🔍 No matches found for '{pattern}' in {file_path.name}"

        # Format results
        result_lines = [f"🔍 Search results for '{pattern}' in {file_path.name}"]
        result_lines.append("=" * 60)
        result_lines.append(
            f"📊 Found {len(matches)} match{'es' if len(matches) > 1 else ''}"
        )

        if len(matches) >= max_matches:
            result_lines.append(f"⚠️  Showing first {max_matches} matches")

        result_lines.append("")

        # Show each match with context
        for i, match in enumerate(matches, 1):
            result_lines.append(f"Match {i} (line {match['line_num']}):")
            result_lines.append("-" * 40)

            # Show context lines
            for context_line_num in range(
                match["context_start"], match["context_end"] + 1
            ):
                if 1 <= context_line_num <= len(lines):
                    line_content = lines[context_line_num - 1].rstrip()

                    if context_line_num == match["line_num"]:
                        # Highlight the matching line
                        result_lines.append(
                            f">>> {context_line_num:4d}: {line_content}"
                        )
                    else:
                        # Regular context line
                        result_lines.append(
                            f"    {context_line_num:4d}: {line_content}"
                        )

            result_lines.append("")

        return "\n".join(result_lines)

    except PermissionError:
        return f"❌ Permission denied reading file: {file_path}"
    except Exception as e:
        return f"Error searching file: {str(e)}"


def grep_directory(
    directory_path: str,
    pattern: str,
    file_pattern: str = "*",
    max_files: int = 20,
    context_lines: int = 1,
    use_regex: bool = False,
    recursive: bool = True,
) -> str:
    """Search for a pattern across multiple files in a directory.

    Use this tool to search for patterns across multiple files, such as finding
    all occurrences of an error message in rendered templates, or searching for
    configuration values across an entire Helm chart.

    Args:
        directory_path: Path to directory to search
        pattern: String or regex pattern to search for (case-insensitive)
        file_pattern: Glob pattern for files to search (default: "*" for all files)
        max_files: Maximum number of files to search (default: 20, max: 50)
        context_lines: Lines of context around each match (default: 1, max: 3)
        use_regex: Whether to use regex matching instead of substring search (default: False)
        recursive: Whether to search subdirectories recursively (default: True)

    Returns:
        Formatted search results grouped by file.
        Returns message if no matches found or directory cannot be accessed.

    Examples of when to use:
        - Search for error patterns across all rendered templates
        - Find all uses of a specific variable across Helm templates
        - Look for security issues across multiple configuration files
        - Find duplicate configurations across different files
        - Use regex to find multiple patterns: pattern="error|warning|fatal" with use_regex=True
    """
    try:
        directory_path = Path(directory_path)
        if not directory_path.exists():
            return f"Error: Directory not found: {directory_path}"

        if not directory_path.is_dir():
            return f"Error: {directory_path} is not a directory"

        # Constrain parameters
        max_files = max(1, min(max_files, 50))
        context_lines = max(0, min(context_lines, 3))

        # Find files matching the pattern
        try:
            # Use rglob for recursive search, glob for non-recursive
            if recursive:
                if file_pattern == "*":
                    # For "*" pattern with recursive, use "**/*" to get all files
                    files = list(directory_path.rglob("*"))
                else:
                    # For specific patterns, rglob already handles recursion
                    files = list(directory_path.rglob(file_pattern))
            else:
                files = list(directory_path.glob(file_pattern))

            # Filter to only text files and limit count
            text_files = []
            for f in files:
                if (
                    f.is_file() and f.stat().st_size < 10 * 1024 * 1024
                ):  # Skip files > 10MB
                    text_files.append(f)
                    if len(text_files) >= max_files:
                        break

        except Exception as e:
            return f"Error listing files: {str(e)}"

        if not text_files:
            mode = "recursively" if recursive else "in directory"
            return f"No files found matching pattern '{file_pattern}' {mode} {directory_path}"

        # Compile regex pattern if needed
        if use_regex:
            try:
                regex_pattern = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                return f"❌ Invalid regex pattern '{pattern}': {str(e)}"
        else:
            pattern_lower = pattern.lower()

        # Search each file
        all_matches = {}

        for file_path in text_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                file_matches = []
                for line_num, line in enumerate(lines, 1):
                    # Check if line matches
                    match_found = False
                    if use_regex:
                        if regex_pattern.search(line):
                            match_found = True
                    else:
                        if pattern_lower in line.lower():
                            match_found = True

                    if match_found:
                        file_matches.append(
                            {
                                "line_num": line_num,
                                "line": line.rstrip(),
                                "context_start": max(1, line_num - context_lines),
                                "context_end": min(
                                    len(lines), line_num + context_lines
                                ),
                            }
                        )

                if file_matches:
                    all_matches[file_path.name] = {
                        "path": file_path,
                        "matches": file_matches,
                        "lines": lines,
                    }

            except (UnicodeDecodeError, PermissionError):
                continue  # Skip files we can't read

        if not all_matches:
            return f"🔍 No matches found for '{pattern}' in {len(text_files)} files"

        # Format results
        result_lines = [f"🔍 Directory search results for '{pattern}'"]
        result_lines.append("=" * 60)
        result_lines.append(
            f"📊 Found matches in {len(all_matches)} of {len(text_files)} files"
        )
        result_lines.append("")

        for filename, file_data in all_matches.items():
            matches = file_data["matches"]
            lines = file_data["lines"]

            result_lines.append(
                f"📄 {filename} ({len(matches)} match{'es' if len(matches) > 1 else ''})"
            )
            result_lines.append("-" * 40)

            for match in matches[:5]:  # Limit to 5 matches per file
                # Show minimal context for directory searches
                for context_line_num in range(
                    match["context_start"], match["context_end"] + 1
                ):
                    if 1 <= context_line_num <= len(lines):
                        line_content = lines[context_line_num - 1].rstrip()

                        if context_line_num == match["line_num"]:
                            result_lines.append(
                                f">>> {context_line_num:4d}: {line_content}"
                            )
                        else:
                            result_lines.append(
                                f"    {context_line_num:4d}: {line_content}"
                            )

            if len(matches) > 5:
                result_lines.append(f"    ... and {len(matches) - 5} more matches")

            result_lines.append("")

        return "\n".join(result_lines)

    except Exception as e:
        return f"Error searching directory: {str(e)}"


def list_directory(directory_path: str, max_depth: int = 2) -> str:
    """List directory contents with structure, useful for exploring extracted files.

    Use this tool to explore directory structures after extracting files,
    understanding the layout of Helm charts, or navigating KOTS release contents.

    Args:
        directory_path: Path to directory to explore
        max_depth: Maximum depth to traverse (default: 2, max: 5)

    Returns:
        Formatted directory tree showing files and subdirectories.

    Examples of when to use:
        - Explore extracted KOTS release structure
        - Navigate Helm chart directory layout
        - Find specific files within complex directory structures
        - Understand template organization in charts
    """
    try:
        directory_path = Path(directory_path)
        if not directory_path.exists():
            return f"Error: Directory not found: {directory_path}"

        if not directory_path.is_dir():
            return f"Error: {directory_path} is not a directory"

        # Constrain depth for safety
        max_depth = max(1, min(max_depth, 5))

        lines = [f"📁 Directory: {directory_path}"]
        lines.append("=" * 50)

        def _explore_directory(path: Path, current_depth: int = 0, prefix: str = ""):
            if current_depth >= max_depth:
                return

            items = []
            try:
                items = sorted(
                    path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())
                )
            except PermissionError:
                lines.append(f"{prefix}❌ Permission denied")
                return

            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                current_prefix = "└── " if is_last else "├── "
                next_prefix = prefix + ("    " if is_last else "│   ")

                if item.is_dir():
                    lines.append(f"{prefix}{current_prefix}📁 {item.name}/")
                    _explore_directory(item, current_depth + 1, next_prefix)
                else:
                    # Show file size for regular files
                    try:
                        size = item.stat().st_size
                        size_str = (
                            f" ({size} bytes)"
                            if size < 1024
                            else f" ({size / 1024:.1f} KB)"
                        )
                    except:
                        size_str = ""
                    lines.append(f"{prefix}{current_prefix}📄 {item.name}{size_str}")

        _explore_directory(directory_path)

        return "\n".join(lines)

    except Exception as e:
        return f"Error exploring directory: {str(e)}"
