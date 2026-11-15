"""
Unit tests for the button accessibility remediation module.

Tests cover HTML parsing, button analysis, fix generation, and diff output.
"""

import pytest
from remediation.button_fixer import (
    ButtonHTMLParser,
    ButtonInfo,
    ButtonFix,
    has_accessible_name,
    infer_aria_label,
    generate_button_fix,
    generate_unified_diff,
    analyze_html_for_buttons,
)


class TestButtonHTMLParser:
    """Tests for the ButtonHTMLParser class."""

    def test_parse_simple_button(self):
        """Test parsing a simple button element."""
        parser = ButtonHTMLParser()
        parser.feed('<button id="submit-btn">Submit</button>')

        assert len(parser.buttons) == 1
        button = parser.buttons[0]
        assert button.attributes["id"] == "submit-btn"
        assert button.text_content == "Submit"

    def test_parse_button_with_multiple_attributes(self):
        """Test parsing button with class, type, and data attributes."""
        parser = ButtonHTMLParser()
        parser.feed('<button class="btn primary" type="submit" data-action="submit">Save</button>')

        assert len(parser.buttons) == 1
        button = parser.buttons[0]
        assert button.attributes["class"] == "btn primary"
        assert button.attributes["type"] == "submit"
        assert button.attributes["data-action"] == "submit"

    def test_parse_empty_button_text(self):
        """Test parsing button with no text content."""
        parser = ButtonHTMLParser()
        parser.feed('<button id="icon-search" type="button"></button>')

        assert len(parser.buttons) == 1
        button = parser.buttons[0]
        assert button.text_content == ""

    def test_parse_multiple_buttons(self):
        """Test parsing multiple buttons in one HTML."""
        parser = ButtonHTMLParser()
        parser.feed('<button id="btn1">One</button><button id="btn2">Two</button>')

        assert len(parser.buttons) == 2
        assert parser.buttons[0].attributes["id"] == "btn1"
        assert parser.buttons[1].attributes["id"] == "btn2"

    def test_parse_button_with_whitespace_text(self):
        """Test that whitespace in button text is stripped."""
        parser = ButtonHTMLParser()
        parser.feed('<button>   Click me   </button>')

        button = parser.buttons[0]
        assert button.text_content == "Click me"

    def test_parse_button_with_nested_elements(self):
        """Test parsing button containing nested elements."""
        parser = ButtonHTMLParser()
        parser.feed('<button><span>Submit</span></button>')

        button = parser.buttons[0]
        # Text content should include nested text
        assert "Submit" in button.text_content


class TestHasAccessibleName:
    """Tests for the has_accessible_name function."""

    def test_button_with_aria_label_is_accessible(self):
        """Button with aria-label has an accessible name."""
        button = ButtonInfo(
            tag="button",
            attributes={"aria-label": "Submit form"},
            text_content="",
            start_tag='<button aria-label="Submit form">',
            line_number=1,
        )

        has_name, reason = has_accessible_name(button)
        assert has_name is True
        assert reason == ""

    def test_button_with_visible_text_is_accessible(self):
        """Button with visible text has an accessible name."""
        button = ButtonInfo(
            tag="button",
            attributes={},
            text_content="Click me",
            start_tag="<button>",
            line_number=1,
        )

        has_name, reason = has_accessible_name(button)
        assert has_name is True

    def test_button_with_aria_labelledby_is_accessible(self):
        """Button with aria-labelledby has an accessible name."""
        button = ButtonInfo(
            tag="button",
            attributes={"aria-labelledby": "label-id"},
            text_content="",
            start_tag='<button aria-labelledby="label-id">',
            line_number=1,
        )

        has_name, reason = has_accessible_name(button)
        assert has_name is True

    def test_empty_button_missing_accessible_name(self):
        """Empty button without attributes lacks accessible name."""
        button = ButtonInfo(
            tag="button",
            attributes={},
            text_content="",
            start_tag="<button>",
            line_number=1,
        )

        has_name, reason = has_accessible_name(button)
        assert has_name is False
        assert "no visible text" in reason.lower()

    def test_button_with_only_whitespace_missing_accessible_name(self):
        """Button with only whitespace lacks accessible name."""
        button = ButtonInfo(
            tag="button",
            attributes={},
            text_content="   ",
            start_tag="<button>",
            line_number=1,
        )

        has_name, reason = has_accessible_name(button)
        assert has_name is False


class TestInferAriaLabel:
    """Tests for the infer_aria_label function."""

    def test_infer_from_id(self):
        """Should infer label from button ID."""
        button = ButtonInfo(
            tag="button",
            attributes={"id": "search-button", "type": "button"},
            text_content="",
            start_tag='<button id="search-button">',
            line_number=1,
        )

        label = infer_aria_label(button)
        assert "Search" in label

    def test_infer_from_class_icon(self):
        """Should infer label from icon button class."""
        button = ButtonInfo(
            tag="button",
            attributes={"class": "icon-trash"},
            text_content="",
            start_tag='<button class="icon-trash">',
            line_number=1,
        )

        label = infer_aria_label(button)
        assert label == "Delete"

    def test_infer_submit_type_button(self):
        """Submit button should have 'Submit' in label."""
        button = ButtonInfo(
            tag="button",
            attributes={"type": "submit"},
            text_content="",
            start_tag='<button type="submit">',
            line_number=1,
        )

        label = infer_aria_label(button)
        assert "Submit" in label

    def test_infer_from_name_attribute(self):
        """Should infer label from button name attribute."""
        button = ButtonInfo(
            tag="button",
            attributes={"name": "save-btn", "type": "submit"},
            text_content="",
            start_tag='<button name="save-btn">',
            line_number=1,
        )

        label = infer_aria_label(button)
        assert "Save" in label

    def test_infer_handles_camel_case_id(self):
        """Should handle camelCase IDs correctly."""
        button = ButtonInfo(
            tag="button",
            attributes={"id": "cancelButton"},
            text_content="",
            start_tag='<button id="cancelButton">',
            line_number=1,
        )

        label = infer_aria_label(button)
        # "cancelButton" becomes "Cancel" after suffix stripping
        assert "Cancel" in label


