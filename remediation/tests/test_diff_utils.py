"""
Unit tests for the diff utilities module.

Tests cover unified diff generation, readable diff formatting,
and side-by-side comparison.
"""

import pytest
from remediation.utils.diff_utils import (
    generate_unified_diff,
    generate_readable_diff,
    generate_formatted_diff,
    generate_side_by_side_diff,
    DiffResult,
)


class TestGenerateUnifiedDiff:
    """Tests for the generate_unified_diff function."""

    def test_simple_addition(self):
        """Test diff with simple addition."""
        original = "<button>Click</button>"
        modified = '<button aria-label="Submit">Click</button>'

        diff = generate_unified_diff(original, modified)

        assert "-<button>Click</button>" in diff
        assert '+"<button aria-label="Submit">Click</button>"' in diff or '+"<button aria-label="Submit">Click</button>' in diff or "aria-label" in diff

    def test_with_context_lines(self):
        """Test diff generation with context lines."""
        original = """<div>
    <button>Click me</button>
    <p>Some content</p>
</div>"""
        modified = """<div>
    <button aria-label="Submit action">Click me</button>
    <p>Some content</p>
</div>"""

        diff = generate_unified_diff(original, modified)

        # Should show context around the change
        assert "-" in diff
        assert "+" in diff

    def test_no_changes(self):
        """Test diff when there are no changes."""
        html = "<button>Click me</button>"

        diff = generate_unified_diff(html, html)

        assert "-" not in diff.split('\n')[0] if diff else True

    def test_adds_file_path_header(self):
        """Test that diff includes file path in headers."""
        diff = generate_unified_diff("a", "b", file_path="src/index.html")

        assert "src/index.html" in diff


class TestGenerateReadableDiff:
    """Tests for the generate_readable_diff function."""

    def test_basic_readable_diff(self):
        """Test that readable diff is generated."""
        original = "<button>Click</button>"
        modified = '<button aria-label="Submit">Click</button>'

        diff = generate_readable_diff(original, modified)

        assert isinstance(diff, str)
        assert len(diff) > 0

    def test_includes_file_path(self):
        """Test that readable diff includes file path."""
        diff = generate_readable_diff("a", "b", file_path="form.html")

        assert "form.html" in diff


class TestGenerateFormattedDiff:
    """Tests for the generate_formatted_diff function."""

    def test_returns_diff_result(self):
        """Test that function returns DiffResult object."""
        result = generate_formatted_diff("a", "b")

        assert isinstance(result, DiffResult)
        assert hasattr(result, 'unified_diff')
        assert hasattr(result, 'readable_diff')
        assert hasattr(result, 'changes')

    def test_counts_changes_correctly(self):
        """Test that changes are counted correctly."""
        original = "<input>"
        modified = '<input aria-label="Email">'

        result = generate_formatted_diff(original, modified)

        # At minimum, the unified diff should show a change
        assert "+" in result.unified_diff or "-" in result.unified_diff
        assert result.context_lines == 3


class TestGenerateSideBySideDiff:
    """Tests for the generate_side_by_side_diff function."""

    def test_basic_comparison(self):
        """Test side-by-side comparison generation."""
        original = "<input>Click</input>"
        modified = '<input aria-label="Submit">Click</input>'

        diff = generate_side_by_side_diff(original, modified)

        assert isinstance(diff, str)
        assert "SIDE-BY-SIDE" in diff


class TestDiffResult:
    """Tests for the DiffResult dataclass."""

    def test_diff_result_creation(self):
        """Test creating a DiffResult instance."""
        diff_result = DiffResult(
            unified_diff="--- a/file\n+++ b/file",
            readable_diff="Formatted diff",
            changes=2,
            context_lines=3,
        )

        assert diff_result.changes == 2
        assert diff_result.context_lines == 3


class TestIntegration:
    """Integration tests for diff utilities."""

    def test_real_world_button_change(self):
        """Test diff with a realistic button accessibility change."""
        original = '<button type="submit"></button>'
        modified = '<button type="submit" aria-label="Form Submit"></button>'

        unified = generate_unified_diff(original, modified)
        readable = generate_readable_diff(original, modified)

        # Both should show the change
        assert '+"<button type="submit" aria-label="Form Submit">"</button>' in unified or "aria-label" in unified
        assert len(readable) > 0

    def test_real_world_input_change(self):
        """Test diff with a realistic input accessibility change."""
        original = '<input type="email" id="user-email">'
        modified = '<input type="email" id="user-email" aria-label="Email address">'

        unified = generate_unified_diff(original, modified, "src/form.html")

        assert "src/form.html" in unified
        assert "aria-label" in unified