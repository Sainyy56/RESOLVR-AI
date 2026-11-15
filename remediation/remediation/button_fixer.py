"""
Button accessibility remediation module.

This module provides functionality to identify and fix buttons with missing
accessible names, ensuring WCAG 2.1 compliance for button elements.
"""

from html.parser import HTMLParser
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import re

from remediation.utils.diff_utils import (
    generate_unified_diff as _generate_enhanced_unified_diff,
    generate_readable_diff as _generate_readable_diff,
)


@dataclass
class ButtonInfo:
    """Information about a button element for remediation."""
    tag: str
    attributes: dict
    text_content: str
    start_tag: str
    line_number: int
    parent_form: Optional[str] = None
    siblings: List[str] = field(default_factory=list)


@dataclass
class ButtonFix:
    """Result of fixing a button accessibility issue."""
    original_html: str
    fixed_html: str
    explanation: str
    aria_label_added: bool = False


class ButtonHTMLParser(HTMLParser):
    """
    Custom HTML parser to extract button information.

    Uses the standard library html.parser module to parse HTML and identify
    button elements that may need accessible names.
    """

    def __init__(self):
        super().__init__()
        self.buttons: List[ButtonInfo] = []
        self._current_button: Optional[dict] = None
        self._button_text: str = ""
        self._in_button: bool = False
        self._button_start_pos: tuple = (0, 0)

    def handle_starttag(self, tag: str, attrs: list):
        """Handle opening tags."""
        tag_lower = tag.lower()

        if tag_lower == "button":
            attrs_dict = {k.lower(): v for k, v in attrs}
            self._current_button = {
                "attributes": attrs_dict,
                "text_content": "",
            }
            self._in_button = True
            self._button_text = ""
            self._button_start_pos = self.getpos()

    def handle_endtag(self, tag: str):
        """Handle closing tags."""
        tag_lower = tag.lower()

        if tag_lower == "button" and self._in_button and self._current_button:
            # Found a complete button
            attrs_dict = self._current_button["attributes"]

            button_info = ButtonInfo(
                tag=tag_lower,
                attributes=attrs_dict,
                text_content=self._button_text.strip(),
                start_tag=self._build_tag("button", attrs_dict),
                line_number=self._button_start_pos[0],
            )
            self.buttons.append(button_info)
            self._in_button = False
            self._current_button = None
            self._button_text = ""

    def handle_data(self, data: str):
        """Handle text content within elements."""
        if self._in_button and self._current_button:
            self._button_text += data

    def _build_tag(self, tag: str, attrs: dict) -> str:
        """Build an opening tag string from tag name and attributes dict."""
        if not attrs:
            return f"<{tag}>"

        # Sort attributes for consistent output
        attr_strs = []
        for key in sorted(attrs.keys()):
            value = attrs[key]
            attr_strs.append(f'{key}="{self._escape_attr(value)}"')

        return f"<{tag} {' '.join(attr_strs)}>"

    def _escape_attr(self, value: str) -> str:
        """Escape special characters in attribute values."""
        return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def has_accessible_name(button: ButtonInfo) -> Tuple[bool, str]:
    """
    Check if a button has an accessible name.

    According to WCAG, a button has an accessible name if it has:
    - Non-empty text content between the buttons tags
    - aria-label attribute
    - aria-labelledby attribute
    - An associated label element (though we can't always detect this)

    Returns:
        Tuple of (has_name, reason_if_missing)
    """
    # Check for aria-labelledby
    if button.attributes.get("aria-labelledby"):
        return True, ""

    # Check for aria-label
    if button.attributes.get("aria-label"):
        return True, ""

    # Check for visible text content
    if button.text_content.strip():
        return True, ""

    # Check if there's an alt attribute on nested img (which contributes to accessible name)
    # This is complex to detect in fragment parsing, so we'll skip it

    return False, "Button has no visible text, aria-label, or aria-labelledby"


def infer_aria_label(button: ButtonInfo) -> str:
    """
    Infer an appropriate aria-label for a button based on its context.

    Strategy:
    1. Look at the button's type attribute
    2. Look at the button's id, name, and class attributes
    3. Look at parent form context
    4. Generate a descriptive label
    """
    attrs = button.attributes

    # Get button type
    button_type = attrs.get("type", "button").lower()

    # Start with type-based default - but only for default buttons
    type_labels = {
        "submit": "Submit action",
        "button": "Button",
        "reset": "Reset form",
    }
    suggested = type_labels.get(button_type, "Button")

    # Try to get more context from attributes
    if "id" in attrs:
        # Extract meaningful part from id
        id_val = attrs["id"]
        readable = _id_to_readable(id_val)
        if readable and readable != "Button":
            suggested = readable

    if "name" in attrs:
        name_val = attrs["name"]
        readable = _id_to_readable(name_val)
        if readable and readable != "Button":
            suggested = readable

    if "class" in attrs:
        classes = attrs["class"].split()
        for cls in classes:
            # Map common icon button classes
            class_labels = {
                "icon-search": "Search",
                "icon-user": "User",
                "icon-menu": "Menu",
                "icon-close": "Close",
                "icon-back": "Back",
                "icon-home": "Home",
                "icon-profile": "Profile",
                "icon-settings": "Settings",
                "icon-trash": "Delete",
                "icon-edit": "Edit",
                "icon-save": "Save",
                "icon-cancel": "Cancel",
                "icon-add": "Add",
                "icon-remove": "Remove",
                "icon-filter": "Filter",
                "icon-sort": "Sort",
            }
            if cls in class_labels:
                suggested = class_labels[cls]
                break

    # For submit/reset buttons, add action context if not already there
    if button_type == "submit" and "submit" not in suggested.lower():
        suggested = f"{suggested} Submit"
    elif button_type == "reset" and "reset" not in suggested.lower():
        suggested = f"{suggested} Reset"

    # Capitalize first letter
    suggested = suggested[0].upper() + suggested[1:]

    return suggested


