"""
Form input accessibility remediation module.

This module provides functionality to identify and fix form inputs
with missing labels, ensuring WCAG 2.1 compliance for form controls.
"""

from html.parser import HTMLParser
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import re
import difflib


@dataclass
class InputInfo:
    """Information about a form input element for remediation."""
    tag: str
    attributes: dict
    text_content: str
    start_tag: str
    end_tag: str
    line_number: int
    parent_form: Optional[str] = None
    siblings: List[str] = field(default_factory=list)


@dataclass
class InputFix:
    """Result of fixing a form input accessibility issue."""
    original_html: str
    fixed_html: str
    explanation: str
    aria_label_added: bool = False
    label_added: bool = False


class InputHTMLParser(HTMLParser):
    """
    Custom HTML parser to extract form input elements.

    Uses the standard library html.parser module to parse HTML and identify
    input, select, and textarea elements that may need labels.
    """

    def __init__(self):
        super().__init__()
        self.inputs: List[InputInfo] = []
        self._in_textarea: bool = False
        self._textarea_attrs: dict = {}
        self._textarea_text: str = ""

    def handle_starttag(self, tag: str, attrs: list):
        """Handle opening tags."""
        tag_lower = tag.lower()

        if tag_lower in ("input", "select"):
            attrs_dict = {k.lower(): v for k, v in attrs}
            input_info = InputInfo(
                tag=tag_lower,
                attributes=attrs_dict,
                text_content="",
                start_tag=self._build_tag(tag_lower, attrs_dict),
                end_tag="",
                line_number=self.getpos()[0],
            )
            self.inputs.append(input_info)

        elif tag_lower == "textarea":
            attrs_dict = {k.lower(): v for k, v in attrs}
            self._textarea_attrs = attrs_dict
            self._textarea_text = ""
            self._in_textarea = True

    def handle_startendtag(self, tag: str, attrs: list):
        """Handle self-closing tags (HTML5 style)."""
        tag_lower = tag.lower()

        if tag_lower in ("input", "select"):
            attrs_dict = {k.lower(): v for k, v in attrs}
            input_info = InputInfo(
                tag=tag_lower,
                attributes=attrs_dict,
                text_content="",
                start_tag=self._build_tag(tag_lower, attrs_dict),
                end_tag="",
                line_number=self.getpos()[0],
            )
            self.inputs.append(input_info)

    def handle_endtag(self, tag: str):
        """Handle closing tags for textarea."""
        tag_lower = tag.lower()

        if tag_lower == "textarea" and self._in_textarea:
            # Create textarea InputInfo with captured text
            textarea_info = InputInfo(
                tag="textarea",
                attributes=self._textarea_attrs,
                text_content=self._textarea_text,
                start_tag=self._build_tag("textarea", self._textarea_attrs),
                end_tag="</textarea>",
                line_number=self.getpos()[0],
            )
            self.inputs.append(textarea_info)
            self._in_textarea = False

    def handle_data(self, data: str):
        """Handle text content within textarea elements."""
        if self._in_textarea:
            self._textarea_text += data

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
        if value is None:
            return ""
        return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def has_label(input_elem: InputInfo) -> Tuple[bool, str]:
    """
    Check if a form input has an accessible label.

    According to WCAG, an input has an accessible label if it has:
    - aria-label attribute
    - aria-labelledby attribute
    - An associated label element via for/id matching
    - A visible label wrapper (input inside label element)
    - Text content (for textarea)

    Returns:
        Tuple of (has_label, reason_if_missing)
    """
    attrs = input_elem.attributes

    # Check for aria-labelledby
    if attrs.get("aria-labelledby"):
        return True, ""

    # Check for aria-label
    if attrs.get("aria-label"):
        return True, ""

    # Check for textarea with text content
    if input_elem.tag == "textarea" and input_elem.text_content.strip():
        return True, ""

    # Check for visible text content in the input tag itself
    # (e.g., <textarea>Description</textarea> would have text)
    if input_elem.text_content.strip():
        return True, ""

    return False, "Input has no aria-label, aria-labelledby, or visible text"


def infer_input_label(input_elem: InputInfo) -> str:
    """
    Infer an appropriate aria-label for an input based on its context.

    Strategy:
    1. Look at the input's type attribute
    2. Look at the input's id, name, and placeholder attributes
    3. Look at associated labels in siblings/context
    4. Generate a descriptive label
    """
    attrs = input_elem.attributes

    # Get input type
    input_type = attrs.get("type", "text").lower()

    # Common type labels
    type_labels = {
        "email": "Email address",
        "password": "Password",
        "username": "Username",
        "text": "Text input",
        "textarea": "Description",
        "number": "Number",
        "tel": "Phone number",
        "url": "Website URL",
        "search": "Search",
        "date": "Date",
        "time": "Time",
        "checkbox": "Option",
        "radio": "Option",
    }

    # Start with type-based default for text inputs
    suggested = type_labels.get(input_type, "Input")

    # Try to get more context from attributes
    if "id" in attrs:
        id_val = attrs["id"]
        readable = _id_to_readable(id_val)
        if readable and readable != "Input":
            suggested = readable

    if "name" in attrs:
        name_val = attrs["name"]
        readable = _id_to_readable(name_val)
        if readable and readable != "Input":
            suggested = readable

    if "placeholder" in attrs:
        placeholder = attrs["placeholder"]
        # Use placeholder as basis for label if it's meaningful
        if placeholder and len(placeholder) > 2:
            suggested = placeholder

    # Special handling for checkbox/radio
    if input_type in ("checkbox", "radio"):
        # These often have associated labels with text
        # We'll use a generic label if we can't find context
        if "aria-label" not in attrs:
            # Use the id or name to infer
            if "id" in attrs:
                label_text = _id_to_readable(attrs["id"])
            elif "name" in attrs:
                label_text = _id_to_readable(attrs["name"])
            else:
                label_text = "Option"
            suggested = label_text

    # Add suffix for clarity on some types
    if input_type in ("email", "tel", "url"):
        if "address" not in suggested.lower() and "number" not in suggested.lower():
            suggested = f"{suggested} address"

    # Capitalize first letter
    suggested = suggested[0].upper() + suggested[1:]

    return suggested


