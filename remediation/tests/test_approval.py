"""
Unit tests for the approval workflow module.

Tests cover approval/rejection endpoints, approval storage,
and status tracking.
"""

import pytest
from fastapi.testclient import TestClient

from remediation.app import app
from remediation.models import (
    AccessibilityFinding,
    IssueType,
    ApprovalDecision,
)
from remediation.approval_store import get_approval_store, reset_approval_store


@pytest.fixture(autouse=True)
def reset_store():
    """Reset approval store before each test."""
    reset_approval_store()
    yield
    reset_approval_store()


class TestApprovalEndpoints:
    """Tests for the approval API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    def test_approve_request(self, client):
        """Test approving a remediation request."""
        # First create a remediation request
        finding = AccessibilityFinding(
            finding_id="test-001",
            issue_type=IssueType.BUTTON_NAME_MISSING,
            element="#submit-btn",
            html='<button id="submit-btn"></button>',
            root_cause="No accessible name",
        )

        response = client.post('/remediate', json={
            'findings': [finding.model_dump(exclude_none=True)]
        })

        assert response.status_code == 200
        data = response.json()
        request_id = data['request_id']

        # Now approve the request
        approve_response = client.post(
            f'/approve/{request_id}',
            json={'reviewer': 'test-user', 'feedback': 'Looks good'}
        )

        assert approve_response.status_code == 200
        approval = approve_response.json()
        assert approval['decision'] == 'approved'
        assert approval['reviewer'] == 'test-user'

    def test_reject_request(self, client):
        """Test rejecting a remediation request."""
        finding = AccessibilityFinding(
            finding_id="test-002",
            issue_type=IssueType.INPUT_LABEL_MISSING,
            element="#email",
            html='<input type="email" id="email">',
            root_cause="No label",
        )

        response = client.post('/remediate', json={
            'findings': [finding.model_dump(exclude_none=True)]
        })

        data = response.json()
        request_id = data['request_id']

        # Reject the request
        reject_response = client.post(
            f'/reject/{request_id}',
            json={'reviewer': 'test-user', 'feedback': 'Needs different approach'}
        )

        assert reject_response.status_code == 200
        approval = reject_response.json()
        assert approval['decision'] == 'rejected'
        assert 'needs different' in approval['feedback'].lower()

    def test_approve_nonexistent_request(self, client):
        """Test that approving a non-existent request returns 404."""
        response = client.post('/approve/nonexistent-id', json={})
        assert response.status_code == 404

    def test_reject_nonexistent_request(self, client):
        """Test that rejecting a non-existent request returns 404."""
        response = client.post('/reject/nonexistent-id', json={})
        assert response.status_code == 404

    def test_get_request_status_pending(self, client):
        """Test getting status of a pending request."""
        finding = AccessibilityFinding(
            finding_id="test-003",
            issue_type=IssueType.BUTTON_NAME_MISSING,
            element="#btn",
            html='<button id="btn">Click</button>',
            root_cause="OK",
        )

        response = client.post('/remediate', json={
            'findings': [finding.model_dump(exclude_none=True)]
        })

        request_id = response.json()['request_id']

        status = client.get(f'/status/{request_id}')

        assert status.status_code == 200
        data = status.json()
        assert data['status'] == 'pending'
        assert data['approval_status'] == 'pending'

    def test_get_request_status_after_approval(self, client):
        """Test getting status after approval."""
        finding = AccessibilityFinding(
            finding_id="test-004",
            issue_type=IssueType.BUTTON_NAME_MISSING,
            element="#btn",
            html='<button id="btn"></button>',
            root_cause="No name",
        )

        response = client.post('/remediate', json={
            'findings': [finding.model_dump(exclude_none=True)]
        })

        request_id = response.json()['request_id']

        # Approve
        client.post(f'/approve/{request_id}', json={'reviewer': 'user'})

        # Get status
        status = client.get(f'/status/{request_id}')
        data = status.json()

        assert data['status'] == 'approved'
        assert data['approval_status'] == 'approved'

    def test_list_pending_requests(self, client):
        """Test listing all pending requests."""
        # Create two requests
        for i in range(2):
            finding = AccessibilityFinding(
                finding_id=f"pending-{i}",
                issue_type=IssueType.BUTTON_NAME_MISSING,
                element=f"#btn{i}",
                html=f'<button id="btn{i}"></button>',
                root_cause="No name",
            )
            client.post('/remediate', json={
                'findings': [finding.model_dump(exclude_none=True)]
            })

        pending = client.get('/pending')
        assert pending.status_code == 200
        assert len(pending.json()) == 2


class TestPartialApproval:
    """Tests for partial approval/rejection."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_approve_specific_changes(self, client):
        """Test approving only specific changes by finding_id."""
        findings = [
            AccessibilityFinding(
                finding_id="partial-1",
                issue_type=IssueType.BUTTON_NAME_MISSING,
                element="#btn1",
                html='<button id="btn1"></button>',
                root_cause="No name",
            ),
            AccessibilityFinding(
                finding_id="partial-2",
                issue_type=IssueType.INPUT_LABEL_MISSING,
                element="#input1",
                html='<input id="input1">',
                root_cause="No label",
            ),
        ]

        response = client.post('/remediate', json={
            'findings': [f.model_dump(exclude_none=True) for f in findings]
        })

        request_id = response.json()['request_id']

        # Approve only the first change
        approve = client.post(
            f'/approve/{request_id}',
            json={'approved_changes': ['partial-1']}
        )

        assert approve.status_code == 200
        record = approve.json()
        assert 'partial-1' in record['approved_changes']

    def test_reject_specific_changes(self, client):
        """Test rejecting only specific changes by finding_id."""
        findings = [
            AccessibilityFinding(
                finding_id="reject-1",
                issue_type=IssueType.BUTTON_NAME_MISSING,
                element="#btn1",
                html='<button id="btn1"></button>',
                root_cause="No name",
            ),
            AccessibilityFinding(
                finding_id="reject-2",
                issue_type=IssueType.INPUT_LABEL_MISSING,
                element="#input1",
                html='<input id="input1">',
                root_cause="No label",
            ),
        ]

        response = client.post('/remediate', json={
            'findings': [f.model_dump(exclude_none=True) for f in findings]
        })

        request_id = response.json()['request_id']

        # Reject only the first change
        reject = client.post(
            f'/reject/{request_id}',
            json={'rejected_changes': ['reject-1']}
        )

        assert reject.status_code == 200
        record = reject.json()
        assert 'reject-1' in record['rejected_changes']