def _id_to_readable(id_str: str) -> str:
    """
    Convert an ID like 'search-button' or 'cancelBtn' to readable like 'Search Button' or 'Cancel'.
    """
    # Replace hyphens and underscores with spaces
    text = re.sub(r'[_-]+', ' ', id_str)

    # Handle camelCase/PascalCase
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

    # Remove common suffixes
    for suffix in ['-button', '-btn', '-icon', '-link', '-field']:
        if text.lower().endswith(suffix):
            text = text[:-len(suffix)]
            break

    # Capitalize each word
    words = text.split()
    words = [w.capitalize() for w in words if w]

    return ' '.join(words) if words else "Button"


def generate_button_fix(original_html: str, line_number: Optional[int] = None) -> ButtonFix:
    """
    Generate a fix for a button that lacks an accessible name.

    Uses the input HTML as-is and builds a corrected version by:
    1. Parsing to understand button structure
    2. Generating appropriate aria-label
    3. Building the fixed HTML with aria-label added

    Args:
        original_html: The HTML string containing the button
        line_number: Optional line number for context

    Returns:
        ButtonFix with the remediated HTML
    """
    parser = ButtonHTMLParser()

    try:
        parser.feed(original_html)
    except Exception:
        # If parsing fails, return as-is with note
        return ButtonFix(
            original_html=original_html,
            fixed_html=original_html,
            explanation="Could not parse HTML for remediation",
            aria_label_added=False,
        )

    if not parser.buttons:
        # No buttons found - return as-is with note
        return ButtonFix(
            original_html=original_html,
            fixed_html=original_html,
            explanation="No button element found in HTML fragment",
            aria_label_added=False,
        )

    # Get the first button (we typically process one finding at a time)
    button = parser.buttons[0]

    # Check if it already has an accessible name
    has_name, reason = has_accessible_name(button)
    if has_name:
        return ButtonFix(
            original_html=original_html,
            fixed_html=original_html,
            explanation="Button already has an accessible name",
            aria_label_added=False,
        )

    # Generate aria-label and apply fix
    aria_label = infer_aria_label(button)

    # Build the fixed HTML by adding aria-label to the start tag
    fixed_html = _add_aria_label_to_html(original_html, aria_label)

    return ButtonFix(
        original_html=original_html,
        fixed_html=fixed_html,
        explanation=f"Added aria-label=\"{aria_label}\" to provide accessible name for screen readers",
        aria_label_added=True,
    )


def _add_aria_label_to_html(html: str, aria_label: str) -> str:
    """
    Add an aria-label attribute to the first button in the HTML.

    This function handles the HTML directly by finding the button tag
    and inserting the aria-label attribute.
    """
    # Find the button opening tag
    button_match = re.search(r'<button\s+([^>]*)', html, re.IGNORECASE)
    if not button_match:
        # Button has no attributes, just add aria-label
        return re.sub(r'<button(?![a-zA-Z0-9_\-])', f'<button aria-label="{aria_label}"', html, count=1)

    # Get the attributes portion
    attrs_start = button_match.start(1)
    attrs_end = button_match.end()

    # Find where the > is
    tag_end_match = re.search(r'>', html[button_match.start():])
    if not tag_end_match:
        return html

    # Get the full tag start
    before = html[:button_match.end()]
    after = html[button_match.end():]

    # Find the position of >
    gt_pos = after.find('>')
    if gt_pos == -1:
        return html

    # Check if it's a self-closing tag (shouldn't be for button but handle it)
    if after.startswith('/>'):
        # Self-closing - add aria-label before />
        return before + f' aria-label="{aria_label}"' + after
    else:
        # Normal closing >
        return before + f' aria-label="{aria_label}">' + after[gt_pos+1:]


def _escape_attr(value: str) -> str:
    """Escape special characters in attribute values."""
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def generate_unified_diff(original_html: str, modified_html: str, file_path: str = "index.html") -> str:
    """
    Generate a unified diff between original and modified HTML.

    Uses enhanced diff generation with proper context lines for
    better readability in code reviews.

    Args:
        original_html: The original HTML
        modified_html: The modified HTML
        file_path: Virtual file path for the diff header

    Returns:
        Unified diff string with context
    """
    return _generate_enhanced_unified_diff(
        original_html,
        modified_html,
        file_path=file_path,
        context_lines=3
    )


def generate_readable_diff(original_html: str, modified_html: str, file_path: str = "index.html") -> str:
    """
    Generate a human-readable diff format.

    This provides an alternative representation optimized for
    developer review, showing before/after clearly.

    Args:
        original_html: The original HTML
        modified_html: The modified HTML
        file_path: File path for context

    Returns:
        Human-readable diff string
    """
    return _generate_readable_diff(
        original_html,
        modified_html,
        file_path=file_path,
        context_lines=3
    )


def analyze_html_for_buttons(html: str) -> List[ButtonInfo]:
    """
    Analyze HTML to find all buttons that may need accessible names.

    Args:
        html: HTML string to analyze

    Returns:
        List of ButtonInfo objects for buttons without accessible names
    """
    parser = ButtonHTMLParser()
    parser.feed(html)

    inaccessible_buttons = []
    for button in parser.buttons:
        has_name, _ = has_accessible_name(button)
        if not has_name:
            inaccessible_buttons.append(button)

    return inaccessible_buttons