def _id_to_readable(id_str: str) -> str:
    """
    Convert an ID like 'email-address' or 'searchQuery' to readable like 'Email address' or 'Search query'.
    """
    # Remove common suffixes
    text = id_str
    suffixes = ['-input', '-field', '-control', 'Input', 'Field']
    for suffix in suffixes:
        if text.endswith(suffix):
            text = text[:-len(suffix)]
            break

    # Replace hyphens and underscores with spaces
    text = re.sub(r'[_-]+', ' ', text)

    # Handle camelCase/PascalCase
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

    # Replace common technical terms with user-friendly terms
    replacements = {
        'email': 'Email address',
        'username': 'Username',
        'password': 'Password',
        'phone': 'Phone number',
        'url': 'Website',
        'search': 'Search',
        'description': 'Description',
        'label': 'Label',
        'name': 'Name',
    }

    text_lower = text.lower()
    for tech_term, friendly in replacements.items():
        if tech_term in text_lower:
            # Replace the term
            text = re.sub(re.escape(tech_term), friendly, text, flags=re.IGNORECASE)
            break

    # Capitalize each word
    words = text.split()
    words = [w.capitalize() for w in words if w]

    return ' '.join(words) if words else "Input"


def generate_input_fix(original_html: str, line_number: Optional[int] = None) -> InputFix:
    """
    Generate a fix for an input that lacks an accessible label.

    Uses the input_fixer module to intelligently generate aria-label
    based on input context (type, id, class, placeholder, etc.).

    Args:
        original_html: The HTML string containing the input
        line_number: Optional line number for context

    Returns:
        InputFix with the remediated HTML
    """
    parser = InputHTMLParser()

    try:
        parser.feed(original_html)
    except Exception:
        return InputFix(
            original_html=original_html,
            fixed_html=original_html,
            explanation="Could not parse HTML for remediation",
            aria_label_added=False,
        )

    if not parser.inputs:
        return InputFix(
            original_html=original_html,
            fixed_html=original_html,
            explanation="No input element found in HTML fragment",
            aria_label_added=False,
        )

    # Get the first input (we process one finding at a time)
    input_elem = parser.inputs[0]

    # Check if it already has a label
    has_label_attr, reason = has_label(input_elem)
    if has_label_attr:
        return InputFix(
            original_html=original_html,
            fixed_html=original_html,
            explanation="Input already has an accessible label",
            aria_label_added=False,
        )

    # Generate aria-label and apply fix
    aria_label = infer_input_label(input_elem)

    # Build the fixed HTML
    fixed_html = _add_aria_label_to_html(original_html, aria_label)

    return InputFix(
        original_html=original_html,
        fixed_html=fixed_html,
        explanation=f"Added aria-label=\"{aria_label}\" to provide accessible name for screen readers",
        aria_label_added=True,
    )


def _add_aria_label_to_html(html: str, aria_label: str) -> str:
    """
    Add an aria-label attribute to the first input/select/textarea in the HTML.
    """
    # Simple approach: find input/select/textarea and add aria-label
    # Pattern for input/select tags
    input_pattern = r'(<(input|select)(\s+[^>]*)?>)'
    textarea_pattern = r'(<textarea(\s+[^>]*)?>)'

    # Try to match input/select first
    def add_aria_to_input(match):
        full_tag = match.group(0)
        attrs_part = match.group(3) if match.group(3) else ""
        return f'<input{attrs_part} aria-label="{aria_label}">'

    # Check if it's an input/select
    if 'input' in html or 'select' in html:
        result = re.sub(input_pattern, add_aria_to_input, html, count=1, flags=re.IGNORECASE)
        if result != html:
            return result

    # Check if it's a textarea
    if 'textarea' in html:
        def add_aria_to_textarea_match(match):
            full_tag = match.group(0)
            attrs_part = match.group(2) if match.group(2) else ""
            return f'<textarea{attrs_part} aria-label="{aria_label}">'
        result = re.sub(textarea_pattern, add_aria_to_textarea_match, html, count=1, flags=re.IGNORECASE)
        if result != html:
            return result

    return html


def generate_unified_diff(original_html: str, modified_html: str, file_path: str = "index.html") -> str:
    """
    Generate a unified diff between original and modified HTML.
    """
    original_lines = original_html.splitlines(keepends=True)
    modified_lines = modified_html.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
    )

    return "".join(diff)


def analyze_html_for_inputs(html: str) -> List[InputInfo]:
    """
    Analyze HTML to find all inputs that may need labels.

    Args:
        html: HTML string to analyze

    Returns:
        List of InputInfo objects for inputs without accessible labels
    """
    parser = InputHTMLParser()
    parser.feed(html)

    unlabeled_inputs = []
    for input_elem in parser.inputs:
        has_label_attr, _ = has_label(input_elem)
        if not has_label_attr:
            unlabeled_inputs.append(input_elem)

    return unlabeled_inputs