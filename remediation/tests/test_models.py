"""
Unit tests for remediation data models.

These tests verify that the models correctly serialize/deserialize
and validate data from the Investigator module.
"""

import pytest
from pydantic import ValidationError

from remediation.models import (
    AccessibilityFinding,
    CodeChange,
    RemediationRequest,
    RemediationResponse,
    IssueType,
    ChangeType,
)


class TestAccessibilityFinding:
    """Tests for the AccessibilityFinding model."""

    def test_create_valid_finding_button(self):
        """Test creating a valid button-name-missing finding."""
        finding = AccessibilityFinding(
            finding_id="btn-001",
            issue_type=IssueType.BUTTON_NAME_MISSING,
            element="#submit-btn",
            html='<button id="submit-btn">Click me</button>',
            root_cause="Button has no accessible name attribute",
            context={"parent_tag": "form"},
            file_path="/src/index.html",
            line_number=42,
        )

        assert finding.finding_id == "btn-001"
        assert finding.issue_type == IssueType.BUTTON_NAME_MISSING
        assert finding.element == "#submit-btn"
        assert finding.html == '<button id="submit-btn">Click me</button>'
        assert finding.file_path == "/src/index.html"

    def test_create_finding_minimal(self):
        """Test creating a finding with required fields only."""
        finding = AccessibilityFinding(
            finding_id="btn-002",
            issue_type=IssueType.BUTTON_NAME_MISSING,
            element="button",
            html="<button>Submit</button>",
            root_cause="Missing aria-label",
        )

        assert finding.context == {}  # Default empty dict
        assert finding.file_path is None  # Default None

    def test_finding_serialization(self):
        """Test that findings serialize to JSON correctly."""
        finding = AccessibilityFinding(
            finding_id="btn-003",
            issue_type=IssueType.BUTTON_NAME_MISSING,
            element="button.submit",
            html="<button>Submit</button>",
            root_cause="No accessible name",
        )

        # Serialize to dict
        data = finding.model_dump()
        assert data["finding_id"] == "btn-003"
        assert data["issue_type"] == "button-name-missing"

        # Serialize to JSON string
        json_str = finding.model_dump_json()
        assert "btn-003" in json_str

    def test_finding_deserialization(self):
        """Test that findings deserialize from dict correctly."""
        data = {
            "finding_id": "btn-004",
            "issue_type": "button-name-missing",
            "element": "button",
            "html": "<button>Submit</button>",
            "root_cause": "No accessible name",
        }

        finding = AccessibilityFinding(**data)
        assert finding.finding_id == "btn-004"
        assert finding.issue_type == IssueType.BUTTON_NAME_MISSING

    def test_finding_invalid_missing_required(self):
        """Test that validation fails when required fields are missing."""
        with pytest.raises(ValidationError) as exc_info:
            AccessibilityFinding(
                finding_id="btn-005",
                issue_type=IssueType.BUTTON_NAME_MISSING,
                # Missing: element, html, root_cause
            )

        errors = exc_info.value.errors()
        assert len(errors) == 3  # Three missing required fields


class TestCodeChange:
    """Tests for the CodeChange model."""

    def test_create_code_change(self):
        """Test creating a valid code change."""
        change = CodeChange(
            finding_id="btn-001",
            file_path="/src/index.html",
            original_code='<button id="submit-btn">Submit</button>',
            modified_code='<button id="submit-btn" aria-label="Submit form">Submit</button>',
            diff='--- a/index.html\n+++ b/index.html\n@@ -1 +1 @@\n-<button id="submit-btn">Submit</button>\n+<button id="submit-btn" aria-label="Submit form">Submit</button>',
            change_type=ChangeType.ADD_ARIA_LABEL,
            explanation="Added aria-label for screen reader accessibility",
        )

        assert change.finding_id == "btn-001"
        assert change.change_type == ChangeType.ADD_ARIA_LABEL
        assert "aria-label" in change.modified_code

    def test_code_change_explanation_optional(self):
        """Test that explanation is optional."""
        change = CodeChange(
            finding_id="btn-002",
            file_path="/app.html",
            original_code="<button>Test</button>",
            modified_code="<button>Test</button>",
            diff="no change",
            change_type=ChangeType.ADD_ARIA_LABEL,
            # No explanation provided
        )

        assert change.explanation is None


class TestRemediationRequest:
    """Tests for the RemediationRequest model."""

    def test_create_request_with_findings(self):
        """Test creating a remediation request."""
        findings = [
            AccessibilityFinding(
                finding_id="f1",
                issue_type=IssueType.BUTTON_NAME_MISSING,
                element="#btn1",
                html="<button>Submit</button>",
                root_cause="No accessible name",
            ),
            AccessibilityFinding(
                finding_id="f2",
                issue_type=IssueType.INPUT_LABEL_MISSING,
                element="#email",
                html='<input type="email" id="email">',
                root_cause="No label",
            ),
        ]

        request = RemediationRequest(
            findings=findings,
            repo_path="/my-project",
            target_branch="fix-accessibility",
        )

        assert len(request.findings) == 2
        assert request.repo_path == "/my-project"
        assert request.target_branch == "fix-accessibility"


class TestRemediationResponse:
    """Tests for the RemediationResponse model."""

    def test_create_response(self):
        """Test creating a remediation response."""
        changes = [
            CodeChange(
                finding_id="f1",
                file_path="/index.html",
                original_code="<button>Submit</button>",
                modified_code='<button aria-label="Submit form">Submit</button>',
                diff="diff here",
                change_type=ChangeType.ADD_ARIA_LABEL,
            )
        ]

        response = RemediationResponse(
            request_id="req-123",
            changes=changes,
            status="pending",
            requires_approval=True,
            summary="1 change proposed",
        )

        assert response.request_id == "req-123"
        assert len(response.changes) == 1
        assert response.requires_approval is True

    def test_response_defaults(self):
        """Test default values for response fields."""
        response = RemediationResponse(
            request_id="req-456",
            changes=[],
        )

        assert response.status == "pending"
        assert response.requires_approval is True
        assert response.summary == ""


class TestIssueType:
    """Tests for IssueType enum."""

    def test_all_issue_types_exist(self):
        """Verify all expected issue types are defined."""
        expected = [
            "button-name-missing",
            "input-label-missing",
            "image-alt-missing",
            "link-name-missing",
            "form-input-empty",
            "heading-improper",
            "color-contrast",
        ]

        for issue in expected:
            assert issue in [it.value for it in IssueType]


class TestChangeType:
    """Tests for ChangeType enum."""

    def test_all_change_types_exist(self):
        """Verify all expected change types are defined."""
        expected = [
            "add-aria-label",
            "wrap-with-label",
            "add-alt-attribute",
            "add-accessible-name",
            "fix-heading-level",
            "add-contrast-styles",
        ]

        for change in expected:
            assert change in [ct.value for ct in ChangeType]