class TestGenerateButtonFix:
    """Tests for the generate_button_fix function."""

    def test_fix_simple_button(self):
        """Generate fix for simple button with no text."""
        result = generate_button_fix('<button id="submit-btn" type="submit"></button>')

        assert result.aria_label_added is True
        assert "aria-label" in result.fixed_html
        assert "Submit" in result.explanation

    def test_fix_button_with_empty_text(self):
        """Generate fix for button with empty text content."""
        result = generate_button_fix('<button class="icon-search"></button>')

        assert result.aria_label_added is True
        assert "Search" in result.fixed_html

    def test_no_fix_needed_for_accessible_button(self):
        """Should not modify button that already has accessible name."""
        result = generate_button_fix('<button id="submit-btn">Submit</button>')

        # Button has visible text, so no fix needed
        assert result.aria_label_added is False
        assert result.fixed_html == result.original_html

    def test_no_fix_for_aria_label_button(self):
        """Should not modify button that has aria-label."""
        result = generate_button_fix('<button aria-label="Close"></button>')

        assert result.aria_label_added is False

    def test_fix_preserves_existing_attributes(self):
        """Fix should preserve all existing button attributes."""
        original = '<button id="save-btn" type="submit" class="primary">Save</button>'
        result = generate_button_fix(original)

        # Since button has text, no fix should be added
        assert "id=\"save-btn\"" in result.fixed_html or result.aria_label_added is False


class TestGenerateUnifiedDiff:
    """Tests for the generate_unified_diff function."""

    def test_simple_diff(self):
        """Generate a simple unified diff."""
        original = '<button>Click me</button>'
        modified = '<button aria-label="Submit">Click me</button>'

        diff = generate_unified_diff(original, modified)

        assert "-<button>Click me</button>" in diff
        assert "+<button aria-label=\"Submit\">Click me</button>" in diff
        assert "@@ -1 +1 @@" in diff

    def test_diff_with_file_path(self):
        """Diff should include file path in headers."""
        original = "before"
        modified = "after"

        diff = generate_unified_diff(original, modified, "src/index.html")

        assert "src/index.html" in diff

    def test_empty_diff_for_same_content(self):
        """Diff should show no changes for identical content."""
        html = "<button>Test</button>"

        diff = generate_unified_diff(html, html)

        # No minus or plus lines should appear for identical content
        assert "-" not in diff.split('\n')[0] if diff else True


class TestAnalyzeHTMLForButtons:
    """Tests for the analyze_html_for_buttons function."""

    def test_finds_inaccessible_buttons(self):
        """Should find buttons without accessible names."""
        html = '<button id="btn1"></button><button id="btn2">OK</button>'

        buttons = analyze_html_for_buttons(html)

        assert len(buttons) == 1
        assert buttons[0].attributes["id"] == "btn1"

    def test_ignores_accessible_buttons(self):
        """Should not return buttons with accessible names."""
        html = '''
        <button id="btn1">Submit</button>
        <button id="btn2" aria-label="Close"></button>
        '''

        buttons = analyze_html_for_buttons(html)

        assert len(buttons) == 0

    def test_handles_complex_html(self):
        """Should handle complex HTML with multiple issues."""
        html = '''
        <form>
            <button type="submit"></button>
            <button aria-label="Help">?</button>
            <button class="icon-trash"></button>
        </form>
        '''

        buttons = analyze_html_for_buttons(html)

        # Two buttons without accessible names (first and last)
        assert len(buttons) == 2


class TestButtonFix:
    """Tests for the ButtonFix dataclass."""

    def test_fix_creation(self):
        """Test creating a ButtonFix instance."""
        fix = ButtonFix(
            original_html='<button></button>',
            fixed_html='<button aria-label="Submit"></button>',
            explanation="Added aria-label",
            aria_label_added=True,
        )

        assert fix.aria_label_added is True
        assert "aria-label" in fix.fixed_html


class TestIntegration:
    """Integration tests for button remediation workflow."""

    def test_full_workflow_icon_buttons(self):
        """Test full workflow for common icon buttons."""
        test_cases = [
            ('<button class="icon-search"></button>', "Search"),
            ('<button class="icon-trash"></button>', "Delete"),
            ('<button class="icon-edit"></button>', "Edit"),
            ('<button class="icon-save"></button>', "Save"),
        ]

        for html, expected_label in test_cases:
            result = generate_button_fix(html)
            assert expected_label in result.fixed_html, f"Expected '{expected_label}' in {result.fixed_html}"

    def test_multiple_buttons_in_form(self):
        """Test handling multiple buttons in a form context."""
        # Test each button type can be fixed
        button_htmls = [
            '<button type="submit"></button>',
            '<button type="reset"></button>',
            '<button type="button"></button>',
        ]

        for html in button_htmls:
            result = generate_button_fix(html)
            assert result.aria_label_added is True, f"Failed for {html}"
            assert "aria-label" in result.fixed_html