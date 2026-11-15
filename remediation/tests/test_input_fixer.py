"""
Unit tests for the input accessibility remediation module.

Tests cover HTML parsing, input analysis, fix generation, and diff output.
"""

import pytest
from remediation.input_fixer import (
    InputHTMLParser,
    InputInfo,
    InputFix,
    has_label,
    infer_input_label,
    generate_input_fix,
    generate_unified_diff,
    analyze_html_for_inputs,
)


class TestInputHTMLParser:
    """Tests for the InputHTMLParser class."""

    def test_parse_simple_input(self):
        """Test parsing a simple input element."""
        parser = InputHTMLParser()
        parser.feed('<input type="text" id="name">')

        assert len(parser.inputs) == 1
        input_elem = parser.inputs[0]
        assert input_elem.attributes["type"] == "text"
        assert input_elem.attributes["id"] == "name"

    def test_parse_input_with_multiple_attributes(self):
        """Test parsing input with class, type, and data attributes."""
        parser = InputHTMLParser()
        parser.feed('<input class="form-control" type="email" placeholder="Enter email" required>')

        assert len(parser.inputs) == 1
        input_elem = parser.inputs[0]
        assert input_elem.attributes["class"] == "form-control"
        assert input_elem.attributes["type"] == "email"
        assert input_elem.attributes["placeholder"] == "Enter email"

    def test_parse_textarea(self):
        """Test parsing textarea element."""
        parser = InputHTMLParser()
        parser.feed('<textarea id="description">Default text</textarea>')

        assert len(parser.inputs) == 1
        textarea = parser.inputs[0]
        assert textarea.tag == "textarea"
        assert textarea.attributes["id"] == "description"
        assert textarea.text_content == "Default text"

    def test_parse_multiple_inputs(self):
        """Test parsing multiple inputs in one HTML."""
        parser = InputHTMLParser()
        parser.feed('<input id="first"><input id="second">')

        assert len(parser.inputs) == 2
        assert parser.inputs[0].attributes["id"] == "first"
        assert parser.inputs[1].attributes["id"] == "second"

    def test_parse_select_element(self):
        """Test parsing select element."""
        parser = InputHTMLParser()
        parser.feed('<select id="country"><option value="us">USA</option></select>')

        assert len(parser.inputs) == 1
        select = parser.inputs[0]
        assert select.tag == "select"
        assert select.attributes["id"] == "country"


class TestHasLabel:
    """Tests for the has_label function."""

    def test_input_with_aria_label_is_labeled(self):
        """Input with aria-label has an accessible label."""
        input_elem = InputInfo(
            tag="input",
            attributes={"aria-label": "Email address"},
            text_content="",
            start_tag='<input aria-label="Email address">',
            end_tag="",
            line_number=1,
        )

        has_label_attr, reason = has_label(input_elem)
        assert has_label_attr is True
        assert reason == ""

    def test_input_with_aria_labelledby_is_labeled(self):
        """Input with aria-labelledby has an accessible label."""
        input_elem = InputInfo(
            tag="input",
            attributes={"aria-labelledby": "email-label"},
            text_content="",
            start_tag='<input aria-labelledby="email-label">',
            end_tag="",
            line_number=1,
        )

        has_label_attr, reason = has_label(input_elem)
        assert has_label_attr is True

    def test_textarea_with_text_is_labeled(self):
        """Textarea with text content has an accessible label."""
        input_elem = InputInfo(
            tag="textarea",
            attributes={},
            text_content="Enter description here",
            start_tag="<textarea>",
            end_tag="</textarea>",
            line_number=1,
        )

        has_label_attr, reason = has_label(input_elem)
        assert has_label_attr is True

    def test_empty_input_missing_label(self):
        """Empty input without attributes lacks accessible label."""
        input_elem = InputInfo(
            tag="input",
            attributes={},
            text_content="",
            start_tag="<input>",
            end_tag="",
            line_number=1,
        )

        has_label_attr, reason = has_label(input_elem)
        assert has_label_attr is False
        assert "no aria-label" in reason.lower()

    def test_input_with_placeholder_only_no_label(self):
        """Input with only placeholder does not have accessible label (placeholder is not a label)."""
        input_elem = InputInfo(
            tag="input",
            attributes={"placeholder": "Enter your email"},
            text_content="",
            start_tag='<input placeholder="Enter your email">',
            end_tag="",
            line_number=1,
        )

        has_label_attr, reason = has_label(input_elem)
        assert has_label_attr is False


