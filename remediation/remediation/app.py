"""
FastAPI application for the Remediation module.

Provides endpoints for generating and applying code fixes
for accessibility issues.
"""

from fastapi import FastAPI, HTTPException
from pathlib import Path
import uuid

from remediation.models import (
    AccessibilityFinding,
    RemediationRequest,
    RemediationResponse,
)

app = FastAPI(
    title="AccessPath AI - Remediation Service",
    description="Generate and apply code fixes for accessibility issues",
    version="0.1.0",
)


@app.post("/remediate", response_model=RemediationResponse)
async def remediate(request: RemediationRequest) -> RemediationResponse:
    """
    Generate code fixes for accessibility findings.

    This endpoint receives findings from the AI Investigator,
    generates appropriate code changes, and returns proposed fixes
    for developer approval.

    Args:
        request: RemediationRequest containing findings to fix

    Returns:
        RemediationResponse with proposed code changes
    """
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

    return RemediationResponse(
        request_id=request_id,
        changes=changes,
        status="pending",
        requires_approval=len(changes) > 0,
        summary=summary,
    )


def generate_fix_for_finding(finding: AccessibilityFinding):
    """
    Generate a code fix for a single accessibility finding.

    This is a simple implementation for Milestone 1.
    In later milestones, this will be expanded to handle more issue types.
    """
    from remediation.models import CodeChange, ChangeType

    # Simple fix generation logic based on issue type
    if finding.issue_type.value == "button-name-missing":
        return _generate_button_name_fix(finding)
    elif finding.issue_type.value == "input-label-missing":
        return _generate_input_label_fix(finding)

    # Not implemented for other issue types yet
    return None


def _generate_button_name_fix(finding: AccessibilityFinding) -> CodeChange:
    """Generate a fix for missing button accessible name."""
    html = finding.html

    # Simple heuristic: if button has text but no aria-label/name,
    # we might need to add context or verify the text is sufficient

    return CodeChange(
        finding_id=finding.finding_id,
        file_path=finding.file_path or "unknown",
        original_code=html,
        modified_code=html,  # To be updated in later milestones
        diff=f"@@ -1 +1 @@\n-{html}\n+{html}",  # Placeholder
        change_type=ChangeType.ADD_ARIA_LABEL,
        explanation="Button needs an accessible name for screen readers",
    )


def _generate_input_label_fix(finding: AccessibilityFinding) -> CodeChange:
    """Generate a fix for missing input label."""
    html = finding.html

    return CodeChange(
        finding_id=finding.finding_id,
        file_path=finding.file_path or "unknown",
        original_code=html,
        modified_code=html,  # To be updated in later milestones
        diff=f"@@ -1 +1 @@\n-{html}\n+{html}",  # Placeholder
        change_type=ChangeType.WRAP_WITH_LABEL,
        explanation="Input needs a label for screen readers",
    )