class TestApprovalStore:
    """Tests for the ApprovalStore class directly."""

    def test_store_response_and_retrieve(self):
        """Test storing and retrieving a response."""
        from remediation.models import RemediationResponse, CodeChange, ChangeType

        store = get_approval_store()

        # Create a response
        change = CodeChange(
            finding_id="test",
            file_path="/test.html",
            original_code="<button></button>",
            modified_code='<button aria-label="Submit"></button>',
            diff="diff",
            change_type=ChangeType.ADD_ARIA_LABEL,
        )

        response = RemediationResponse(
            request_id="req-test",
            changes=[change],
            status="pending",
            requires_approval=True,
            summary="1 change",
        )

        store.store_response("req-test", response)
        retrieved = store.get_response("req-test")

        assert retrieved is not None
        assert retrieved.request_id == "req-test"
        assert len(retrieved.changes) == 1

    def test_get_pending_and_approved(self):
        """Test getting pending and approved request lists."""
        from remediation.models import RemediationResponse, CodeChange, ChangeType

        store = get_approval_store()

        # Create and store two responses
        change = CodeChange(
            finding_id="test",
            file_path="/test.html",
            original_code="<button></button>",
            modified_code='<button aria-label="Submit"></button>',
            diff="diff",
            change_type=ChangeType.ADD_ARIA_LABEL,
        )

        response1 = RemediationResponse(
            request_id="pending-req",
            changes=[change],
            status="pending",
            requires_approval=True,
            summary="1 change",
        )

        response2 = RemediationResponse(
            request_id="approved-req",
            changes=[change],
            status="pending",
            requires_approval=True,
            summary="1 change",
        )

        store.store_response("pending-req", response1)
        store.store_response("approved-req", response2)

        # Record approval for second
        from remediation.approval_store import ApprovalStore
        store.record_approval("approved-req", ApprovalDecision.APPROVED)

        pending = store.get_pending_requests()
        approved = store.get_approved_requests()

        assert "pending-req" in pending
        assert "approved-req" in approved


class TestIntegration:
    """Integration tests for the full approval workflow."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_full_workflow(self, client):
        """Test the complete workflow: create -> approve -> status -> changes."""
        # 1. Create remediation request
        finding = AccessibilityFinding(
            finding_id="workflow-test",
            issue_type=IssueType.BUTTON_NAME_MISSING,
            element="#submit",
            html='<button id="submit" type="submit"></button>',
            root_cause="No accessible name",
        )

        remediate_response = client.post('/remediate', json={
            'findings': [finding.model_dump(exclude_none=True)]
        })

        assert remediate_response.status_code == 200
        data = remediate_response.json()
        request_id = data['request_id']
        assert len(data['changes']) == 1

        # 2. Check pending status
        status = client.get(f'/status/{request_id}')
        assert status.json()['status'] == 'pending'

        # 3. Approve the request
        approve_response = client.post(
            f'/approve/{request_id}',
            json={'reviewer': 'integration-test'}
        )
        assert approve_response.status_code == 200

        # 4. Verify status after approval
        status = client.get(f'/status/{request_id}')
        assert status.json()['status'] == 'approved'

        # 5. Get changes to apply
        store = get_approval_store()
        changes = store.get_changes_to_apply(request_id)
        assert len(changes) == 1

    def test_no_double_approval(self, client):
        """Test that double approval is prevented."""
        finding = AccessibilityFinding(
            finding_id="double-test",
            issue_type=IssueType.BUTTON_NAME_MISSING,
            element="#btn",
            html='<button id="btn"></button>',
            root_cause="No name",
        )

        response = client.post('/remediate', json={
            'findings': [finding.model_dump(exclude_none=True)]
        })

        request_id = response.json()['request_id']

        # First approval
        approve1 = client.post(f'/approve/{request_id}', json={'reviewer': 'user1'})
        assert approve1.status_code == 200

        # Second approval attempt
        approve2 = client.post(f'/approve/{request_id}', json={'reviewer': 'user2'})
        assert approve2.status_code == 400  # Bad request - already approved