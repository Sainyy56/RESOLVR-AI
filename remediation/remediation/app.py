"""
FastAPI application for the Remediation module.

Provides endpoints for generating and applying code fixes
for accessibility issues.
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pathlib import Path
import uuid
import logging
import html.parser
from typing import Optional

from remediation.models import (
    AccessibilityFinding,
    RemediationRequest,
    RemediationResponse,
    IssueType,
    ChangeType,
    CodeChange,
    ApprovalDecision,
    ApprovalRecord,
    RemediationStatus,
    ApprovalRequest,
    RejectionRequest,
)
from remediation.button_fixer import (
    generate_button_fix as _generate_button_fix_impl,
    generate_unified_diff as _button_unified_diff,
)
from remediation.input_fixer import (
    generate_input_fix as _generate_input_fix_impl,
    generate_unified_diff as _input_unified_diff,
)
from remediation.approval_store import get_approval_store
from remediation.button_fixer import (
    generate_button_fix as _generate_button_fix_impl,
    generate_unified_diff as _button_unified_diff,
)
from remediation.input_fixer import (
    generate_input_fix as _generate_input_fix_impl,
    generate_unified_diff as _input_unified_diff,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AccessPath AI - Remediation Service",
    description="Generate and apply code fixes for accessibility issues",
    version="0.1.0",
)


class ValidationError(Exception):
    """Custom exception for validation errors."""
    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle validation errors with a consistent response format."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "validation_failed",
            "message": exc.message,
            "field": exc.field,
        }
    )


def validate_finding(finding: AccessibilityFinding, index: int) -> None:
    """
    Validate a single accessibility finding.

    Raises ValidationError if validation fails.
    """
    # Validate finding_id
    if not finding.finding_id or len(finding.finding_id) > 100:
        raise ValidationError(
            f"Finding ID must be 1-100 characters",
            field=f"findings[{index}].finding_id"
        )

    # Validate element selector
    if not finding.element or len(finding.element) > 500:
        raise ValidationError(
            "Element selector is required and must be <= 500 characters",
            field=f"findings[{index}].element"
        )

    # Validate HTML content
    if not finding.html or len(finding.html) > 50000:
        raise ValidationError(
            "HTML content is required and must be <= 50000 characters",
            field=f"findings[{index}].html"
        )

    # Validate file_path if provided
    if finding.file_path:
        validate_file_path(finding.file_path, index)

    # Validate line_number if provided
    if finding.line_number is not None and finding.line_number < 1:
        raise ValidationError(
            "Line number must be positive",
            field=f"findings[{index}].line_number"
        )


def validate_file_path(file_path: str, finding_index: int) -> None:
    """
    Validate that a file path is safe and reasonable.

    Prevents path traversal attacks and validates format.
    """
    if not file_path:
        return

    # Check for path traversal attempts
    if ".." in file_path:
        raise ValidationError(
            "File path cannot contain '..' (path traversal)",
            field=f"findings[{finding_index}].file_path"
        )

    # Check for absolute paths starting with /
    if file_path.startswith("/") and not file_path.startswith("/project/") and not file_path.startswith("/home/"):
        # Allow absolute paths for now, but log for security
        logger.warning(f"Unusual absolute path in finding: {file_path}")

    # Validate path format
    try:
        Path(file_path)  # This will raise if invalid format
    except Exception as e:
        raise ValidationError(
            f"Invalid file path format: {str(e)}",
            field=f"findings[{finding_index}].file_path"
        )

    # Check path length
    if len(file_path) > 1000:
        raise ValidationError(
            "File path must be <= 1000 characters",
            field=f"findings[{finding_index}].file_path"
        )


def validate_html_safety(html: str, finding_index: int) -> None:
    """
    Perform basic HTML safety validation.

    This is a lightweight check - more thorough validation
    will happen during actual analysis.
    """
    # Check for obviously dangerous patterns (basic check)
    dangerous_patterns = [
        "javascript:",
        "vbscript:",
        "onerror=",
        "onclick=",
    ]

    html_lower = html.lower()
    for pattern in dangerous_patterns:
        if pattern in html_lower:
            logger.warning(
                f"Potentially dangerous HTML pattern found in finding {finding_index}: {pattern}"
            )
            # Don't raise error - just log warning


def validate_request(request: RemediationRequest) -> None:
    """
    Validate the entire remediation request.

    Raises ValidationError if validation fails.
    """
    # Check findings array is not empty
    if not request.findings:
        raise ValidationError(
            "At least one finding is required"
        )

    # Limit number of findings per request (prevent abuse)
    if len(request.findings) > 100:
        raise ValidationError(
            "Maximum 100 findings per request"
        )

    # Validate each finding
    for idx, finding in enumerate(request.findings):
        validate_finding(finding, idx)
        validate_html_safety(finding.html, idx)

    # Validate repo_path if provided
    if request.repo_path:
        if len(request.repo_path) > 500:
            raise ValidationError(
                "Repository path must be <= 500 characters"
            )
        if ".." in request.repo_path:
            raise ValidationError(
                "Repository path cannot contain '..' (path traversal)"
            )

    # Validate target_branch if provided
    if request.target_branch:
        if not request.target_branch.replace("-", "").replace("_", "").isalnum():
            raise ValidationError(
                "Branch name can only contain alphanumeric characters, hyphens, and underscores"
            )
        if len(request.target_branch) > 100:
            raise ValidationError(
                "Branch name must be <= 100 characters"
            )


@app.post("/remediate", response_model=RemediationResponse)
async def remediate(request: RemediationRequest) -> RemediationResponse:
    """
    Generate code fixes for accessibility findings.

    This endpoint receives findings from the AI Investigator,
    validates the input, generates appropriate code changes,
    and returns proposed fixes for developer approval.

    Args:
        request: RemediationRequest containing findings to fix

    Returns:
        RemediationResponse with proposed code changes

    Raises:
        400 Bad Request: If input validation fails
    """
    # Validate the request
    validate_request(request)

    logger.info(f"Processing remediation request with {len(request.findings)} findings")

    request_id = str(uuid.uuid4())

    changes = []

    for finding in request.findings:
        # Map issue types to their fix generators
        fix = generate_fix_for_finding(finding)
        if fix:
            changes.append(fix)

    summary = f"{len(changes)} change(s) proposed: "
    if changes:
        change_types = [c.change_type.value for c in changes]
        summary += ", ".join(change_types)
    else:
        summary += "No automatic fixes generated"

    logger.info(f"Generated {len(changes)} changes for request {request_id}")

    response = RemediationResponse(
        request_id=request_id,
        changes=changes,
        status="pending",
        requires_approval=len(changes) > 0,
        summary=summary,
    )

    # Store the response for later approval
    store = get_approval_store()
    store.store_response(request_id, response)

    return response


def generate_fix_for_finding(finding: AccessibilityFinding):
    """
    Generate a code fix for a single accessibility finding.

    This is a simple implementation for Milestone 1.
    In later milestones, this will be expanded to handle more issue types.
    """
    # Simple fix generation logic based on issue type
    if finding.issue_type.value == "button-name-missing":
        return _generate_button_name_fix(finding)
    elif finding.issue_type.value == "input-label-missing":
        return _generate_input_label_fix(finding)

    # Not implemented for other issue types yet
    return None


def _generate_button_name_fix(finding: AccessibilityFinding) -> CodeChange:
    """Generate a fix for missing button accessible name.

    Uses the button_fixer module to intelligently generate aria-label
    based on button context (type, id, class, parent form, etc.).
    """
    html = finding.html

    # Use the button fixer module to generate an intelligent fix
    fix = _generate_button_fix_impl(html)

    # Generate unified diff for the change
    diff = _button_unified_diff(
        fix.original_html,
        fix.fixed_html,
        file_path=finding.file_path or "index.html"
    )

    return CodeChange(
        finding_id=finding.finding_id,
        file_path=finding.file_path or "unknown",
        original_code=fix.original_html,
        modified_code=fix.fixed_html,
        diff=diff.rstrip('\n'),  # Remove trailing newline if present
        change_type=ChangeType.ADD_ARIA_LABEL,
        explanation=fix.explanation,
    )


def _generate_input_label_fix(finding: AccessibilityFinding) -> CodeChange:
    """Generate a fix for missing input label.

    Uses the input_fixer module to intelligently generate aria-label
    based on input context (type, id, placeholder, etc.).
    """
    html = finding.html

    # Use the input fixer module to generate an intelligent fix
    fix = _generate_input_fix_impl(html)

    # Generate unified diff for the change
    diff = _input_unified_diff(
        fix.original_html,
        fix.fixed_html,
        file_path=finding.file_path or "index.html"
    )

    return CodeChange(
        finding_id=finding.finding_id,
        file_path=finding.file_path or "unknown",
        original_code=fix.original_html,
        modified_code=fix.fixed_html,
        diff=diff.rstrip('\n'),  # Remove trailing newline if present
        change_type=ChangeType.ADD_ARIA_LABEL,
        explanation=fix.explanation,
    )


# ============================================================================
# Approval Endpoints - Milestone 6 Phase 1
# ============================================================================

@app.post("/approve/{request_id}", response_model=ApprovalRecord)
async def approve_request(
    request_id: str,
    approval: ApprovalRequest
):
    """
    Approve a remediation request.

    Approves the proposed changes for application. Can optionally
    approve only specific changes by providing their finding_ids.

    Args:
        request_id: ID of the remediation request to approve
        approval: ApprovalRequest with reviewer, feedback, and optional approved_changes

    Returns:
        ApprovalRecord with the decision details

    Raises:
        404 Not Found: If request_id doesn't exist
        400 Bad Request: If no changes to approve
    """
    store = get_approval_store()

    # Check if response exists
    response = store.get_response(request_id)
    if not response:
        raise HTTPException(
            status_code=404,
            detail=f"Remediation request {request_id} not found"
        )

    # Check if already approved
    existing = store.get_approval(request_id)
    if existing and existing.decision == ApprovalDecision.APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"Request {request_id} has already been approved"
        )

    # Record the approval
    record = store.record_approval(
        request_id=request_id,
        decision=ApprovalDecision.APPROVED,
        reviewer=approval.reviewer,
        feedback=approval.feedback,
        approved_changes=approval.approved_changes,
    )

    logger.info(f"Approved remediation request {request_id} by {approval.reviewer or 'anonymous'}")

    return record


@app.post("/reject/{request_id}", response_model=ApprovalRecord)
async def reject_request(
    request_id: str,
    rejection: RejectionRequest
):
    """
    Reject a remediation request.

    Rejects the proposed changes. Can optionally reject only specific
    changes by providing their finding_ids (useful for partial rejection).

    Args:
        request_id: ID of the remediation request to reject
        rejection: RejectionRequest with reviewer, feedback, and optional rejected_changes

    Returns:
        ApprovalRecord with the decision details

    Raises:
        404 Not Found: If request_id doesn't exist
    """
    store = get_approval_store()

    # Check if response exists
    response = store.get_response(request_id)
    if not response:
        raise HTTPException(
            status_code=404,
            detail=f"Remediation request {request_id} not found"
        )

    # Record the rejection
    record = store.record_approval(
        request_id=request_id,
        decision=ApprovalDecision.REJECTED,
        reviewer=rejection.reviewer,
        feedback=rejection.feedback,
        rejected_changes=rejection.rejected_changes,
    )

    logger.info(f"Rejected remediation request {request_id} by {rejection.reviewer or 'anonymous'}")

    return record


@app.get("/status/{request_id}", response_model=RemediationStatus)
async def get_request_status(request_id: str):
    """
    Get the current status of a remediation request.

    Shows whether the request is pending, approved, rejected, or applied.

    Args:
        request_id: ID of the remediation request

    Returns:
        RemediationStatus with current state

    Raises:
        404 Not Found: If request_id doesn't exist
    """
    store = get_approval_store()

    response = store.get_response(request_id)
    if not response:
        raise HTTPException(
            status_code=404,
            detail=f"Remediation request {request_id} not found"
        )

    approval = store.get_approval(request_id)

    # Determine status
    if approval:
        status = approval.decision.value
        if approval.applied and approval.decision != ApprovalDecision.REJECTED:
            status = "applied"
    else:
        status = "pending" if response.requires_approval else response.status

    return RemediationStatus(
        request_id=request_id,
        status=status,
        approval_status=approval.decision if approval else ApprovalDecision.PENDING,
        changes=response.changes,
        approval_record=approval,
        summary=response.summary,
    )


@app.get("/pending", response_model=list[str])
async def list_pending_requests():
    """
    List all remediation requests pending approval.

    Returns:
        List of request IDs awaiting approval
    """
    store = get_approval_store()
    return store.get_pending_requests()