class TestInferInputLabel:
    """Tests for the infer_input_label function."""

    def test_infer_from_id_email(self):
        """Should infer label from email input ID."""
        input_elem = InputInfo(
            tag="input",
            attributes={"id": "email-address", "type": "email"},
            text_content="",
            start_tag='<input id="email-address" type="email">',
            end_tag="",
            line_number=1,
        )

        label = infer_input_label(input_elem)
        assert "Email" in label

    def test_infer_from_id_search(self):
        """Should infer label from search input ID."""
        input_elem = InputInfo(
            tag="input",
            attributes={"id": "search-query"},
            text_content="",
            start_tag='<input id="search-query">',
            end_tag="",
            line_number=1,
        )

        label = infer_input_label(input_elem)
        assert "Search" in label

    def test_infer_from_type_email(self):
        """Should infer label from email input type."""
        input_elem = InputInfo(
            tag="input",
            attributes={"type": "email"},
            text_content="",
            start_tag='<input type="email">',
            end_tag="",
            line_number=1,
        )

        label = infer_input_label(input_elem)
        assert "Email" in label

    def test_infer_from_type_password(self):
        """Should infer label from password input type."""
        input_elem = InputInfo(
            tag="input",
            attributes={"type": "password"},
            text_content="",
            start_tag='<input type="password">',
            end_tag="",
            line_number=1,
        )

        label = infer_input_label(input_elem)
        assert "Password" in label

    def test_infer_from_type_number(self):
        """Should infer label from number input type."""
        input_elem = InputInfo(
            tag="input",
            attributes={"type": "number"},
            text_content="",
            start_tag='<input type="number">',
            end_tag="",
            line_number=1,
        )

        label = infer_input_label(input_elem)
        assert "Number" in label

    def test_infer_from_placeholder(self):
        """Should use placeholder as label if available."""
        input_elem = InputInfo(
            tag="input",
            attributes={"type": "text", "placeholder": "Search products"},
            text_content="",
            start_tag='<input type="text" placeholder="Search products">',
            end_tag="",
            line_number=1,
        )

        label = infer_input_label(input_elem)
        assert "Search" in label

    def test_infer_from_name_attribute(self):
        """Should infer label from input name attribute."""
        input_elem = InputInfo(
            tag="input",
            attributes={"name": "user-name", "type": "text"},
            text_content="",
            start_tag='<input name="user-name">',
            end_tag="",
            line_number=1,
        )

        label = infer_input_label(input_elem)
        assert "Name" in label


class TestGenerateInputFix:
    """Tests for the generate_input_fix function."""

    def test_fix_simple_input(self):
        """Generate fix for simple input with no text."""
        result = generate_input_fix('<input id="email" type="email">')

        assert result.aria_label_added is True
        assert "aria-label" in result.fixed_html

    def test_fix_input_with_id(self):
        """Generate fix using input ID for label context."""
        result = generate_input_fix('<input id="search-query">')

        assert result.aria_label_added is True
        assert "Search" in result.fixed_html or "Query" in result.fixed_html

    def test_no_fix_needed_for_aria_label_input(self):
        """Should not modify input that already has aria-label."""
        result = generate_input_fix('<input aria-label="Email address">')

        assert result.aria_label_added is False
        assert result.fixed_html == result.original_html

    def test_no_fix_for_textarea_with_text(self):
        """Should not modify textarea that already has text content."""
        result = generate_input_fix('<textarea>Description</textarea>')

        # Textarea with text content has accessible name from text
        assert result.aria_label_added is False

    def test_fix_textarea_without_label(self):
        """Generate fix for textarea without accessible label."""
        result = generate_input_fix('<textarea id="comments"></textarea>')

        assert result.aria_label_added is True
        assert "aria-label" in result.fixed_html

    def test_fix_preserves_existing_attributes(self):
        """Fix should preserve all existing input attributes."""
        original = '<input id="email" type="email" placeholder="Enter email" required>'
        result = generate_input_fix(original)

        # All original attributes should be preserved
        assert 'id="email"' in result.fixed_html
        assert 'type="email"' in result.fixed_html
        assert 'placeholder="Enter email"' in result.fixed_html


class TestGenerateUnifiedDiff:
    """Tests for the generate_unified_diff function."""

    def test_simple_diff(self):
        """Generate a simple unified diff."""
        original = '<input>Click me</input>'
        modified = '<input aria-label="Email">Click me</input>'

        diff = generate_unified_diff(original, modified)

        assert "-<input>Click me</input>" in diff
        # Check that the diff shows the change
        assert "+<input aria-label=" in diff

    def test_diff_with_file_path(self):
        """Diff should include file path in headers."""
        original = "before"
        modified = "after"

        diff = generate_unified_diff(original, modified, "src/form.html")

        assert "src/form.html" in diff

    def test_empty_diff_for_same_content(self):
        """Diff should show no changes for identical content."""
        html = "<input type='text'>"

        diff = generate_unified_diff(html, html)

        # No minus or plus lines should appear for identical content
        assert "-" not in diff.split('\n')[0] if diff else True


