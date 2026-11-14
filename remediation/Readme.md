# Remediation Module

This module handles code fix generation and verification for accessibility issues identified by the AccessPath AI platform.

## Purpose

The remediation module receives structured accessibility findings from the AI Investigator, generates appropriate code fixes, and manages the human approval workflow.

## Responsibilities

1. **Fix Generation**: Create minimal, appropriate code fixes for accessibility issues
2. **Diff Generation**: Produce readable code diffs for developer review
3. **Patch Application**: Apply approved fixes in an isolated environment (worktree)
4. **Verification**: Run builds/tests/rescans to confirm fixes work

## Data Flow

```
Investigator → [AccessibilityFinding] → Remediation Module → [CodeChange] → Developer Approval → Apply → Verify
```

## API Endpoints

- `POST /remediate` - Generate code fixes for accessibility findings

## Usage

```python
from remediation.models import AccessibilityFinding, RemediationRequest

finding = AccessibilityFinding(
    finding_id="abc-123",
    issue_type="button-name",
    element="#submit-btn",
    html="<button>Click me</button>",
    root_cause="Missing accessible name",
    context={}
)

request = RemediationRequest(findings=[finding])
```

See `remediation/models.py` for complete schema definitions.