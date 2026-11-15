"""
Human-readable diff generation utilities.

This module provides enhanced diff generation for accessibility remediation,
producing both unified diffs (for Git) and human-readable formats (for review).
"""

import difflib
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class DiffResult:
    """Result of a diff operation."""
    unified_diff: str
    readable_diff: str
    changes: int  # Number of lines changed
    context_lines: int = 3  # Number of context lines shown


def generate_unified_diff(
    original: str,
    modified: str,
    file_path: str = "index.html",
    context_lines: int = 3
) -> str:
    """
    Generate a unified diff between original and modified content.

    This is the standard Git-compatible diff format with configurable
    context lines for better readability.

    Args:
        original: The original content
        modified: The modified content
        file_path: Virtual file path for the diff header
        context_lines: Number of context lines to show (default: 3)

    Returns:
        Unified diff string
    """
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        n=context_lines,
        lineterm="",
    )

    return "".join(diff)


def generate_readable_diff(
    original: str,
    modified: str,
    file_path: str = "index.html",
    context_lines: int = 3
) -> str:
    """
    Generate a human-readable diff in a side-by-side format.

    This format is optimized for developer review, showing:
    - A clear header with file info
    - Unified diff format with proper context
    - Visual indicators for additions (+) and removals (-)

    Args:
        original: The original content
        modified: The modified content
        file_path: File path to display in header
        context_lines: Number of context lines to show

    Returns:
        Human-readable diff string
    """
    original_lines = original.splitlines()
    modified_lines = modified.splitlines()

    # Use SequenceMatcher for better change detection
    matcher = difflib.SequenceMatcher(None, original_lines, modified_lines)

    output = []
    output.append(f"File: {file_path}")
    output.append("-" * 40)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue

        if tag == 'delete':
            # Lines removed
            for i in range(max(0, i1 - context_lines), i2):
                output.append(f"  {original_lines[i]}")

        elif tag == 'insert':
            # Lines added
            for i in range(max(0, j1 - context_lines), j2):
                output.append(f"  {modified_lines[i]}")

        elif tag == 'replace':
            # Lines replaced
            for i in range(max(0, i1 - context_lines), i2):
                if i < len(original_lines):
                    output.append(f"  {original_lines[i]}")
            for j in range(max(0, j1 - context_lines), j2):
                if j < len(modified_lines):
                    output.append(f"  {modified_lines[j]}")

    return "\n".join(output)


def generate_formatted_diff(
    original: str,
    modified: str,
    file_path: str = "index.html",
    context_lines: int = 3
) -> DiffResult:
    """
    Generate both unified and readable diffs.

    Returns a DiffResult object containing both formats and metadata.

    Args:
        original: The original content
        modified: The modified content
        file_path: File path for diff headers
        context_lines: Number of context lines to show

    Returns:
        DiffResult with unified_diff, readable_diff, and metadata
    """
    original_lines = original.splitlines()
    modified_lines = modified.splitlines()

    unified = generate_unified_diff(original, modified, file_path, context_lines)
    readable = generate_readable_diff(original, modified, file_path, context_lines)

    # Count changes
    changes = len([l for l in unified.split('\n') if l.startswith('+') and not l.startswith('+++')])

    return DiffResult(
        unified_diff=unified.rstrip('\n'),
        readable_diff=readable,
        changes=changes,
        context_lines=context_lines,
    )


def format_diff_for_display(
    unified_diff: str,
    file_path: str = None
) -> str:
    """
    Format a unified diff for terminal display with syntax highlighting cues.

    This adds visual cues for common diff patterns:
    - Color indicators (can be styled by frontend)
    - Line count summaries
    - File context

    Args:
        unified_diff: The unified diff string
        file_path: Optional file path for display

    Returns:
        Formatted diff string ready for display
    """
    if not unified_diff:
        return "No changes"

    lines = unified_diff.split('\n')
    additions = sum(1 for l in lines if l.startswith('+') and not l.startswith('+++'))
    deletions = sum(1 for l in lines if l.startswith('-') and not l.startswith('---'))

    output = []
    output.append(f"```diff")
    output.extend(lines)
    output.append(f"```")
    output.append("")
    output.append(f"* Changes: +{additions}/-{deletions} lines modified*")

    return "\n".join(output)


def generate_side_by_side_diff(
    original: str,
    modified: str,
    context_lines: int = 3
) -> str:
    """
    Generate a side-by-side comparison of changes.

    This is useful for presenting remediation results where you can see
    the before and after clearly.

    Args:
        original: The original content
        modified: The modified content
        context_lines: Number of context lines to show

    Returns:
        Side-by-side diff string
    """
    original_lines = original.splitlines()
    modified_lines = modified.splitlines()

    matcher = difflib.SequenceMatcher(None, original_lines, modified_lines)

    output = []
    output.append("=" * 80)
    output.append("SIDE-BY-SIDE COMPARISON")
    output.append("=" * 80)
    output.append(f"{'ORIGINAL':^40} │ {'MODIFIED':^40}")
    output.append("-" * 81)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue

        # Get context before
        start_i = max(0, i1 - context_lines)
        start_j = max(0, j1 - context_lines)

        # Show the changes
        orig_block = original_lines[start_i:i1] if tag in ('delete', 'replace') else []
        mod_block = modified_lines[start_j:j1] if tag in ('insert', 'replace') else []

        # Determine max width
        for i in range(max(len(orig_block), len(mod_block))):
            orig_line = orig_block[i] if i < len(orig_block) else ""
            mod_line = mod_block[i] if i < len(mod_block) else ""

            if tag == 'insert':
                orig_line = ""
            elif tag == 'delete':
                mod_line = ""

            output.append(f"{orig_line:<40} │ {mod_line:<40}")

    return "\n".join(output)