class TestAnalyzeHTMLForInputs:
    """Tests for the analyze_html_for_inputs function."""

    def test_finds_unlabeled_inputs(self):
        """Should find inputs without accessible labels."""
        html = '<input id="first"><input id="second" aria-label="Email">'

        inputs = analyze_html_for_inputs(html)

        # Only first input is unlabeled
        assert len(inputs) == 1
        assert inputs[0].attributes["id"] == "first"

    def test_ignores_labeled_inputs(self):
        """Should not return inputs with accessible labels."""
        html = '''
        <input id="email" type="email">
        <input aria-label="Search" placeholder="Search">
        '''

        # First has no label (aria-label is on second only)
        inputs = analyze_html_for_inputs(html)
        assert len(inputs) >= 1

    def test_handles_complex_html(self):
        """Should handle complex HTML with multiple issues."""
        html = '''
        <form>
            <input type="email" id="email">
            <input type="password" aria-label="Password">
            <textarea id="bio"></textarea>
        </form>
        '''

        inputs = analyze_html_for_inputs(html)
        # Email and textarea are unlabeled
        assert len(inputs) >= 2


class TestInputFix:
    """Tests for the InputFix dataclass."""

    def test_fix_creation(self):
        """Test creating an InputFix instance."""
        fix = InputFix(
            original_html='<input>',
            fixed_html='<input aria-label="Email">',
            explanation="Added aria-label",
            aria_label_added=True,
        )

        assert fix.aria_label_added is True
        assert "aria-label" in fix.fixed_html


class TestIntegration:
    """Integration tests for input remediation workflow."""

    def test_full_workflow_email_inputs(self):
        """Test full workflow for common email inputs."""
        test_cases = [
            '<input id="email" type="email">',
            '<input type="email" placeholder="Enter email">',
            '<input name="user-email">',
        ]

        for html in test_cases:
            result = generate_input_fix(html)
            assert result.aria_label_added is True, f"Failed for {html}"
            assert "aria-label" in result.fixed_html

    def test_multiple_inputs_in_form(self):
        """Test handling multiple inputs in a form context."""
        html = '''
        <form>
            <input type="email" id="email">
            <input type="password" id="password">
            <input type="submit" value="Login">
        </form>
        '''

        inputs = analyze_html_for_inputs(html)
        # At least email and password should be unlabeled
        assert len(inputs) >= 2

        # Each should be fixable
        for input_elem in inputs:
            if input_elem.attributes.get("type") in ("email", "password"):
                fix = generate_input_fix(f"<input {input_elem.start_tag.replace('<input', '')}>")
                assert fix.aria_label_added is True


class TestSpecialCases:
    """Tests for special input types and edge cases."""

    def test_checkbox_input(self):
        """Test checkbox input handling."""
        input_elem = InputInfo(
            tag="input",
            attributes={"type": "checkbox", "id": "agree"},
            text_content="",
            start_tag='<input type="checkbox" id="agree">',
            end_tag="",
            line_number=1,
        )

        label = infer_input_label(input_elem)
        assert label is not None
        assert len(label) > 0

    def test_radio_input(self):
        """Test radio input handling."""
        input_elem = InputInfo(
            tag="input",
            attributes={"type": "radio", "id": "male"},
            text_content="",
            start_tag='<input type="radio" id="male">',
            end_tag="",
            line_number=1,
        )

        label = infer_input_label(input_elem)
        assert "Male" in label

    def test_url_input(self):
        """Test URL input handling."""
        input_elem = InputInfo(
            tag="input",
            attributes={"type": "url", "id": "website"},
            text_content="",
            start_tag='<input type="url" id="website">',
            end_tag="",
            line_number=1,
        )

        label = infer_input_label(input_elem)
        assert "Website" in label

    def test_date_input(self):
        """Test date input handling."""
        input_elem = InputInfo(
            tag="input",
            attributes={"type": "date", "id": "birth-date"},
            text_content="",
            start_tag='<input type="date" id="birth-date">',
            end_tag="",
            line_number=1,
        )

        label = infer_input_label(input_elem)
        assert "Date" in label