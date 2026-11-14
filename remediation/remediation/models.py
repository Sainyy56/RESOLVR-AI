"""
Data models for the Remediation module.

These Pydantic models define the data contract between:
- The AI Investigator (input)
- The Remediation module (processing)
- The Developer (approval interface)
- The Backend (results)
"""

from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field


class IssueType(str, Enum):
    """Types of accessibility issues we handle."""

    BUTTON_NAME_MISSING = "button-name-missing"
    INPUT_LABEL_MISSING = "input-label-missing"
    IMAGE_ALT_MISSING = "image-alt-missing"
    LINK_NAME_MISSING = "link-name-missing"
    FORM_INPUT_EMPTY = "form-input-empty"
    HEADING_IMPROPER = "heading-improper"
    CONTRAST_INSUFFICIENT = "color-contrast"


class ChangeType(str, Enum):
    """Types of code changes we can generate."""

    ADD_ARIA_LABEL = "add-aria-label"
    WRAP_WITH_LABEL = "wrap-with-label"
    ADD_ALT_ATTRIBUTE = "add-alt-attribute"
    ADD_ACCESSIBLE_NAME = "add-accessible-name"
    FIX_HEADING_LEVEL = "fix-heading-level"
    ADD_CONTRAST_STYLES = "add-contrast-styles"


class AccessibilityFinding(BaseModel):
    """
    A single accessibility issue identified by the Investigator.

    This is the INPUT to the Remediation module.
    """

    finding_id: str = Field(
        ...,
        description="Unique identifier for this finding"
    )
    issue_type: IssueType = Field(
        ...,
        description="Type of accessibility issue"
    )
    element: str = Field(
        ...,
        description="Selector (CSS/XPath) for the problematic element"
    )
    html: str = Field(
        ...,
        description="Current HTML of the element"
    )
    root_cause: str = Field(
        ...,
        description="AI-identified reason why the issue exists"
    )
    context: dict = Field(
        default_factory=dict,
        description="Additional context from investigation"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Path to the source file (if available)"
    )
    line_number: Optional[int] = Field(
        default=None,
        description="Line number in source file"
    )
    suggested_fix: Optional[str] = Field(
        default=None,
        description="AI's suggested fix (optional guidance)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "finding_id": "f123-abc-456",
                "issue_type": "button-name-missing",
                "element": "#submit-btn",
                "html": "<button>Click me</button>",
                "root_cause": "Button has no accessible name - text content 'Click me' is not programmatically determinable",
                "context": {
                    "parent_tag": "form",
                    "siblings": []
                },
                "file_path": "/project/src/index.html",
                "line_number": 42
            }
        }


class CodeChange(BaseModel):
    """
    A proposed code change to fix an accessibility issue.

    This represents ONE fix for ONE finding.
    """

    finding_id: str = Field(
        ...,
        description="Which finding this change addresses"
    )
    file_path: str = Field(
        ...,
        description="Path to file that needs changing"
    )
    original_code: str = Field(
        ...,
        description="The code BEFORE the fix"
    )
    modified_code: str = Field(
        ...,
        description="The code AFTER the fix"
    )
    diff: str = Field(
        ...,
        description="Unified diff format of changes"
    )
    change_type: ChangeType = Field(
        ...,
        description="What kind of fix this is"
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Human-readable explanation of why this fixes the issue"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "finding_id": "f123-abc-456",
                "file_path": "/project/src/index.html",
                "original_code": '<button id="submit-btn">Click me</button>',
                "modified_code": '<button id="submit-btn" aria-label="Submit form">Click me</button>',
                "diff": '--- a/src/index.html\n+++ b/src/index.html\n@@ -1 +1 @@\n-<button id="submit-btn">Click me</button>\n+<button id="submit-btn" aria-label="Submit form">Click me</button>',
                "change_type": "add-aria-label",
                "explanation": "Added aria-label to make the button's purpose clear for screen readers"
            }
        }


class RemediationRequest(BaseModel):
    """
    Request to generate fixes for accessibility findings.

    This is the INPUT to the /remediate endpoint.
    """

    findings: list[AccessibilityFinding] = Field(
        ...,
        description="List of issues to fix"
    )
    target_branch: Optional[str] = Field(
        default=None,
        description="Name of branch to apply changes to"
    )
    repo_path: Optional[str] = Field(
        default=None,
        description="Path to the project repository"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "findings": [
                    {
                        "finding_id": "f123-abc-456",
                        "issue_type": "button-name-missing",
                        "element": "#submit-btn",
                        "html": "<button>Click me</button>",
                        "root_cause": "Button has no accessible name"
                    }
                ]
            }
        }


class RemediationResponse(BaseModel):
    """
    Response containing the proposed fixes.

    This is the OUTPUT from the /remediate endpoint.
    """

    request_id: str = Field(
        ...,
        description="ID for this remediation request"
    )
    changes: list[CodeChange] = Field(
        default_factory=list,
        description="List of proposed changes"
    )
    status: Literal["pending", "partial", "applied", "failed"] = Field(
        default="pending",
        description="Current status of remediation"
    )
    requires_approval: bool = Field(
        default=True,
        description="Whether developer approval is needed"
    )
    summary: str = Field(
        default="",
        description="Human-readable summary of proposed changes"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "req-789",
                "changes": [
                    {
                        "finding_id": "f123-abc-456",
                        "file_path": "/project/src/index.html",
                        "original_code": "<button>Click me</button>",
                        "modified_code": '<button aria-label="Submit form">Click me</button>',
                        "diff": "@@ -1 +1 @@\n-<button>Click me</button>\n+<button aria-label=\"Submit form\">Click me</button>",
                        "change_type": "add-aria-label"
                    }
                ],
                "status": "pending",
                "requires_approval": True,
                "summary": "1 change proposed: Add aria-label to button"
            }
        }


# Backward compatibility alias
AccessibilityFindingV1 = AccessibilityFinding
CodeChangeV1 = CodeChange